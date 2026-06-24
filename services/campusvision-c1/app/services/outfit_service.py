from __future__ import annotations

from collections import Counter, defaultdict
from hashlib import sha1
import re
from typing import Any

import cv2
import numpy as np

from app.core.config import settings
from app.storage import db
from app.vision import person_analysis


OUTFIT_GROUPING_VERSION = "source_visual_outfit_group_v2"
SOURCE_MERGE_DISTANCE_THRESHOLD = 0.18
SOURCE_MERGE_DOMINANT_COLOR_RATIO = 0.70

_CHOKEPOINT_SOURCE_RE = re.compile(r"^(p\d+)[a-z]?_s\d+(?:_c\d+)?$")
_CAMERA_CHANNEL_SUFFIX_RE = re.compile(r"(?:[_-](?:camera|cam|c))\d+$")


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


def _source_segment_key(event: dict[str, Any]) -> str:
    camera_id = str(event.get("camera_id") or "").strip().lower()
    if not camera_id:
        return str(event.get("live_source_id") or event.get("video_id") or "unknown_source")

    chokepoint_match = _CHOKEPOINT_SOURCE_RE.match(camera_id)
    if chokepoint_match:
        return chokepoint_match.group(1)

    without_channel = _CAMERA_CHANNEL_SUFFIX_RE.sub("", camera_id).strip("_-")
    return without_channel or camera_id


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


def _group_centroid(group: list[dict[str, Any]]) -> np.ndarray | None:
    features = [item["feature"] for item in group if item.get("feature") is not None]
    if not features:
        return None
    centroid = np.stack(features).mean(axis=0)
    norm = float(np.linalg.norm(centroid))
    return centroid / norm if norm > 0.0 else centroid


def _dominant_color(group: list[dict[str, Any]]) -> tuple[str, float]:
    counts = Counter(str(item.get("model_upper_color") or "unknown") for item in group)
    if not counts:
        return "unknown", 0.0
    color, count = counts.most_common(1)[0]
    return color, float(count / max(1, sum(counts.values())))


def _event_upper_probabilities(event: dict[str, Any]) -> dict[str, float]:
    raw = (
        event.get("upper_color_probs")
        or event.get("normalized_upper_color_probs")
        or event.get("raw_upper_color_probs")
        or {}
    )
    if not isinstance(raw, dict):
        return {}

    out: dict[str, float] = {}
    for color in settings.clothing_color_labels:
        if color in {"unknown", "other"}:
            continue
        try:
            value = float(raw.get(color) or 0.0)
        except (TypeError, ValueError):
            value = 0.0
        if value > 0.0:
            out[color] = value
    total = sum(out.values())
    return {color: value / total for color, value in out.items()} if total > 0.0 else {}


def _aggregate_upper_probabilities(events: list[dict[str, Any]]) -> dict[str, float]:
    totals: Counter[str] = Counter()
    total_weight = 0.0
    for event in events:
        probabilities = _event_upper_probabilities(event)
        if not probabilities:
            continue
        confidence = max(0.05, min(1.0, float(event.get("upper_color_confidence") or 0.0)))
        for color, probability in probabilities.items():
            totals[color] += probability * confidence
        total_weight += confidence
    if total_weight <= 0.0:
        return {}
    return {color: float(value / total_weight) for color, value in totals.items()}


