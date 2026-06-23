from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

import cv2

from app.core.config import settings
from app.storage import db
from app.vision import glasses_status
from app.vision.person_analysis import clamp_bbox


PROFILE_SCHEMA_VERSION = "glasses_status_profiles_v1"
PROFILE_SOURCE = "clip_zero_shot_person_profile"
PROFILE_PATH = settings.data_dir / "person_profiles" / "glasses_status_profiles.json"
MANUAL_EVAL_LABEL_PATH = (
    settings.data_dir
    / "evals"
    / "manual_person_glasses_labels"
    / "person_glasses_labels.json"
)
TARGETS = {
    "person_accuracy": 0.90,
    "person_macro_f1": 0.88,
    "glasses_precision": 0.92,
    "glasses_recall": 0.85,
    "no_glasses_precision": 0.92,
    "no_glasses_recall": 0.90,
    "unknown_recall": 0.80,
    "unknown_forced_decision_rate": 0.10,
    "identified_event_accuracy": 0.90,
    "same_person_event_consistency": 0.95,
}


def utc_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def load_profiles() -> dict[str, Any]:
    if not PROFILE_PATH.exists():
        return _empty_profiles()
    try:
        data = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return _empty_profiles()
    if not isinstance(data, dict):
        return _empty_profiles()
    profiles = data.get("profiles") if isinstance(data.get("profiles"), dict) else {}
    event_profiles = data.get("event_profiles") if isinstance(data.get("event_profiles"), dict) else {}
    return {
        "schema_version": data.get("schema_version") or PROFILE_SCHEMA_VERSION,
        "source": data.get("source") or PROFILE_SOURCE,
        "model_version": data.get("model_version") or glasses_status.MODEL_VERSION,
        "eval_data_used_for_training": False,
        "created_at": data.get("created_at"),
        "updated_at": data.get("updated_at"),
        "include_candidates": bool(data.get("include_candidates", True)),
        "sample_count_per_person": data.get("sample_count_per_person"),
        "profile_count": int(data.get("profile_count") or len(profiles)),
        "event_profile_count": int(data.get("event_profile_count") or len(event_profiles)),
        "profiles": profiles,
        "event_profiles": event_profiles,
        "evaluation": data.get("evaluation") if isinstance(data.get("evaluation"), dict) else {},
        "errors": data.get("errors") if isinstance(data.get("errors"), list) else [],
    }


def save_profiles(data: dict[str, Any]) -> None:
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    data["schema_version"] = PROFILE_SCHEMA_VERSION
    data["source"] = PROFILE_SOURCE
    data["model_version"] = glasses_status.MODEL_VERSION
    data["eval_data_used_for_training"] = False
    PROFILE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def profile_for_person(person_id: str, profiles_data: dict[str, Any] | None = None) -> dict[str, Any] | None:
    data = profiles_data or load_profiles()
    profile = (data.get("profiles") or {}).get(person_id)
    return profile if isinstance(profile, dict) else None


def profile_for_event(event_id: str, profiles_data: dict[str, Any] | None = None) -> dict[str, Any] | None:
    data = profiles_data or load_profiles()
    profile = (data.get("event_profiles") or {}).get(event_id)
    return profile if isinstance(profile, dict) else None


