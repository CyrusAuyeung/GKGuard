from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

import numpy as np

from app.core.config import settings
from app.storage import db
from app.vision import person_analysis


ESTIMATED_BODY_MODEL_VERSION = "face_estimated_body_v1"


@dataclass
class _UpperColorCacheEntry:
    body: dict
    timestamp_sec: float
    prediction: person_analysis.RegionResult


def _bbox_iou(left: dict, right: dict) -> float:
    x1 = max(float(left.get("x1", 0)), float(right.get("x1", 0)))
    y1 = max(float(left.get("y1", 0)), float(right.get("y1", 0)))
    x2 = min(float(left.get("x2", 0)), float(right.get("x2", 0)))
    y2 = min(float(left.get("y2", 0)), float(right.get("y2", 0)))
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    left_area = person_analysis.bbox_area(left)
    right_area = person_analysis.bbox_area(right)
    union = left_area + right_area - inter
    return inter / union if union > 0.0 else 0.0


def _same_body_source(left: dict, right: dict) -> bool:
    return bool(left.get("estimated_from_face")) == bool(right.get("estimated_from_face")) and str(
        left.get("detector") or ""
    ) == str(right.get("detector") or "")


class UpperColorTemporalCache:
    def __init__(
        self,
        *,
        max_age_sec: float | None = None,
        iou_threshold: float | None = None,
    ) -> None:
        self.max_age_sec = (
            float(settings.upper_color_temporal_cache_max_age_sec)
            if max_age_sec is None
            else float(max_age_sec)
        )
        self.iou_threshold = (
            float(settings.upper_color_temporal_cache_iou_threshold)
            if iou_threshold is None
            else float(iou_threshold)
        )
        self._entries: list[_UpperColorCacheEntry] = []

    def _prune(self, timestamp_sec: float) -> None:
        self._entries = [
            entry
            for entry in self._entries
            if 0.0 <= timestamp_sec - entry.timestamp_sec <= self.max_age_sec
        ]

    def get(
        self,
        body: dict,
        *,
        timestamp_sec: float,
        used_entry_indexes: set[int],
    ) -> person_analysis.RegionResult | None:
        self._prune(timestamp_sec)
        best: tuple[float, int, _UpperColorCacheEntry] | None = None
        for index, entry in enumerate(self._entries):
            if index in used_entry_indexes:
                continue
            if not _same_body_source(body, entry.body):
                continue
            age = timestamp_sec - entry.timestamp_sec
            if age < 0.0 or age > self.max_age_sec:
                continue
            iou = _bbox_iou(body, entry.body)
            if iou < self.iou_threshold:
                continue
            if best is None or iou > best[0]:
                best = (iou, index, entry)
        if best is None:
            return None
        used_entry_indexes.add(best[1])
        return best[2].prediction

    def put(self, body: dict, *, timestamp_sec: float, prediction: person_analysis.RegionResult) -> None:
        self._prune(timestamp_sec)
        self._entries.append(
            _UpperColorCacheEntry(
                body=dict(body),
                timestamp_sec=timestamp_sec,
                prediction=prediction,
            )
        )


def _unknown_clothing() -> dict[str, Any]:
    return {
        "upper_color": "unknown",
        "upper_color_confidence": None,
        "upper_visible": False,
        "upper_valid_pixel_ratio": None,
        "lower_color": "unknown",
        "lower_color_confidence": None,
        "lower_visible": False,
        "lower_valid_pixel_ratio": None,
    }


def _estimated_body_from_face_if_visible(frame: np.ndarray, face: dict) -> dict | None:
    height, width = frame.shape[:2]
    face_h = max(1.0, float(face.get("y2", 0) - face.get("y1", 0)))
    space_below_face = float(height) - float(face.get("y2", 0))

    # Do not invent clothing for true face-only close-ups or heavily cropped faces.
    # Hallway surveillance faces usually have enough pixels below the face for
    # at least a shoulder/torso estimate; close-up query-like crops do not.
    if space_below_face < face_h * 1.6:
        return None

    return person_analysis.estimate_body_bbox_from_face(face, width, height)


def _body_observation_payload(
    *,
    frame: np.ndarray,
    body: dict,
    face: dict | None,
    upper_prediction: person_analysis.RegionResult | None = None,
) -> dict[str, Any]:
    visibility = person_analysis.classify_body_visibility(frame, body, face)
    try:
        clothing = person_analysis.analyze_clothing(
            frame,
            body,
            visibility,
            upper_prediction=upper_prediction,
        )
    except Exception:
        clothing = _unknown_clothing()
    return {
        "body_visibility": visibility,
        "person_bbox": body,
        "person_detection_confidence": body.get("score"),
        **clothing,
    }


