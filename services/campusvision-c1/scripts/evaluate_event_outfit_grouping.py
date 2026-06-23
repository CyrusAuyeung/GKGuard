from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import settings  # noqa: E402
from app.services import outfit_service  # noqa: E402
from app.storage import db  # noqa: E402


LABEL_PATH = settings.data_dir / "evals" / "manual_event_outfit_groups" / "event_outfit_groups.json"
REPORT_PATH = settings.data_dir / "evals" / "manual_event_outfit_groups" / "event_outfit_group_eval.json"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_manual_assignments(label_path: Path) -> dict[str, dict[str, str]]:
    data = json.loads(label_path.read_text(encoding="utf-8"))
    labels = data.get("labels")
    if not isinstance(labels, dict):
        raise ValueError("manual event outfit labels must contain a labels object")

    out: dict[str, dict[str, str]] = {}
    for label in labels.values():
        if not isinstance(label, dict):
            continue
        person_id = str(label.get("person_id") or "")
        if not person_id:
            continue
        assignments: dict[str, str] = {}
        for assignment in label.get("manual_assignments") or []:
            if not isinstance(assignment, dict):
                continue
            event_id = str(assignment.get("event_id") or "")
            manual_group = str(assignment.get("manual_group") or "")
            if event_id and manual_group not in {"", "unassigned", "exclude"}:
                assignments[event_id] = manual_group
        if assignments:
            out[person_id] = assignments
    return out


def _pairwise_counts(y_true: dict[str, str], y_pred: dict[str, str]) -> dict[str, Any]:
    event_ids = sorted(set(y_true) & set(y_pred))
    true_positive = false_positive = false_negative = true_negative = 0
    for left, right in combinations(event_ids, 2):
        same_true = y_true[left] == y_true[right]
        same_pred = y_pred[left] == y_pred[right]
        if same_true and same_pred:
            true_positive += 1
        elif not same_true and same_pred:
            false_positive += 1
        elif same_true and not same_pred:
            false_negative += 1
        else:
            true_negative += 1

    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "event_count": len(event_ids),
        "pair_count": len(event_ids) * (len(event_ids) - 1) // 2,
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "true_negative": true_negative,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def _cluster_purity(y_true: dict[str, str], y_pred: dict[str, str]) -> dict[str, Any]:
    clusters: dict[str, Counter[str]] = defaultdict(Counter)
    for event_id in sorted(set(y_true) & set(y_pred)):
        clusters[y_pred[event_id]][y_true[event_id]] += 1

    correct = sum(counter.most_common(1)[0][1] for counter in clusters.values() if counter)
    total = sum(sum(counter.values()) for counter in clusters.values())
    mixed_clusters = sum(1 for counter in clusters.values() if len(counter) > 1)
    return {
        "purity_accuracy": correct / total if total else 0.0,
        "purity_correct": correct,
        "purity_total": total,
        "mixed_predicted_groups": mixed_clusters,
    }


def _predicted_assignments(person_id: str, event_ids: set[str], distance_threshold: float) -> dict[str, str]:
    events = [
        event
        for event in db.list_events(person_id=person_id, identified=True, limit=10000)
        if str(event.get("event_id") or "") in event_ids
    ]
    groups = outfit_service.build_outfit_groups_for_events(
        person_id,
        events,
        distance_threshold=distance_threshold,
    )

    assignments = {}
    for group in groups:
        group_id = str(group.get("outfit_id") or group.get("group_index") or "")
        for event in group.get("events") or []:
            event_id = str(event.get("event_id") or "")
            if event_id:
                assignments[event_id] = group_id
    return assignments


