from __future__ import annotations

from collections import Counter, defaultdict
from hashlib import sha1
from typing import Any

import cv2
import numpy as np

from app.core.config import settings
from app.storage import db
from app.vision import person_analysis


OUTFIT_GROUPING_VERSION = "visual_outfit_group_v1"


def _event_time_key(event: dict[str, Any]) -> tuple[str, float, str]:
    return (
        str(event.get("start_time") or event.get("end_time") or ""),
        float(event.get("start_timestamp_sec") or 0.0),
        str(event.get("event_id") or ""),
    )


def _event_image_url(event: dict[str, Any]) -> str:
    return (
        event.get("representative_body_crop_url")
        or event.get("representative_frame_url")
        or event.get("representative_face_crop_url")
        or ""
    )


def _upper_roi_for_event(event: dict[str, Any]) -> np.ndarray | None:
    observation_id = event.get("representative_observation_id")
    if not observation_id:
        return None
    observation = db.get_person_observation(observation_id)
    if not observation or not observation.get("person_bbox") or not observation.get("frame_path"):
        return None

    image = cv2.imread(observation["frame_path"])
    if image is None:
        return None

    roi = person_analysis._roi_from_ratio(
        image,
        observation["person_bbox"],
        settings.upper_roi_start_ratio,
        settings.upper_roi_end_ratio,
    )
    if roi is not None and roi.size > 0:
        return person_analysis._center_roi(roi)

    box = person_analysis.clamp_bbox(observation["person_bbox"], image.shape[1], image.shape[0])
    crop = image[box["y1"] : box["y2"], box["x1"] : box["x2"]]
    if crop.size <= 0:
        return None
    height = crop.shape[0]
    upper = crop[max(0, int(height * 0.18)) : max(1, int(height * 0.55)), :]
    return person_analysis._center_roi(upper) if upper.size > 0 else None


def _hist(values: np.ndarray, bins: int, value_range: tuple[int, int]) -> np.ndarray:
    hist, _ = np.histogram(values.reshape(-1), bins=bins, range=value_range)
    hist = hist.astype(np.float32)
    total = float(hist.sum())
    return hist / total if total > 0 else hist


def _outfit_feature(roi_bgr: np.ndarray | None, model_color: str | None) -> tuple[np.ndarray | None, dict[str, Any]]:
    if roi_bgr is None or roi_bgr.size == 0:
        return None, {"feature_status": "missing_roi"}

    roi = cv2.resize(roi_bgr, (48, 64), interpolation=cv2.INTER_AREA)
    lab = cv2.cvtColor(roi, cv2.COLOR_BGR2LAB)
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

    lab_l = lab[:, :, 0].astype(np.float32)
    lab_a = lab[:, :, 1].astype(np.float32)
    lab_b = lab[:, :, 2].astype(np.float32)
    hsv_h = hsv[:, :, 0].astype(np.float32)
    hsv_s = hsv[:, :, 1].astype(np.float32)
    hsv_v = hsv[:, :, 2].astype(np.float32)

    color_hist = np.concatenate(
        [
            _hist(lab_l, 10, (0, 256)),
            _hist(lab_a, 10, (0, 256)),
            _hist(lab_b, 10, (0, 256)),
            _hist(hsv_h[hsv_s >= 45], 12, (0, 180)) if np.any(hsv_s >= 45) else np.zeros(12, dtype=np.float32),
        ]
    )
    stats = np.array(
        [
            float(np.mean(lab_l)) / 255.0,
            float(np.std(lab_l)) / 128.0,
            float(np.mean(lab_a) - 128.0) / 128.0,
            float(np.mean(lab_b) - 128.0) / 128.0,
            float(np.mean(hsv_s)) / 255.0,
            float(np.std(hsv_s)) / 128.0,
            float(np.mean(hsv_v)) / 255.0,
            float(np.std(hsv_v)) / 128.0,
        ],
        dtype=np.float32,
    )

    tiny = cv2.resize(cv2.GaussianBlur(lab, (5, 5), 0), (8, 12), interpolation=cv2.INTER_AREA)
    tiny = tiny.astype(np.float32)
    tiny[:, :, 0] = (tiny[:, :, 0] - 128.0) / 128.0
    tiny[:, :, 1] = (tiny[:, :, 1] - 128.0) / 128.0
    tiny[:, :, 2] = (tiny[:, :, 2] - 128.0) / 128.0

    striped_score = person_analysis._striped_score(roi)
    one_hot = np.zeros(len(settings.clothing_color_labels), dtype=np.float32)
    if model_color in settings.clothing_color_labels:
        one_hot[settings.clothing_color_labels.index(str(model_color))] = 1.0

    feature = np.concatenate(
        [
            color_hist * 1.15,
            stats * 0.75,
            tiny.reshape(-1) * 0.18,
            np.array([striped_score], dtype=np.float32) * 1.35,
            one_hot * 0.18,
        ]
    ).astype(np.float32)
    norm = float(np.linalg.norm(feature))
    if norm <= 0.0:
        return None, {"feature_status": "zero_feature"}

    diagnostics = {
        "feature_status": "ok",
        "striped_score": round(float(striped_score), 4),
        "mean_l": round(float(np.mean(lab_l)), 3),
        "mean_s": round(float(np.mean(hsv_s)), 3),
    }
    return feature / norm, diagnostics