def _batch_upper_predictions(
    frame: np.ndarray,
    bodies: list[dict],
    *,
    timestamp_sec: float | None = None,
    cache: UpperColorTemporalCache | None = None,
) -> dict[int, person_analysis.RegionResult]:
    if not bodies or not settings.enable_clothing_detection or not settings.enable_upper_clothing_detection:
        return {}
    if settings.upper_color_backend != "clip_schp":
        return {}

    unique_bodies = []
    seen: set[int] = set()
    for body in bodies:
        body_key = id(body)
        if body_key in seen:
            continue
        seen.add(body_key)
        unique_bodies.append(body)

    results: dict[int, person_analysis.RegionResult] = {}
    uncached_bodies: list[dict] = []
    used_cache_entries: set[int] = set()
    if cache is not None and timestamp_sec is not None and settings.enable_upper_color_temporal_cache:
        for body in unique_bodies:
            prediction = cache.get(
                body,
                timestamp_sec=float(timestamp_sec),
                used_entry_indexes=used_cache_entries,
            )
            if prediction is None:
                uncached_bodies.append(body)
            else:
                results[id(body)] = prediction
    else:
        uncached_bodies = unique_bodies

    if not uncached_bodies:
        return results

    try:
        predictions = person_analysis._classify_upper_colors_with_backend(frame, uncached_bodies)
    except Exception:
        return results

    for body, prediction in zip(uncached_bodies, predictions):
        if prediction is None:
            continue
        results[id(body)] = prediction
        if cache is not None and timestamp_sec is not None and settings.enable_upper_color_temporal_cache:
            cache.put(body, timestamp_sec=float(timestamp_sec), prediction=prediction)
    return results


def create_frame_observations(
    *,
    frame: np.ndarray,
    video_id: str,
    camera_id: str,
    frame_path: str,
    video_timestamp_sec: float,
    captured_at: str | None,
    frame_index: int | None,
    faces: list[dict],
    bodies: list[dict],
    live_source_id: str | None = None,
    upper_color_cache: UpperColorTemporalCache | None = None,
) -> list[dict]:
    match_result = person_analysis.match_faces_to_bodies(faces, bodies)
    estimated_body_by_face_index: dict[int, dict] = {}
    upper_prediction_bodies: list[dict] = [
        bodies[pair["body_index"]]
        for pair in match_result["pairs"]
    ]
    for face_index in match_result["unmatched_face_indices"]:
        estimated_body = _estimated_body_from_face_if_visible(frame, faces[face_index])
        if estimated_body is not None:
            estimated_body_by_face_index[face_index] = estimated_body
            upper_prediction_bodies.append(estimated_body)
    for body_index in match_result["unmatched_body_indices"]:
        upper_prediction_bodies.append(bodies[body_index])
    upper_predictions = _batch_upper_predictions(
        frame,
        upper_prediction_bodies,
        timestamp_sec=video_timestamp_sec,
        cache=upper_color_cache,
    )
    observations = []

    for pair in match_result["pairs"]:
        face = faces[pair["face_index"]]
        body = bodies[pair["body_index"]]
        body_payload = _body_observation_payload(
            frame=frame,
            body=body,
            face=face,
            upper_prediction=upper_predictions.get(id(body)),
        )
        observation = db.add_person_observation(
            {
                "observation_id": "obs_" + uuid.uuid4().hex,
                "camera_id": camera_id,
                "video_id": video_id,
                "live_source_id": live_source_id,
                "frame_index": frame_index,
                "video_timestamp_sec": video_timestamp_sec,
                "captured_at": captured_at,
                "frame_path": frame_path,
                "track_id": None,
                "observation_type": "face_and_body",
                "face_record_id": face["face_id"],
                "person_id": None,
                "clothing_model_version": settings.clothing_model_version,
                "body_model_version": settings.body_model_version,
                **body_payload,
            }
        )
        db.update_face_record_observation(face["face_id"], observation["observation_id"])
        observations.append(observation)

    for face_index in match_result["unmatched_face_indices"]:
        face = faces[face_index]
        estimated_body = estimated_body_by_face_index.get(face_index)
        body_payload = None
        body_model_version = settings.body_model_version
        observation_type = "face_only"
        if estimated_body is not None:
            body_payload = _body_observation_payload(
                frame=frame,
                body=estimated_body,
                face=face,
                upper_prediction=upper_predictions.get(id(estimated_body)),
            )
            body_model_version = ESTIMATED_BODY_MODEL_VERSION
            observation_type = "face_and_body"

        observation = db.add_person_observation(
            {
                "observation_id": "obs_" + uuid.uuid4().hex,
                "camera_id": camera_id,
                "video_id": video_id,
                "live_source_id": live_source_id,
                "frame_index": frame_index,
                "video_timestamp_sec": video_timestamp_sec,
                "captured_at": captured_at,
                "frame_path": frame_path,
                "track_id": None,
                "observation_type": observation_type,
                "face_record_id": face["face_id"],
                "person_id": None,
                "clothing_model_version": settings.clothing_model_version,
                "body_model_version": body_model_version,
                **(
                    body_payload
                    if body_payload is not None
                    else {
                        "body_visibility": "face_only",
                        "person_bbox": None,
                        "person_detection_confidence": None,
                        **_unknown_clothing(),
                    }
                ),
            }
        )
        db.update_face_record_observation(face["face_id"], observation["observation_id"])
        observations.append(observation)

    for body_index in match_result["unmatched_body_indices"]:
        body = bodies[body_index]
        body_payload = _body_observation_payload(
            frame=frame,
            body=body,
            face=None,
            upper_prediction=upper_predictions.get(id(body)),
        )
        observation = db.add_person_observation(
            {
                "observation_id": "obs_" + uuid.uuid4().hex,
                "camera_id": camera_id,
                "video_id": video_id,
                "live_source_id": live_source_id,
                "frame_index": frame_index,
                "video_timestamp_sec": video_timestamp_sec,
                "captured_at": captured_at,
                "frame_path": frame_path,
                "track_id": None,
                "observation_type": "body_only",
                "face_record_id": None,
                "person_id": None,
                "clothing_model_version": settings.clothing_model_version,
                "body_model_version": settings.body_model_version,
                **body_payload,
            }
        )
        observations.append(observation)

    return observations