def _resolve_outfit_upper_color(
    color_counts: Counter[str],
    events: list[dict[str, Any]],
    *,
    average_confidence: float | None,
    max_striped_score: float,
) -> tuple[str, dict[str, Any]]:
    base_color = color_counts.most_common(1)[0][0] if color_counts else "unknown"
    if base_color == "unknown":
        return "unknown", {"action": "keep_base", "base_color": base_color}

    probabilities = _aggregate_upper_probabilities(events)
    confidence = float(average_confidence or 0.0)
    gray_probability = float(probabilities.get("gray", 0.0))
    white_probability = float(probabilities.get("white", 0.0))
    striped_probability = float(probabilities.get("striped", 0.0))

    black_count = int(color_counts.get("black", 0))
    blue_count = int(color_counts.get("blue", 0))
    gray_count = int(color_counts.get("gray", 0))
    purple_count = int(color_counts.get("purple", 0))
    striped_count = int(color_counts.get("striped", 0))
    white_count = int(color_counts.get("white", 0))

    if base_color == "purple" and black_count > 0 and black_count >= purple_count:
        return "black", {
            "action": "override_dark_purple_cast",
            "base_color": base_color,
            "black_count": black_count,
            "purple_count": purple_count,
        }

    if base_color == "gray" and white_count > 0 and white_count >= gray_count and len(color_counts) <= 3:
        return "white", {
            "action": "override_gray_white_tie",
            "base_color": base_color,
            "gray_count": gray_count,
            "white_count": white_count,
        }

    if base_color == "gray" and striped_count > 0 and max_striped_score >= 0.55:
        return "striped", {
            "action": "override_gray_high_stripe_evidence",
            "base_color": base_color,
            "max_striped_score": round(float(max_striped_score), 4),
            "striped_count": striped_count,
        }

    if (
        base_color == "striped"
        and gray_count > 0
        and max_striped_score <= 0.30
        and gray_probability >= striped_probability * 0.80
    ):
        return "gray", {
            "action": "override_low_stripe_gray_evidence",
            "base_color": base_color,
            "gray_probability": round(gray_probability, 6),
            "striped_probability": round(striped_probability, 6),
            "max_striped_score": round(float(max_striped_score), 4),
        }

    if (
        base_color == "blue"
        and purple_count > 0
        and blue_count > 0
        and purple_count >= blue_count
        and confidence < 0.35
    ):
        return "purple", {
            "action": "override_low_confidence_blue_purple_tie",
            "base_color": base_color,
            "blue_count": blue_count,
            "purple_count": purple_count,
            "average_confidence": round(confidence, 4),
        }

    if base_color == "gray" and confidence < 0.30 and white_probability >= 0.10:
        return "white", {
            "action": "override_low_confidence_gray_white_probability",
            "base_color": base_color,
            "average_confidence": round(confidence, 4),
            "white_probability": round(white_probability, 6),
        }

    return "unknown" if base_color == "unknown" else base_color, {
        "action": "keep_base",
        "base_color": base_color,
    }


def _source_segments_for_group(group: list[dict[str, Any]]) -> set[str]:
    return {
        str(item.get("source_segment") or "")
        for item in group
        if item.get("source_segment")
    }