def _visual_distance(left: np.ndarray, right: np.ndarray) -> float:
    return float(1.0 - np.clip(np.dot(left, right), -1.0, 1.0))


def _cluster_feature_items(items: list[dict[str, Any]], distance_threshold: float) -> list[list[dict[str, Any]]]:
    groups: list[list[dict[str, Any]]] = []
    centroids: list[np.ndarray] = []

    for item in sorted(items, key=lambda entry: _event_time_key(entry["event"])):
        feature = item.get("feature")
        if feature is None:
            continue

        best_index = None
        best_distance = float("inf")
        for index, centroid in enumerate(centroids):
            if centroid.shape != feature.shape:
                continue
            distance = _visual_distance(feature, centroid)
            if distance < best_distance:
                best_distance = distance
                best_index = index

        threshold = distance_threshold
        color = item.get("model_upper_color")
        if best_index is not None:
            group_colors = {member.get("model_upper_color") for member in groups[best_index]}
            if color and color in group_colors and color != "unknown":
                threshold += 0.04

        if best_index is None or best_distance > threshold:
            groups.append([item])
            centroids.append(feature.copy())
            continue

        groups[best_index].append(item)
        stacked = np.stack([member["feature"] for member in groups[best_index] if member.get("feature") is not None])
        centroid = stacked.mean(axis=0)
        norm = float(np.linalg.norm(centroid))
        centroids[best_index] = centroid / norm if norm > 0.0 else centroid

    return groups


def _attach_missing_feature_items(
    groups: list[list[dict[str, Any]]],
    missing_items: list[dict[str, Any]],
) -> list[list[dict[str, Any]]]:
    if not missing_items:
        return groups

    if not groups:
        fallback: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in missing_items:
            session_id = str(item["event"].get("appearance_session_id") or item["event"].get("event_id") or "")
            fallback[session_id].append(item)
        return list(fallback.values())

    for item in sorted(missing_items, key=lambda entry: _event_time_key(entry["event"])):
        session_id = item["event"].get("appearance_session_id")
        candidates = [
            index
            for index, group in enumerate(groups)
            if session_id and any(member["event"].get("appearance_session_id") == session_id for member in group)
        ]
        if candidates:
            target_index = max(candidates, key=lambda index: len(groups[index]))
        else:
            target_index = max(range(len(groups)), key=lambda index: len(groups[index]))
        groups[target_index].append(item)

    return groups


def _outfit_id(person_id: str, events: list[dict[str, Any]]) -> str:
    raw = "|".join([person_id] + sorted(str(event.get("event_id") or "") for event in events))
    return "outfit_" + sha1(raw.encode("utf-8")).hexdigest()[:16]


