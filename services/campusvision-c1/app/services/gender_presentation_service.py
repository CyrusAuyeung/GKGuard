from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2

from app.core.config import settings
from app.storage import db
from app.vision import gender_presentation
from app.vision.person_analysis import clamp_bbox


PROFILE_SCHEMA_VERSION = "gender_presentation_profiles_v1"
PROFILE_SOURCE = "clip_zero_shot_person_profile"
PROFILE_PATH = settings.data_dir / "person_profiles" / "gender_presentation_profiles.json"
MANUAL_EVAL_LABEL_PATH = (
    settings.data_dir
    / "evals"
    / "manual_gender_presentation_labels"
    / "person_gender_presentation_labels.json"
)
TARGETS = {
    "person_accuracy": 0.85,
    "person_macro_f1": 0.80,
    "binary_masculine_feminine_accuracy": 0.90,
    "unknown_recall": 0.80,
    "unknown_forced_decision_rate": 0.10,
    "same_person_sample_consistency": 0.90,
    "cross_camera_consistency": 0.85,
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
    return {
        "schema_version": data.get("schema_version") or PROFILE_SCHEMA_VERSION,
        "source": data.get("source") or PROFILE_SOURCE,
        "model_version": data.get("model_version") or gender_presentation.MODEL_VERSION,
        "eval_data_used_for_training": False,
        "created_at": data.get("created_at"),
        "updated_at": data.get("updated_at"),
        "include_candidates": bool(data.get("include_candidates", True)),
        "sample_count_per_person": data.get("sample_count_per_person"),
        "profile_count": int(data.get("profile_count") or len(data.get("profiles") or {})),
        "profiles": data.get("profiles") if isinstance(data.get("profiles"), dict) else {},
        "evaluation": data.get("evaluation") if isinstance(data.get("evaluation"), dict) else {},
        "errors": data.get("errors") if isinstance(data.get("errors"), list) else [],
    }


def save_profiles(data: dict[str, Any]) -> None:
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    data["schema_version"] = PROFILE_SCHEMA_VERSION
    data["source"] = PROFILE_SOURCE
    data["model_version"] = gender_presentation.MODEL_VERSION
    data["eval_data_used_for_training"] = False
    PROFILE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def profile_for_person(person_id: str, profiles_data: dict[str, Any] | None = None) -> dict[str, Any] | None:
    data = profiles_data or load_profiles()
    profile = (data.get("profiles") or {}).get(person_id)
    return profile if isinstance(profile, dict) else None


def rebuild_profiles(
    *,
    include_candidates: bool = True,
    sample_count: int | None = None,
    person_ids: list[str] | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    requested_sample_count = int(sample_count or settings.gender_presentation_sample_count)
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
    errors = []
    for person in persons:
        person_id = str(person["person_id"])
        try:
            samples = collect_person_samples(person_id, sample_count=requested_sample_count)
            prediction = gender_presentation.predict_person_samples(samples)
            profiles[person_id] = _profile_payload(
                person,
                prediction,
                samples=samples,
            )
        except Exception as exc:
            errors.append({"person_id": person_id, "error": f"{type(exc).__name__}: {exc}"})
            profiles[person_id] = _profile_payload(
                person,
                {
                    "gender_presentation": "unknown",
                    "gender_presentation_label": gender_presentation.PRESENTATION_LABELS["unknown"],
                    "confidence": 0.0,
                    "score_margin": 0.0,
                    "evidence_quality": "poor",
                    "evidence_quality_label": "画质较差",
                    "sample_count": 0,
                    "sample_type_counts": {},
                    "scores": {},
                    "probabilities": {},
                    "sample_predictions": [],
                    "model_version": gender_presentation.MODEL_VERSION,
                    "uncertainty_reason": f"{type(exc).__name__}: {exc}",
                },
                samples=[],
            )

    data = {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "source": PROFILE_SOURCE,
        "model_version": gender_presentation.MODEL_VERSION,
        "eval_data_used_for_training": False,
        "created_at": started_at,
        "updated_at": utc_now(),
        "include_candidates": include_candidates,
        "sample_count_per_person": requested_sample_count,
        "profile_count": len(profiles),
        "profiles": profiles,
        "errors": errors,
    }
    data["evaluation"] = evaluate_profiles(data)
    save_profiles(data)
    return data


def evaluate_profiles(profiles_data: dict[str, Any] | None = None) -> dict[str, Any]:
    data = profiles_data or load_profiles()
    profiles = data.get("profiles") if isinstance(data.get("profiles"), dict) else {}
    manual = _load_manual_eval_labels()
    labels = manual.get("labels") if isinstance(manual.get("labels"), dict) else {}
    if not labels:
        return {
            "status": "not_available",
            "source": str(MANUAL_EVAL_LABEL_PATH),
            "eval_only": True,
            "note": "manual gender presentation labels are missing",
        }

    person_status = _person_status_lookup()
    rows = []
    skipped = Counter()
    for person_id, label in labels.items():
        if not isinstance(label, dict):
            skipped["invalid_label"] += 1
            continue
        if label.get("review_status") == "ignore":
            skipped["ignored"] += 1
            continue
        truth = str(label.get("gender_presentation") or "")
        if truth not in gender_presentation.PRESENTATION_LABELS:
            skipped["unsupported_truth"] += 1
            continue
        profile = profiles.get(person_id)
        if not isinstance(profile, dict):
            skipped["missing_profile"] += 1
            continue
        pred = str(profile.get("gender_presentation") or "unknown")
        if pred not in gender_presentation.PRESENTATION_LABELS:
            pred = "unknown"
        rows.append(
            {
                "person_id": person_id,
                "truth": truth,
                "pred": pred,
                "identity_status": person_status.get(person_id, "unknown"),
            }
        )

    if not rows:
        return {
            "status": "not_available",
            "source": str(MANUAL_EVAL_LABEL_PATH),
            "eval_only": True,
            "skipped": dict(skipped),
            "note": "no labeled person has a model profile",
        }

    classes = tuple(gender_presentation.PRESENTATION_LABELS)
    metrics = _classification_metrics(rows, classes)
    observed_classes = sorted({row["truth"] for row in rows})
    observed_macro_f1 = _macro_f1(rows, observed_classes)
    binary_rows = [
        row
        for row in rows
        if row["truth"] in {"masculine", "feminine"} and row["pred"] in {"masculine", "feminine"}
    ]
    unknown_rows = [row for row in rows if row["truth"] == "unknown"]
    neutral_rows = [row for row in rows if row["truth"] == "neutral"]
    consistency = _profile_consistency(profiles)
    breakdown = {
        status: _classification_metrics([row for row in rows if row["identity_status"] == status], classes)
        for status in sorted({row["identity_status"] for row in rows})
    }
    result = {
        "status": "ok",
        "source": str(MANUAL_EVAL_LABEL_PATH),
        "eval_only": True,
        "manual_labels": len(labels),
        "evaluated_persons": len(rows),
        "skipped": dict(skipped),
        "truth_counts": dict(Counter(row["truth"] for row in rows)),
        "prediction_counts": dict(Counter(row["pred"] for row in rows)),
        "observed_classes": observed_classes,
        "accuracy": metrics["accuracy"],
        "macro_f1_observed_classes": observed_macro_f1,
        "macro_f1_all_classes": metrics["macro_f1"],
        "per_class": metrics["per_class"],
        "confusion": metrics["confusion"],
        "binary_masculine_feminine_accuracy": _accuracy(binary_rows) if binary_rows else None,
        "neutral_recall": _recall(neutral_rows, "neutral") if neutral_rows else None,
        "unknown_recall": _recall(unknown_rows, "unknown") if unknown_rows else None,
        "unknown_forced_decision_rate": _unknown_forced_decision_rate(unknown_rows)
        if unknown_rows
        else None,
        "same_person_sample_consistency": consistency["same_person_sample_consistency"],
        "cross_camera_consistency": consistency["cross_camera_consistency"],
        "identity_status_breakdown": breakdown,
        "targets": _target_status(
            accuracy=metrics["accuracy"],
            macro_f1=observed_macro_f1,
            binary_accuracy=_accuracy(binary_rows) if binary_rows else None,
            unknown_recall=_recall(unknown_rows, "unknown") if unknown_rows else None,
            unknown_forced_decision_rate=_unknown_forced_decision_rate(unknown_rows)
            if unknown_rows
            else None,
            same_person_sample_consistency=consistency["same_person_sample_consistency"],
            cross_camera_consistency=consistency["cross_camera_consistency"],
        ),
        "limitations": _evaluation_limitations(rows),
        "updated_at": utc_now(),
    }
    return result


def collect_person_samples(person_id: str, *, sample_count: int) -> list[dict[str, Any]]:
    events = db.list_events(person_id=person_id, identified=True, limit=5000)
    selected_events = _sample_evenly(events, max(1, min(int(sample_count), 16)))
    samples: list[dict[str, Any]] = []
    for event in selected_events:
        samples.extend(_event_samples(event))
    return samples


def _event_samples(event: dict[str, Any]) -> list[dict[str, Any]]:
    observation = None
    observation_id = event.get("representative_observation_id")
    if observation_id:
        observation = db.get_person_observation(str(observation_id))
    face_id = event.get("representative_face_id") or (observation or {}).get("face_record_id")
    face_record = db.get_face_record(str(face_id)) if face_id else None
    frame_path = (
        (observation or {}).get("frame_path")
        or event.get("representative_frame_path")
        or (face_record or {}).get("frame_path")
    )
    image = cv2.imread(str(frame_path)) if frame_path else None
    if image is None:
        return []

    base = {
        "event_id": str(event.get("event_id") or ""),
        "observation_id": str((observation or {}).get("observation_id") or observation_id or ""),
        "camera_id": str(event.get("camera_id") or ""),
    }
    samples = []
    body_bbox = (observation or {}).get("person_bbox")
    if body_bbox:
        body_crop = _crop_bbox_image(image, body_bbox, padding_ratio=0.04)
        if body_crop is not None:
            samples.append(base | {"sample_type": "body", "sample_id": f"{base['event_id']}:body", "image_bgr": body_crop})
        context_crop = _crop_bbox_image(image, body_bbox, padding_ratio=0.35)
        if context_crop is not None:
            samples.append(base | {"sample_type": "frame", "sample_id": f"{base['event_id']}:frame", "image_bgr": context_crop})
    if face_record and face_record.get("bbox"):
        face_crop = _crop_bbox_image(image, face_record["bbox"], padding_ratio=0.20)
        if face_crop is not None:
            samples.append(base | {"sample_type": "face", "sample_id": f"{base['event_id']}:face", "image_bgr": face_crop})
    return samples


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
        "gender_presentation": prediction.get("gender_presentation") or "unknown",
        "gender_presentation_label": prediction.get("gender_presentation_label") or "无法判断",
        "confidence": prediction.get("confidence") or 0.0,
        "score_margin": prediction.get("score_margin") or 0.0,
        "evidence_quality": prediction.get("evidence_quality") or "poor",
        "evidence_quality_label": prediction.get("evidence_quality_label") or "画质较差",
        "sample_count": prediction.get("sample_count") or len(samples),
        "sample_type_counts": prediction.get("sample_type_counts") or {},
        "scores": prediction.get("scores") or {},
        "probabilities": prediction.get("probabilities") or {},
        "sample_predictions": prediction.get("sample_predictions") or [],
        "model_version": prediction.get("model_version") or gender_presentation.MODEL_VERSION,
        "uncertainty_reason": prediction.get("uncertainty_reason"),
        "updated_at": utc_now(),
    }


def _empty_profiles() -> dict[str, Any]:
    return {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "source": PROFILE_SOURCE,
        "model_version": gender_presentation.MODEL_VERSION,
        "eval_data_used_for_training": False,
        "created_at": None,
        "updated_at": None,
        "include_candidates": True,
        "sample_count_per_person": None,
        "profile_count": 0,
        "profiles": {},
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
        return {
            "accuracy": None,
            "macro_f1": None,
            "per_class": {},
            "confusion": {},
        }
    confusion_labels = tuple(dict.fromkeys([*classes, *(row["pred"] for row in rows), *(row["truth"] for row in rows)]))
    per_class = {}
    confusion = {truth: {pred: 0 for pred in confusion_labels} for truth in classes}
    for row in rows:
        if row["truth"] in confusion:
            confusion[row["truth"]][row["pred"]] += 1
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
    forced = sum(1 for row in rows if row["pred"] in {"masculine", "feminine", "neutral"})
    return round(forced / len(rows), 6)


def _profile_consistency(profiles: dict[str, Any]) -> dict[str, Any]:
    sample_consistency_values = []
    camera_consistency_values = []
    for profile in profiles.values():
        if not isinstance(profile, dict):
            continue
        sample_predictions = [
            item
            for item in profile.get("sample_predictions") or []
            if isinstance(item, dict) and item.get("gender_presentation")
        ]
        if sample_predictions:
            counts = Counter(str(item["gender_presentation"]) for item in sample_predictions)
            sample_consistency_values.append(max(counts.values()) / len(sample_predictions))

        by_camera: dict[str, list[str]] = defaultdict(list)
        for item in sample_predictions:
            camera_id = str(item.get("camera_id") or "")
            if camera_id:
                by_camera[camera_id].append(str(item.get("gender_presentation") or ""))
        camera_majorities = []
        for labels in by_camera.values():
            labels = [label for label in labels if label]
            if labels:
                camera_majorities.append(Counter(labels).most_common(1)[0][0])
        if len(camera_majorities) >= 2:
            camera_counts = Counter(camera_majorities)
            camera_consistency_values.append(max(camera_counts.values()) / len(camera_majorities))
    return {
        "same_person_sample_consistency": round(sum(sample_consistency_values) / len(sample_consistency_values), 6)
        if sample_consistency_values
        else None,
        "cross_camera_consistency": round(sum(camera_consistency_values) / len(camera_consistency_values), 6)
        if camera_consistency_values
        else None,
    }


def _target_status(**metrics: float | None) -> dict[str, Any]:
    status = {}
    mapping = {
        "person_accuracy": metrics.get("accuracy"),
        "person_macro_f1": metrics.get("macro_f1"),
        "binary_masculine_feminine_accuracy": metrics.get("binary_accuracy"),
        "unknown_recall": metrics.get("unknown_recall"),
        "same_person_sample_consistency": metrics.get("same_person_sample_consistency"),
        "cross_camera_consistency": metrics.get("cross_camera_consistency"),
    }
    for key, value in mapping.items():
        target = TARGETS[key]
        status[key] = {
            "value": value,
            "target": target,
            "passed": None if value is None else bool(value >= target),
        }
    forced_rate = metrics.get("unknown_forced_decision_rate")
    status["unknown_forced_decision_rate"] = {
        "value": forced_rate,
        "target_max": TARGETS["unknown_forced_decision_rate"],
        "passed": None if forced_rate is None else bool(forced_rate <= TARGETS["unknown_forced_decision_rate"]),
    }
    return status


def _evaluation_limitations(rows: list[dict[str, str]]) -> list[str]:
    truth_counts = Counter(row["truth"] for row in rows)
    limitations = []
    for label in ("neutral", "unknown"):
        if truth_counts.get(label, 0) == 0:
            limitations.append(f"manual eval set has no {label} samples; related recall target is not measurable yet")
    if len(rows) < 100:
        limitations.append("manual eval set has fewer than 100 persons; treat this as a stage-gate result")
    return limitations


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
    last_index = len(items) - 1
    indexes = {round(index * last_index / (count - 1)) for index in range(count)}
    return [items[index] for index in sorted(indexes)]