def rebuild_profiles(
    *,
    include_candidates: bool = True,
    sample_count: int | None = None,
    person_ids: list[str] | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    requested_sample_count = int(sample_count or settings.glasses_status_sample_count)
    requested_sample_count = max(1, min(requested_sample_count, 16))
    persons = db.list_persons()
    if person_ids:
        wanted = set(person_ids)
        persons = [person for person in persons if person["person_id"] in wanted]
    if not include_candidates:
        persons = [
            person
            for person in persons
            if int(person.get("face_count") or 0) >= int(settings.person_identity_stable_min_faces)
        ]
    if limit is not None:
        persons = persons[: max(1, int(limit))]

    started_at = utc_now()
    profiles = {}
    event_profiles = {}
    errors = []
    for person in persons:
        person_id = str(person["person_id"])
        try:
            samples = collect_person_samples(person_id, sample_count=requested_sample_count)
            prediction = glasses_status.predict_person_samples(samples)
            profile = _profile_payload(person, prediction, samples=samples)
            profiles[person_id] = profile
            for event_profile in _event_profiles_for_person(person_id, profile):
                event_profiles[event_profile["event_id"]] = event_profile
        except Exception as exc:
            errors.append({"person_id": person_id, "error": f"{type(exc).__name__}: {exc}"})
            profile = _profile_payload(
                person,
                {
                    "glasses_status": "unknown",
                    "glasses_status_label": glasses_status.STATUS_LABELS["unknown"],
                    "confidence": 0.0,
                    "score_margin": 0.0,
                    "evidence_quality": "poor",
                    "evidence_quality_label": "画质较差",
                    "sample_count": 0,
                    "sample_votes": {},
                    "sample_consistency": None,
                    "scores": {},
                    "probabilities": {},
                    "sample_predictions": [],
                    "model_version": glasses_status.MODEL_VERSION,
                    "uncertainty_reason": f"{type(exc).__name__}: {exc}",
                },
                samples=[],
            )
            profiles[person_id] = profile
            for event_profile in _event_profiles_for_person(person_id, profile):
                event_profiles[event_profile["event_id"]] = event_profile

    data = {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "source": PROFILE_SOURCE,
        "model_version": glasses_status.MODEL_VERSION,
        "eval_data_used_for_training": False,
        "created_at": started_at,
        "updated_at": utc_now(),
        "include_candidates": include_candidates,
        "sample_count_per_person": requested_sample_count,
        "profile_count": len(profiles),
        "event_profile_count": len(event_profiles),
        "profiles": profiles,
        "event_profiles": event_profiles,
        "errors": errors,
    }
    data["evaluation"] = evaluate_profiles(data)
    save_profiles(data)
    return data


def evaluate_profiles(profiles_data: dict[str, Any] | None = None) -> dict[str, Any]:
    data = profiles_data or load_profiles()
    profiles = data.get("profiles") if isinstance(data.get("profiles"), dict) else {}
    event_profiles = data.get("event_profiles") if isinstance(data.get("event_profiles"), dict) else {}
    manual = _load_manual_eval_labels()
    labels = manual.get("labels") if isinstance(manual.get("labels"), dict) else {}
    if not labels:
        return {
            "status": "not_available",
            "source": str(MANUAL_EVAL_LABEL_PATH),
            "eval_only": True,
            "note": "manual person glasses labels are missing",
        }

    person_status = _person_status_lookup()
    person_rows = []
    event_rows = []
    skipped = Counter()
    for person_id, label in labels.items():
        if not isinstance(label, dict):
            skipped["invalid_label"] += 1
            continue
        if label.get("review_status") == "ignore":
            skipped["ignored"] += 1
            continue
        truth = str(label.get("glasses_status") or "")
        if truth not in glasses_status.STATUS_LABELS:
            skipped["unsupported_truth"] += 1
            continue
        profile = profiles.get(person_id)
        if not isinstance(profile, dict):
            skipped["missing_profile"] += 1
            continue
        pred = _normalize_status(profile.get("glasses_status"))
        person_rows.append(
            {
                "person_id": person_id,
                "truth": truth,
                "pred": pred,
                "identity_status": person_status.get(person_id, "unknown"),
            }
        )

        for event_label in label.get("event_glasses_labels") or []:
            if not isinstance(event_label, dict):
                continue
            event_id = str(event_label.get("event_id") or "")
            if not event_id:
                continue
            event_profile = event_profiles.get(event_id)
            if not isinstance(event_profile, dict):
                skipped["missing_event_profile"] += 1
                continue
            event_rows.append(
                {
                    "event_id": event_id,
                    "person_id": person_id,
                    "truth": _normalize_status(event_label.get("glasses_status")),
                    "pred": _normalize_status(event_profile.get("glasses_status")),
                    "identity_status": person_status.get(person_id, "unknown"),
                }
            )

    if not person_rows:
        return {
            "status": "not_available",
            "source": str(MANUAL_EVAL_LABEL_PATH),
            "eval_only": True,
            "skipped": dict(skipped),
            "note": "no labeled person has a model profile",
        }

    classes = tuple(glasses_status.STATUS_LABELS)
    person_metrics = _classification_metrics(person_rows, classes)
    event_metrics = _classification_metrics(event_rows, classes) if event_rows else None
    observed_classes = sorted({row["truth"] for row in person_rows})
    observed_person_macro_f1 = _macro_f1(person_rows, observed_classes)
    unknown_rows = [row for row in person_rows if row["truth"] == "unknown"]
    consistency = _profile_consistency(profiles, event_profiles)
    coverage = _event_coverage()
    result = {
        "status": "ok",
        "source": str(MANUAL_EVAL_LABEL_PATH),
        "eval_only": True,
        "manual_person_labels": len(labels),
        "evaluated_persons": len(person_rows),
        "evaluated_identified_events": len(event_rows),
        "skipped": dict(skipped),
        "truth_counts": dict(Counter(row["truth"] for row in person_rows)),
        "prediction_counts": dict(Counter(row["pred"] for row in person_rows)),
        "person_accuracy": person_metrics["accuracy"],
        "person_macro_f1_observed_classes": observed_person_macro_f1,
        "person_macro_f1_all_classes": person_metrics["macro_f1"],
        "person_per_class": person_metrics["per_class"],
        "person_confusion": person_metrics["confusion"],
        "identified_event_accuracy": event_metrics["accuracy"] if event_metrics else None,
        "identified_event_macro_f1_observed_classes": _macro_f1(event_rows, observed_classes) if event_rows else None,
        "identified_event_per_class": event_metrics["per_class"] if event_metrics else {},
        "identified_event_confusion": event_metrics["confusion"] if event_metrics else {},
        "unknown_recall": _recall(unknown_rows, "unknown") if unknown_rows else None,
        "unknown_forced_decision_rate": _unknown_forced_decision_rate(unknown_rows)
        if unknown_rows
        else None,
        "raw_sample_consistency": consistency["raw_sample_consistency"],
        "same_person_event_consistency": consistency["same_person_event_consistency"],
        "identity_status_breakdown": {
            status: _classification_metrics(
                [row for row in person_rows if row["identity_status"] == status],
                classes,
            )
            for status in sorted({row["identity_status"] for row in person_rows})
        },
        "event_coverage": coverage,
        "targets": _target_status(
            person_metrics=person_metrics,
            observed_person_macro_f1=observed_person_macro_f1,
            identified_event_accuracy=event_metrics["accuracy"] if event_metrics else None,
            unknown_recall=_recall(unknown_rows, "unknown") if unknown_rows else None,
            unknown_forced_decision_rate=_unknown_forced_decision_rate(unknown_rows)
            if unknown_rows
            else None,
            same_person_event_consistency=consistency["same_person_event_consistency"],
        ),
        "limitations": _evaluation_limitations(person_rows, coverage),
        "updated_at": utc_now(),
    }
    return result


def collect_person_samples(person_id: str, *, sample_count: int) -> list[dict[str, Any]]:
    events = db.list_events(person_id=person_id, identified=True, limit=5000)
    selected_events = _sample_evenly(events, max(1, min(int(sample_count), 16)))
    samples = []
    for event in selected_events:
        sample = _event_representative_face_sample(event)
        if sample:
            samples.append(sample)
    return samples


def _event_representative_face_sample(event: dict[str, Any]) -> dict[str, Any] | None:
    face_id = event.get("representative_face_id")
    if not face_id:
        return None
    face_record = db.get_face_record(str(face_id))
    if not face_record or not face_record.get("bbox"):
        return None
    image = cv2.imread(str(face_record.get("frame_path") or ""))
    if image is None:
        return None
    crop = _crop_bbox_image(image, face_record["bbox"], padding_ratio=0.04)
    if crop is None:
        return None
    return {
        "sample_id": f"{event.get('event_id')}:face",
        "event_id": str(event.get("event_id") or ""),
        "observation_id": str(event.get("representative_observation_id") or ""),
        "camera_id": str(event.get("camera_id") or ""),
        "image_bgr": crop,
    }


def _event_profiles_for_person(person_id: str, profile: dict[str, Any]) -> list[dict[str, Any]]:
    event_profiles = []
    for event in db.list_events(person_id=person_id, identified=True, limit=5000):
        event_profiles.append(
            {
                "event_id": event["event_id"],
                "person_id": person_id,
                "camera_id": event.get("camera_id"),
                "video_id": event.get("video_id"),
                "start_time": event.get("start_time"),
                "end_time": event.get("end_time"),
                "start_timestamp_sec": event.get("start_timestamp_sec"),
                "end_timestamp_sec": event.get("end_timestamp_sec"),
                "representative_observation_id": event.get("representative_observation_id"),
                "representative_face_id": event.get("representative_face_id"),
                "glasses_status": profile.get("glasses_status") or "unknown",
                "glasses_status_label": profile.get("glasses_status_label") or "无法判断",
                "glasses_confidence": profile.get("confidence"),
                "glasses_evidence_quality": profile.get("evidence_quality"),
                "glasses_evidence_quality_label": profile.get("evidence_quality_label"),
                "glasses_model_version": profile.get("model_version") or glasses_status.MODEL_VERSION,
                "propagation_source": "model_person_level",
            }
        )
    return event_profiles


def _profile_payload(
    person: dict[str, Any],
    prediction: dict[str, Any],
    *,
    samples: list[dict[str, Any]],
) -> dict[str, Any]:
    status = (
        "stable"
        if int(person.get("face_count") or 0) >= int(settings.person_identity_stable_min_faces)
        else "candidate"
    )
    return {
        "person_id": person["person_id"],
        "identity_status": status,
        "glasses_status": prediction.get("glasses_status") or "unknown",
        "glasses_status_label": prediction.get("glasses_status_label") or "无法判断",
        "confidence": prediction.get("confidence") or 0.0,
        "score_margin": prediction.get("score_margin") or 0.0,
        "evidence_quality": prediction.get("evidence_quality") or "poor",
        "evidence_quality_label": prediction.get("evidence_quality_label") or "画质较差",
        "sample_count": prediction.get("sample_count") or len(samples),
        "sample_votes": prediction.get("sample_votes") or {},
        "sample_consistency": prediction.get("sample_consistency"),
        "scores": prediction.get("scores") or {},
        "probabilities": prediction.get("probabilities") or {},
        "sample_predictions": prediction.get("sample_predictions") or [],
        "model_version": prediction.get("model_version") or glasses_status.MODEL_VERSION,
        "uncertainty_reason": prediction.get("uncertainty_reason"),
        "updated_at": utc_now(),
    }


def _empty_profiles() -> dict[str, Any]:
    return {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "source": PROFILE_SOURCE,
        "model_version": glasses_status.MODEL_VERSION,
        "eval_data_used_for_training": False,
        "created_at": None,
        "updated_at": None,
        "include_candidates": True,
        "sample_count_per_person": None,
        "profile_count": 0,
        "event_profile_count": 0,
        "profiles": {},
        "event_profiles": {},
        "evaluation": {},
        "errors": [],
    }


def _load_manual_eval_labels() -> dict[str, Any]:
    if not MANUAL_EVAL_LABEL_PATH.exists():
        return {}
    try:
        data = json.loads(MANUAL_EVAL_LABEL_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _person_status_lookup() -> dict[str, str]:
    return {
        person["person_id"]: (
            "stable"
            if int(person.get("face_count") or 0) >= int(settings.person_identity_stable_min_faces)
            else "candidate"
        )
        for person in db.list_persons()
    }


def _classification_metrics(rows: list[dict[str, str]], classes: tuple[str, ...]) -> dict[str, Any]:
    if not rows:
        return {"accuracy": None, "macro_f1": None, "per_class": {}, "confusion": {}}
    confusion_labels = tuple(dict.fromkeys([*classes, *(row["pred"] for row in rows), *(row["truth"] for row in rows)]))
    confusion = {truth: {pred: 0 for pred in confusion_labels} for truth in classes}
    for row in rows:
        if row["truth"] in confusion:
            confusion[row["truth"]][row["pred"]] += 1

    per_class = {}
    for label in classes:
        tp = sum(1 for row in rows if row["truth"] == label and row["pred"] == label)
        fp = sum(1 for row in rows if row["truth"] != label and row["pred"] == label)
        fn = sum(1 for row in rows if row["truth"] == label and row["pred"] != label)
        support = sum(1 for row in rows if row["truth"] == label)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        per_class[label] = {
            "precision": round(precision, 6),
            "recall": round(recall, 6),
            "f1": round(f1, 6),
            "support": support,
        }
    return {
        "accuracy": round(_accuracy(rows), 6),
        "macro_f1": round(sum(item["f1"] for item in per_class.values()) / len(classes), 6),
        "per_class": per_class,
        "confusion": confusion,
    }


def _macro_f1(rows: list[dict[str, str]], labels: list[str]) -> float | None:
    if not rows or not labels:
        return None
    metrics = _classification_metrics(rows, tuple(labels))
    return metrics["macro_f1"]


def _accuracy(rows: list[dict[str, str]]) -> float:
    if not rows:
        return 0.0
    return round(sum(1 for row in rows if row["truth"] == row["pred"]) / len(rows), 6)


def _recall(rows: list[dict[str, str]], label: str) -> float:
    if not rows:
        return 0.0
    return round(sum(1 for row in rows if row["pred"] == label) / len(rows), 6)


def _unknown_forced_decision_rate(rows: list[dict[str, str]]) -> float:
    if not rows:
        return 0.0
    forced = sum(1 for row in rows if row["pred"] in {"glasses", "no_glasses"})
    return round(forced / len(rows), 6)


def _profile_consistency(profiles: dict[str, Any], event_profiles: dict[str, Any]) -> dict[str, Any]:
    raw_consistency_values = []
    for profile in profiles.values():
        if not isinstance(profile, dict):
            continue
        value = profile.get("sample_consistency")
        if value is not None:
            raw_consistency_values.append(float(value))

    by_person: dict[str, list[str]] = defaultdict(list)
    for event_profile in event_profiles.values():
        if isinstance(event_profile, dict) and event_profile.get("person_id"):
            by_person[str(event_profile["person_id"])].append(_normalize_status(event_profile.get("glasses_status")))
    person_event_consistency = []
    for statuses in by_person.values():
        if statuses:
            person_event_consistency.append(Counter(statuses).most_common(1)[0][1] / len(statuses))

    return {
        "raw_sample_consistency": round(sum(raw_consistency_values) / len(raw_consistency_values), 6)
        if raw_consistency_values
        else None,
        "same_person_event_consistency": round(sum(person_event_consistency) / len(person_event_consistency), 6)
        if person_event_consistency
        else None,
    }


def _event_coverage() -> dict[str, Any]:
    events = db.list_events(limit=5000)
    total = len(events)
    identified = sum(1 for event in events if event.get("person_id"))
    anonymous = total - identified
    return {
        "total_events": total,
        "identified_events": identified,
        "anonymous_events": anonymous,
        "identified_event_rate": round(identified / total, 6) if total else None,
        "note": "anonymous events cannot be evaluated from person-level manual labels",
    }


def _target_status(
    *,
    person_metrics: dict[str, Any],
    observed_person_macro_f1: float | None,
    identified_event_accuracy: float | None,
    unknown_recall: float | None,
    unknown_forced_decision_rate: float | None,
    same_person_event_consistency: float | None,
) -> dict[str, Any]:
    per_class = person_metrics.get("per_class") or {}
    values = {
        "person_accuracy": person_metrics.get("accuracy"),
        "person_macro_f1": observed_person_macro_f1,
        "glasses_precision": (per_class.get("glasses") or {}).get("precision"),
        "glasses_recall": (per_class.get("glasses") or {}).get("recall"),
        "no_glasses_precision": (per_class.get("no_glasses") or {}).get("precision"),
        "no_glasses_recall": (per_class.get("no_glasses") or {}).get("recall"),
        "unknown_recall": unknown_recall,
        "identified_event_accuracy": identified_event_accuracy,
        "same_person_event_consistency": same_person_event_consistency,
    }
    status = {
        key: {
            "value": value,
            "target": TARGETS[key],
            "passed": None if value is None else bool(value >= TARGETS[key]),
        }
        for key, value in values.items()
    }
    status["unknown_forced_decision_rate"] = {
        "value": unknown_forced_decision_rate,
        "target_max": TARGETS["unknown_forced_decision_rate"],
        "passed": None
        if unknown_forced_decision_rate is None
        else bool(unknown_forced_decision_rate <= TARGETS["unknown_forced_decision_rate"]),
    }
    return status


def _evaluation_limitations(rows: list[dict[str, str]], coverage: dict[str, Any]) -> list[str]:
    truth_counts = Counter(row["truth"] for row in rows)
    limitations = []
    if truth_counts.get("unknown", 0) == 0:
        limitations.append("manual eval set has no unknown samples; unknown recall is not measurable yet")
    if len(rows) < 100:
        limitations.append("manual eval set has fewer than 100 persons; treat this as a stage-gate result")
    if int(coverage.get("anonymous_events") or 0) > 0:
        limitations.append("anonymous events are reported as coverage only until they are linked to a person")
    return limitations


def _normalize_status(value: Any) -> str:
    text = str(value or "unknown")
    return text if text in glasses_status.STATUS_LABELS else "unknown"


def _crop_bbox_image(image, bbox: dict, *, padding_ratio: float = 0.04):
    if image is None or not bbox:
        return None
    height, width = image.shape[:2]
    raw_w = max(1.0, float(bbox.get("x2", 0) - bbox.get("x1", 0)))
    raw_h = max(1.0, float(bbox.get("y2", 0) - bbox.get("y1", 0)))
    padded = {
        **bbox,
        "x1": float(bbox["x1"]) - raw_w * padding_ratio,
        "y1": float(bbox["y1"]) - raw_h * padding_ratio,
        "x2": float(bbox["x2"]) + raw_w * padding_ratio,
        "y2": float(bbox["y2"]) + raw_h * padding_ratio,
    }
    box = clamp_bbox(padded, width, height)
    crop = image[box["y1"] : box["y2"], box["x1"] : box["x2"]]
    return crop if getattr(crop, "size", 0) > 0 else None


def _sample_evenly(items: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    if count <= 0 or not items:
        return []
    if len(items) <= count:
        return items
    if count == 1:
        return [items[len(items) // 2]]
    last_index = len(items) - 1
    indexes = {round(index * last_index / (count - 1)) for index in range(count)}
    return [items[index] for index in sorted(indexes)]