def _group_summary(person_id: str, group: list[dict[str, Any]], group_index: int) -> dict[str, Any]:
    events = sorted((item["event"] for item in group), key=_event_time_key)
    color_counts = Counter(str(item.get("model_upper_color") or "unknown") for item in group)
    session_ids = sorted({str(event.get("appearance_session_id") or "") for event in events if event.get("appearance_session_id")})
    camera_ids = sorted({str(event.get("camera_id") or "") for event in events if event.get("camera_id")})
    confidences = [
        float(event.get("upper_color_confidence") or 0.0)
        for event in events
        if event.get("upper_color_confidence") is not None
    ]
    feature_status = Counter(str(item.get("diagnostics", {}).get("feature_status") or "unknown") for item in group)
    striped_scores = [
        float(item.get("diagnostics", {}).get("striped_score") or 0.0)
        for item in group
        if item.get("diagnostics", {}).get("feature_status") == "ok"
    ]
    return {
        "outfit_id": _outfit_id(person_id, events),
        "person_id": person_id,
        "group_index": group_index,
        "event_count": len(events),
        "session_count": len(session_ids),
        "source_session_ids": session_ids,
        "camera_ids": camera_ids,
        "start_time": events[0].get("start_time"),
        "end_time": events[-1].get("end_time"),
        "start_timestamp_sec": events[0].get("start_timestamp_sec"),
        "end_timestamp_sec": events[-1].get("end_timestamp_sec"),
        "model_upper_color": color_counts.most_common(1)[0][0] if color_counts else "unknown",
        "model_upper_color_counts": dict(color_counts.most_common()),
        "model_upper_color_confidence": round(sum(confidences) / len(confidences), 4) if confidences else None,
        "feature_status_counts": dict(feature_status.most_common()),
        "max_striped_score": round(max(striped_scores), 4) if striped_scores else 0.0,
        "events": events,
        "samples": [_sample_for_event(event) for event in events],
        "grouping_version": OUTFIT_GROUPING_VERSION,
    }


def _sample_for_event(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_id": event.get("event_id"),
        "observation_id": event.get("representative_observation_id"),
        "session_id": event.get("appearance_session_id"),
        "camera_id": event.get("camera_id"),
        "time_label": _time_label(event),
        "image_url": _event_image_url(event),
        "frame_url": event.get("representative_frame_url") or _event_image_url(event),
        "face_url": event.get("representative_face_crop_url") or "",
        "model_upper_color": event.get("upper_color") or "unknown",
        "model_upper_confidence": event.get("upper_color_confidence"),
    }


def _time_label(event: dict[str, Any]) -> str:
    if event.get("start_time") or event.get("end_time"):
        return str(event.get("start_time") or event.get("end_time") or "")
    start = event.get("start_timestamp_sec")
    end = event.get("end_timestamp_sec")
    if start is not None or end is not None:
        return f"{float(start or 0.0):.1f}s-{float(end or 0.0):.1f}s"
    return ""


def build_outfit_groups(
    *,
    person_id: str | None = None,
    distance_threshold: float = 0.42,
) -> list[dict[str, Any]]:
    events = db.list_events(person_id=person_id, identified=True, limit=10000)
    events_by_person: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        if event.get("person_id"):
            events_by_person[str(event["person_id"])].append(event)

    groups: list[dict[str, Any]] = []
    for current_person_id in sorted(events_by_person):
        items = []
        for event in sorted(events_by_person[current_person_id], key=_event_time_key):
            roi = _upper_roi_for_event(event)
            feature, diagnostics = _outfit_feature(roi, event.get("upper_color"))
            items.append(
                {
                    "event": event,
                    "feature": feature,
                    "diagnostics": diagnostics,
                    "model_upper_color": event.get("upper_color") or "unknown",
                }
            )

        feature_items = [item for item in items if item.get("feature") is not None]
        missing_items = [item for item in items if item.get("feature") is None]
        clustered = _cluster_feature_items(feature_items, distance_threshold)
        clustered = _attach_missing_feature_items(clustered, missing_items)
        for index, group in enumerate(clustered, start=1):
            groups.append(_group_summary(current_person_id, group, index))

    return sorted(groups, key=lambda group: (group["person_id"], group["group_index"], group["outfit_id"]))
