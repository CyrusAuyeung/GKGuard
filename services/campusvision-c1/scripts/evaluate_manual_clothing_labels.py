from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import settings  # noqa: E402
from app.storage import db  # noqa: E402


LABEL_PATH = settings.data_dir / "evals" / "manual_clothing_labels" / "person_clothing_labels.json"
REPORT_PATH = settings.data_dir / "evals" / "manual_clothing_labels" / "manual_clothing_eval.json"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_labels(path: Path) -> dict[str, dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    labels = data.get("labels", {})
    if not isinstance(labels, dict):
        raise ValueError("labels must be a dict")
    return labels


def _part_manual(label: dict[str, Any], prefix: str) -> dict[str, Any]:
    return {
        "visible": bool(label.get(f"{prefix}_visible")),
        "color": label.get(f"{prefix}_color") or "unknown",
    }


def _event_part(event: dict[str, Any], prefix: str) -> dict[str, Any]:
    visible = event.get(f"normalized_{prefix}_visible")
    color = event.get(f"normalized_{prefix}_color") or event.get(f"{prefix}_color") or "unknown"
    return {
        "visible": bool(visible) and color != "unknown",
        "color": color,
    }


def _majority_prediction(events: list[dict[str, Any]], prefix: str) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    for event in events:
        part = _event_part(event, prefix)
        if part["visible"] and part["color"] != "unknown":
            counts[part["color"]] += 1
    if not counts:
        return {"visible": False, "color": "unknown", "counts": {}}
    color, support = counts.most_common(1)[0]
    return {
        "visible": True,
        "color": color,
        "support": support,
        "counts": dict(counts.most_common()),
    }


def _session_predictions(person_id: str) -> list[dict[str, Any]]:
    sessions = db.list_appearance_sessions(person_id=person_id)
    out = []
    for session in sessions:
        out.append(
            {
                "session_id": session["session_id"],
                "event_count": session.get("event_count"),
                "upper": {
                    "visible": bool(session.get("upper_visible")) and session.get("upper_color") != "unknown",
                    "color": session.get("upper_color") or "unknown",
                    "support": session.get("upper_color_support"),
                },
                "lower": {
                    "visible": bool(session.get("lower_visible")) and session.get("lower_color") != "unknown",
                    "color": session.get("lower_color") or "unknown",
                    "support": session.get("lower_color_support"),
                },
            }
        )
    return out


def _score_part(manual: dict[str, Any], predicted: dict[str, Any]) -> dict[str, Any]:
    manual_color = manual["color"]
    predicted_color = predicted["color"]
    manual_visible = bool(manual["visible"])
    predicted_visible = bool(predicted["visible"])
    visibility_correct = manual_visible == predicted_visible
    color_evaluable = manual_visible and manual_color != "unknown"
    color_correct = predicted_visible and predicted_color == manual_color if color_evaluable else None
    return {
        "manual": manual,
        "predicted": predicted,
        "visibility_correct": visibility_correct,
        "color_evaluable": color_evaluable,
        "color_correct": color_correct,
    }


def _aggregate_scores(scores: list[dict[str, Any]]) -> dict[str, Any]:
    visibility_total = len(scores)
    visibility_correct = sum(1 for score in scores if score["visibility_correct"])
    color_scores = [score for score in scores if score["color_evaluable"]]
    color_correct = sum(1 for score in color_scores if score["color_correct"])
    return {
        "visibility_total": visibility_total,
        "visibility_correct": visibility_correct,
        "visibility_accuracy": round(visibility_correct / visibility_total, 4) if visibility_total else None,
        "color_total": len(color_scores),
        "color_correct": color_correct,
        "color_accuracy": round(color_correct / len(color_scores), 4) if color_scores else None,
    }


def evaluate(label_path: Path = LABEL_PATH) -> dict[str, Any]:
    db.init_db()
    labels = _load_labels(label_path)
    events_by_person: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in db.list_events(identified=True, limit=5000):
        if event.get("person_id"):
            events_by_person[event["person_id"]].append(event)

    person_results = []
    person_level_scores = []
    person_level_scores_by_part: dict[str, list[dict[str, Any]]] = {"upper": [], "lower": []}
    sample_event_scores = []
    sample_event_scores_by_part: dict[str, list[dict[str, Any]]] = {"upper": [], "lower": []}
    confusion: Counter[tuple[str, str, str]] = Counter()

    for person_id, label in sorted(labels.items()):
        events = events_by_person.get(person_id, [])
        manual_upper = _part_manual(label, "upper")
        manual_lower = _part_manual(label, "lower")
        person_prediction = {
            "upper": _majority_prediction(events, "upper"),
            "lower": _majority_prediction(events, "lower"),
        }
        person_scores = {
            "upper": _score_part(manual_upper, person_prediction["upper"]),
            "lower": _score_part(manual_lower, person_prediction["lower"]),
        }
        person_level_scores.extend(person_scores.values())
        person_level_scores_by_part["upper"].append(person_scores["upper"])
        person_level_scores_by_part["lower"].append(person_scores["lower"])

        sample_events = []
        for event_id in label.get("sample_event_ids", []):
            event = db.get_event(event_id)
            if not event:
                continue
            sample_score = {
                "event_id": event_id,
                "camera_id": event.get("camera_id"),
                "upper": _score_part(manual_upper, _event_part(event, "upper")),
                "lower": _score_part(manual_lower, _event_part(event, "lower")),
            }
            sample_event_scores.append(sample_score["upper"])
            sample_event_scores.append(sample_score["lower"])
            sample_event_scores_by_part["upper"].append(sample_score["upper"])
            sample_event_scores_by_part["lower"].append(sample_score["lower"])
            for prefix in ("upper", "lower"):
                score = sample_score[prefix]
                if score["color_evaluable"] and not score["color_correct"]:
                    confusion[(prefix, score["manual"]["color"], score["predicted"]["color"])] += 1
            sample_events.append(sample_score)

        for prefix in ("upper", "lower"):
            score = person_scores[prefix]
            if score["color_evaluable"] and not score["color_correct"]:
                confusion[(prefix, score["manual"]["color"], score["predicted"]["color"])] += 1

        person_results.append(
            {
                "person_id": person_id,
                "manual": {"upper": manual_upper, "lower": manual_lower, "note": label.get("note") or ""},
                "person_majority_prediction": person_prediction,
                "person_majority_scores": person_scores,
                "appearance_sessions": _session_predictions(person_id),
                "sample_events": sample_events,
            }
        )

    return {
        "schema_version": "manual_clothing_eval_v1",
        "generated_at": _now(),
        "label_path": str(label_path),
        "persons": len(labels),
        "core_clothing_parts": ["upper"] if not settings.enable_lower_clothing_core else ["upper", "lower"],
        "upper_only_core_metrics": _aggregate_scores(person_level_scores_by_part["upper"]),
        "upper_only_sample_event_metrics": _aggregate_scores(sample_event_scores_by_part["upper"]),
        "person_majority_metrics": _aggregate_scores(person_level_scores),
        "person_majority_metrics_by_part": {
            part: _aggregate_scores(scores)
            for part, scores in person_level_scores_by_part.items()
        },
        "sample_event_metrics": _aggregate_scores(sample_event_scores),
        "sample_event_metrics_by_part": {
            part: _aggregate_scores(scores)
            for part, scores in sample_event_scores_by_part.items()
        },
        "confusion_top": [
            {
                "part": part,
                "manual_color": manual_color,
                "predicted_color": predicted_color,
                "count": count,
            }
            for (part, manual_color, predicted_color), count in confusion.most_common()
        ],
        "results": person_results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate C1 clothing colors against manual person labels.")
    parser.add_argument("--labels", type=Path, default=LABEL_PATH)
    parser.add_argument("--out", type=Path, default=REPORT_PATH)
    args = parser.parse_args()

    report = evaluate(args.labels)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "persons",
                    "core_clothing_parts",
                    "upper_only_core_metrics",
                    "upper_only_sample_event_metrics",
                    "person_majority_metrics",
                    "person_majority_metrics_by_part",
                    "sample_event_metrics",
                    "sample_event_metrics_by_part",
                    "confusion_top",
                )
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print(args.out)


if __name__ == "__main__":
    main()