def _should_merge_source_groups(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> bool:
    left_sources = _source_segments_for_group(left)
    right_sources = _source_segments_for_group(right)
    if left_sources & right_sources:
        return False

    left_color, left_ratio = _dominant_color(left)
    right_color, right_ratio = _dominant_color(right)
    if left_color == "unknown" or left_color != right_color:
        return False
    if left_ratio < SOURCE_MERGE_DOMINANT_COLOR_RATIO or right_ratio < SOURCE_MERGE_DOMINANT_COLOR_RATIO:
        return False

    left_centroid = _group_centroid(left)
    right_centroid = _group_centroid(right)
    if left_centroid is None or right_centroid is None:
        return False

    return _visual_distance(left_centroid, right_centroid) <= SOURCE_MERGE_DISTANCE_THRESHOLD


def _merge_source_compatible_groups(groups: list[list[dict[str, Any]]]) -> list[list[dict[str, Any]]]:
    if len(groups) <= 1:
        return groups

    parents = list(range(len(groups)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left: int, right: int) -> None:
        parents[find(right)] = find(left)

    for left_index in range(len(groups)):
        for right_index in range(left_index + 1, len(groups)):
            if _should_merge_source_groups(groups[left_index], groups[right_index]):
                union(left_index, right_index)

    merged: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for index, group in enumerate(groups):
        merged[find(index)].extend(group)

    return sorted(
        merged.values(),
        key=lambda group: _event_time_key(sorted((item["event"] for item in group), key=_event_time_key)[0]),
    )


def _outfit_id(person_id: str, events: list[dict[str, Any]]) -> str:
    raw = "|".join([person_id] + sorted(str(event.get("event_id") or "") for event in events))
    return "outfit_" + sha1(raw.encode("utf-8")).hexdigest()[:16]


def _group_summary(person_id: str, group: list[dict[str, Any]], group_index: int) -> dict[str, Any]:
    events = sorted((item["event"] for item in group), key=_event_time_key)
    color_counts = Counter(str(item.get("model_upper_color") or "unknown") for item in group)
    session_ids = sorted({str(event.get("appearance_session_id") or "") for event in events if event.get("appearance_session_id")})
    camera_ids = sorted({str(event.get("camera_id") or "") for event in events if event.get("camera_id")})
    source_segment_ids = sorted(_source_segments_for_group(group))
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
    average_confidence = sum(confidences) / len(confidences) if confidences else None
    max_striped_score = max(striped_scores) if striped_scores else 0.0
    model_upper_color, color_resolution = _resolve_outfit_upper_color(
        color_counts,
        events,
        average_confidence=average_confidence,
        max_striped_score=max_striped_score,
    )
    return {
        "outfit_id": _outfit_id(person_id, events),
        "person_id": person_id,
        "group_index": group_index,
        "event_count": len(events),
        "session_count": len(session_ids),
        "source_session_ids": session_ids,
        "source_segment_ids": source_segment_ids,
        "camera_ids": camera_ids,
        "start_time": events[0].get("start_time"),
        "end_time": events[-1].get("end_time"),
        "start_timestamp_sec": events[0].get("start_timestamp_sec"),
        "end_timestamp_sec": events[-1].get("end_timestamp_sec"),
        "model_upper_color": model_upper_color,
        "model_upper_color_base": color_resolution.get("base_color") or "unknown",
        "model_upper_color_counts": dict(color_counts.most_common()),
        "model_upper_color_confidence": round(average_confidence, 4) if average_confidence is not None else None,
        "model_upper_color_resolution": color_resolution,
        "feature_status_counts": dict(feature_status.most_common()),
        "max_striped_score": round(max_striped_score, 4),
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
        groups.extend(
            build_outfit_groups_for_events(
                current_person_id,
                events_by_person[current_person_id],
                distance_threshold=distance_threshold,
            )
        )

    return sorted(groups, key=lambda group: (group["person_id"], group["group_index"], group["outfit_id"]))


def build_outfit_groups_for_events(
    person_id: str,
    events: list[dict[str, Any]],
    *,
    distance_threshold: float = 0.42,
) -> list[dict[str, Any]]:
    items = []
    for event in sorted(events, key=_event_time_key):
        roi = _upper_roi_for_event(event)
        feature, diagnostics = _outfit_feature(roi, event.get("upper_color"))
        items.append(
            {
                "event": event,
                "feature": feature,
                "diagnostics": diagnostics,
                "model_upper_color": event.get("upper_color") or "unknown",
                "source_segment": _source_segment_key(event),
            }
        )

    clustered = []
    items_by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        items_by_source[str(item.get("source_segment") or "unknown_source")].append(item)

    for source_segment in sorted(items_by_source):
        source_items = items_by_source[source_segment]
        feature_items = [item for item in source_items if item.get("feature") is not None]
        missing_items = [item for item in source_items if item.get("feature") is None]
        source_groups = _cluster_feature_items(feature_items, distance_threshold)
        source_groups = _attach_missing_feature_items(source_groups, missing_items)
        clustered.extend(source_groups)

    clustered = _merge_source_compatible_groups(clustered)
    return [
        _group_summary(person_id, group, index)
        for index, group in enumerate(clustered, start=1)
    ]