def evaluate(
    *,
    label_path: Path = LABEL_PATH,
    distance_threshold: float = 0.42,
) -> dict[str, Any]:
    db.init_db()
    manual_by_person = _load_manual_assignments(label_path)
    totals = Counter()
    person_results = []
    all_true: dict[str, str] = {}
    all_pred: dict[str, str] = {}
    predicted_group_count = 0

    for person_id, manual in sorted(manual_by_person.items()):
        predicted = _predicted_assignments(person_id, set(manual), distance_threshold)
        y_true = {
            event_id: f"{person_id}:{manual_group}"
            for event_id, manual_group in manual.items()
            if event_id in predicted
        }
        y_pred = {
            event_id: f"{person_id}:{predicted_group}"
            for event_id, predicted_group in predicted.items()
            if event_id in manual
        }
        counts = _pairwise_counts(y_true, y_pred)
        purity = _cluster_purity(y_true, y_pred)
        manual_counts = Counter(manual.values())
        predicted_counts = Counter(predicted.values())
        predicted_group_count += len(predicted_counts)

        for key in ("event_count", "pair_count", "true_positive", "false_positive", "false_negative", "true_negative"):
            totals[key] += counts[key]
        for event_id, value in y_true.items():
            all_true[f"{person_id}:{event_id}"] = value
        for event_id, value in y_pred.items():
            all_pred[f"{person_id}:{event_id}"] = value

        person_results.append(
            {
                "person_id": person_id,
                "manual_group_counts": dict(manual_counts.most_common()),
                "predicted_group_sizes": sorted(predicted_counts.values(), reverse=True),
                "metrics": {
                    **{
                        key: round(value, 6) if isinstance(value, float) else value
                        for key, value in counts.items()
                    },
                    **{
                        key: round(value, 6) if isinstance(value, float) else value
                        for key, value in purity.items()
                    },
                },
            }
        )

    precision = (
        totals["true_positive"] / (totals["true_positive"] + totals["false_positive"])
        if totals["true_positive"] + totals["false_positive"]
        else 0.0
    )
    recall = (
        totals["true_positive"] / (totals["true_positive"] + totals["false_negative"])
        if totals["true_positive"] + totals["false_negative"]
        else 0.0
    )
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    purity = _cluster_purity(all_true, all_pred)
    macro_f1 = (
        sum(float(row["metrics"]["f1"]) for row in person_results) / len(person_results)
        if person_results
        else 0.0
    )

    return {
        "schema_version": "event_outfit_group_eval_v1",
        "generated_at": _now(),
        "label_path": str(label_path),
        "eval_only": True,
        "grouping_version": outfit_service.OUTFIT_GROUPING_VERSION,
        "distance_threshold": distance_threshold,
        "persons": len(manual_by_person),
        "events": totals["event_count"],
        "manual_group_count": sum(len(set(groups.values())) for groups in manual_by_person.values()),
        "predicted_group_count": predicted_group_count,
        "pairwise": {
            "pair_count": totals["pair_count"],
            "true_positive": totals["true_positive"],
            "false_positive": totals["false_positive"],
            "false_negative": totals["false_negative"],
            "true_negative": totals["true_negative"],
            "precision": round(precision, 6),
            "recall": round(recall, 6),
            "f1": round(f1, 6),
            "macro_f1": round(macro_f1, 6),
        },
        "purity": {
            key: round(value, 6) if isinstance(value, float) else value
            for key, value in purity.items()
        },
        "worst_persons": sorted(
            person_results,
            key=lambda row: (float(row["metrics"]["f1"]), row["person_id"]),
        )[:10],
        "results": person_results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate event outfit grouping against manual eval-only labels.")
    parser.add_argument("--label-path", type=Path, default=LABEL_PATH)
    parser.add_argument("--output", type=Path, default=REPORT_PATH)
    parser.add_argument("--distance-threshold", type=float, default=0.42)
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()

    report = evaluate(label_path=args.label_path, distance_threshold=args.distance_threshold)
    if not args.no_write:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    pairwise = report["pairwise"]
    purity = report["purity"]
    print(
        "event_outfit_grouping",
        f"version={report['grouping_version']}",
        f"persons={report['persons']}",
        f"events={report['events']}",
        f"precision={pairwise['precision']:.4f}",
        f"recall={pairwise['recall']:.4f}",
        f"f1={pairwise['f1']:.4f}",
        f"macro_f1={pairwise['macro_f1']:.4f}",
        f"purity={purity['purity_accuracy']:.4f}",
    )
    if not args.no_write:
        print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
