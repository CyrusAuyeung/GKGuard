from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import settings  # noqa: E402
from app.storage import db  # noqa: E402
from app.vision import person_analysis, upper_color_calibrator  # noqa: E402


LABEL_PATH = settings.data_dir / "evals" / "manual_outfit_labels" / "outfit_labels.json"
MODEL_PATH = settings.upper_color_calibrator_path
REPORT_PATH = settings.data_dir / "evals" / "manual_outfit_labels" / "upper_color_calibrator_eval.json"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_manual_items(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    labels = data.get("labels", {})
    if not isinstance(labels, dict):
        raise ValueError("manual outfit labels must contain a labels object")

    items = []
    for label in labels.values():
        if not isinstance(label, dict):
            continue
        if not (label.get("source") == "manual_person_outfit_grouping" or label.get("manual_grouping")):
            continue
        person_id = str(label.get("person_id") or "")
        events_by_group: dict[str, list[str]] = defaultdict(list)
        for assignment in label.get("manual_split_assignments") or []:
            if not isinstance(assignment, dict):
                continue
            split_group = str(assignment.get("split_group") or "unassigned")
            event_id = str(assignment.get("event_id") or "")
            if split_group in {"unassigned", "exclude"} or not event_id:
                continue
            events_by_group[split_group].append(event_id)

        for split_group, group_label in (label.get("manual_split_group_labels") or {}).items():
            if not isinstance(group_label, dict):
                continue
            color = str(group_label.get("upper_color") or "unknown")
            if color == "unknown":
                continue
            for event_id in events_by_group.get(str(split_group), []):
                items.append(
                    {
                        "person_id": person_id,
                        "split_group": str(split_group),
                        "event_id": event_id,
                        "upper_color": color,
                    }
                )
    return items


def _event_upper_roi(event_id: str, *, allow_face_estimated: bool = True) -> tuple[np.ndarray | None, str]:
    event = db.get_event(event_id)
    if not event:
        return None, "event_missing"

    observation_id = event.get("representative_observation_id")
    observation = db.get_person_observation(observation_id) if observation_id else None
    image = None
    body_box = None
    source = "db_body"
    if observation and observation.get("frame_path"):
        image = cv2.imread(observation["frame_path"])
        body_box = observation.get("person_bbox")

    if image is None and event.get("representative_frame_path"):
        image = cv2.imread(event["representative_frame_path"])
    if image is None:
        return None, "frame_missing"

    if not body_box and allow_face_estimated:
        face_id = event.get("representative_face_id")
        face_record = db.get_face_record(face_id) if face_id else None
        if face_record and face_record.get("bbox"):
            body_box = person_analysis.estimate_body_bbox_from_face(
                face_record["bbox"],
                image.shape[1],
                image.shape[0],
            )
            source = "face_estimated_body"

    if not body_box:
        return None, "body_missing"

    roi = person_analysis._roi_from_ratio(
        image,
        body_box,
        settings.upper_roi_start_ratio,
        settings.upper_roi_end_ratio,
    )
    if roi is None or roi.size == 0:
        return None, "roi_missing"
    return person_analysis._center_roi(roi), source


def _current_event_prediction(event_id: str) -> str:
    event = db.get_event(event_id)
    if not event:
        return "unknown"
    return event.get("normalized_upper_color") or event.get("upper_color") or "unknown"


def _group_metrics(items: list[dict[str, Any]], predicted_by_event: dict[str, str]) -> dict[str, Any]:
    grouped: dict[tuple[str, str], list[str]] = defaultdict(list)
    truth: dict[tuple[str, str], str] = {}
    for item in items:
        key = (item["person_id"], item["split_group"])
        grouped[key].append(predicted_by_event.get(item["event_id"], "unknown"))
        truth[key] = item["upper_color"]

    correct = 0
    confusion: Counter[tuple[str, str]] = Counter()
    per_group = []
    for key, predictions in sorted(grouped.items()):
        predicted = Counter(predictions).most_common(1)[0][0] if predictions else "unknown"
        manual = truth[key]
        is_correct = predicted == manual
        correct += 1 if is_correct else 0
        if not is_correct:
            confusion[(manual, predicted)] += 1
        per_group.append(
            {
                "person_id": key[0],
                "split_group": key[1],
                "manual_upper_color": manual,
                "predicted_upper_color": predicted,
                "correct": is_correct,
                "prediction_counts": dict(Counter(predictions).most_common()),
            }
        )

    total = len(grouped)
    return {
        "total": total,
        "correct": correct,
        "accuracy": round(correct / total, 4) if total else None,
        "confusion_top": [
            {"manual_color": manual, "predicted_color": predicted, "count": count}
            for (manual, predicted), count in confusion.most_common()
        ],
        "per_group": per_group,
    }


def _event_metrics(items: list[dict[str, Any]], predicted_by_event: dict[str, str]) -> dict[str, Any]:
    correct = 0
    confusion: Counter[tuple[str, str]] = Counter()
    for item in items:
        predicted = predicted_by_event.get(item["event_id"], "unknown")
        manual = item["upper_color"]
        is_correct = predicted == manual
        correct += 1 if is_correct else 0
        if not is_correct:
            confusion[(manual, predicted)] += 1
    total = len(items)
    return {
        "total": total,
        "correct": correct,
        "accuracy": round(correct / total, 4) if total else None,
        "confusion_top": [
            {"manual_color": manual, "predicted_color": predicted, "count": count}
            for (manual, predicted), count in confusion.most_common()
        ],
    }


def _fit_model(records: list[dict[str, Any]], *, k: int) -> dict[str, Any]:
    matrix = np.vstack([record["features"] for record in records]).astype(np.float32)
    feature_mean = matrix.mean(axis=0)
    feature_scale = matrix.std(axis=0)
    feature_scale = np.where(feature_scale <= 1e-6, 1.0, feature_scale)
    normalized = (matrix - feature_mean) / feature_scale
    return {
        "model_version": upper_color_calibrator.MODEL_VERSION,
        "created_at": _now(),
        "labels": [record["upper_color"] for record in records],
        "feature_vectors": normalized.round(6).tolist(),
        "feature_mean": feature_mean.round(6).tolist(),
        "feature_scale": feature_scale.round(6).tolist(),
        "k": int(k),
        "training_sample_count": len(records),
        "training_color_counts": dict(Counter(record["upper_color"] for record in records).most_common()),
        "roi_source_counts": dict(Counter(record["roi_source"] for record in records).most_common()),
    }


def _predict_records(records: list[dict[str, Any]], model: dict[str, Any], *, k: int) -> dict[str, str]:
    out = {}
    for record in records:
        normalized = upper_color_calibrator.normalize_features(record["features"], model)
        query_model = {
            **model,
            "_feature_vectors_np": np.asarray(model["feature_vectors"], dtype=np.float32),
            "_labels_np": np.asarray(model["labels"]),
        }
        distances = np.linalg.norm(query_model["_feature_vectors_np"] - normalized, axis=1)
        order = np.argsort(distances)[: max(1, min(k, len(distances)))]
        votes: Counter[str] = Counter()
        for index in order:
            votes[str(query_model["_labels_np"][index])] += 1.0 / (float(distances[index]) + 1e-6)
        out[record["event_id"]] = votes.most_common(1)[0][0]
    return out


def _leave_one_person_predictions(records: list[dict[str, Any]], *, k: int) -> dict[str, str]:
    out = {}
    people = sorted({record["person_id"] for record in records})
    for person_id in people:
        train_records = [record for record in records if record["person_id"] != person_id]
        test_records = [record for record in records if record["person_id"] == person_id]
        if len({record["upper_color"] for record in train_records}) < 2:
            continue
        model = _fit_model(train_records, k=k)
        out.update(_predict_records(test_records, model, k=k))
    return out


def train_and_evaluate(
    *,
    label_path: Path,
    model_path: Path,
    report_path: Path,
    k: int,
    allow_face_estimated: bool,
    write_model: bool,
) -> dict[str, Any]:
    db.init_db()
    items = _load_manual_items(label_path)
    records = []
    missing: Counter[str] = Counter()
    for item in items:
        roi, source = _event_upper_roi(item["event_id"], allow_face_estimated=allow_face_estimated)
        if roi is None:
            missing[source] += 1
            continue
        records.append(
            {
                **item,
                "roi_source": source,
                "features": upper_color_calibrator.extract_features(roi),
            }
        )

    if not records:
        raise ValueError("no trainable manual outfit samples found")

    model = _fit_model(records, k=k)
    current_predictions = {item["event_id"]: _current_event_prediction(item["event_id"]) for item in items}
    calibrated_predictions = _predict_records(records, model, k=k)
    loo_predictions = _leave_one_person_predictions(records, k=k)
    for item in items:
        calibrated_predictions.setdefault(item["event_id"], "unknown")
        loo_predictions.setdefault(item["event_id"], "unknown")

    report = {
        "schema_version": "upper_color_calibrator_eval_v1",
        "generated_at": _now(),
        "label_path": str(label_path),
        "model_path": str(model_path),
        "allow_face_estimated": allow_face_estimated,
        "k": k,
        "manual_event_count": len(items),
        "trainable_event_count": len(records),
        "missing_roi_counts": dict(missing.most_common()),
        "training_color_counts": model["training_color_counts"],
        "roi_source_counts": model["roi_source_counts"],
        "current_event_metrics": _event_metrics(items, current_predictions),
        "current_group_metrics": _group_metrics(items, current_predictions),
        "calibrated_in_sample_event_metrics": _event_metrics(items, calibrated_predictions),
        "calibrated_in_sample_group_metrics": _group_metrics(items, calibrated_predictions),
        "leave_one_person_event_metrics": _event_metrics(items, loo_predictions),
        "leave_one_person_group_metrics": _group_metrics(items, loo_predictions),
    }

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    if write_model:
        model_path.parent.mkdir(parents=True, exist_ok=True)
        model_path.write_text(json.dumps(model, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        upper_color_calibrator.clear_model_cache()
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Train upper-color calibrator from manual outfit labels.")
    parser.add_argument("--labels", type=Path, default=LABEL_PATH)
    parser.add_argument("--model-out", type=Path, default=MODEL_PATH)
    parser.add_argument("--report-out", type=Path, default=REPORT_PATH)
    parser.add_argument("--k", type=int, default=settings.upper_color_calibrator_k)
    parser.add_argument("--no-face-estimated", action="store_true")
    parser.add_argument("--no-write-model", action="store_true")
    args = parser.parse_args()

    report = train_and_evaluate(
        label_path=args.labels,
        model_path=args.model_out,
        report_path=args.report_out,
        k=max(1, int(args.k)),
        allow_face_estimated=not args.no_face_estimated,
        write_model=not args.no_write_model,
    )
    summary = {
        "manual_event_count": report["manual_event_count"],
        "trainable_event_count": report["trainable_event_count"],
        "missing_roi_counts": report["missing_roi_counts"],
        "current_event_accuracy": report["current_event_metrics"]["accuracy"],
        "current_group_accuracy": report["current_group_metrics"]["accuracy"],
        "calibrated_in_sample_event_accuracy": report["calibrated_in_sample_event_metrics"]["accuracy"],
        "calibrated_in_sample_group_accuracy": report["calibrated_in_sample_group_metrics"]["accuracy"],
        "leave_one_person_event_accuracy": report["leave_one_person_event_metrics"]["accuracy"],
        "leave_one_person_group_accuracy": report["leave_one_person_group_metrics"]["accuracy"],
        "model_path": str(args.model_out),
        "report_path": str(args.report_out),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
