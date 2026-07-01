from __future__ import annotations

import uuid
from dataclasses import dataclass
from math import hypot
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
    face_embedding: list[float] | None = None


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


def _bbox_size(box: dict) -> tuple[float, float]:
    return (
        max(1.0, float(box.get("x2", 0) - box.get("x1", 0))),
        max(1.0, float(box.get("y2", 0) - box.get("y1", 0))),
    )


def _bbox_center(box: dict) -> tuple[float, float]:
    return (
        (float(box.get("x1", 0)) + float(box.get("x2", 0))) / 2.0,
        (float(box.get("y1", 0)) + float(box.get("y2", 0))) / 2.0,
    )


def _center_distance_ratio(left: dict, right: dict) -> float:
    left_w, left_h = _bbox_size(left)
    right_w, right_h = _bbox_size(right)
    left_cx, left_cy = _bbox_center(left)
    right_cx, right_cy = _bbox_center(right)
    distance = hypot(left_cx - right_cx, left_cy - right_cy)
    avg_diagonal = (hypot(left_w, left_h) + hypot(right_w, right_h)) / 2.0
    return distance / max(1.0, avg_diagonal)


def _similar_box_size(left: dict, right: dict) -> bool:
    left_w, left_h = _bbox_size(left)
    right_w, right_h = _bbox_size(right)
    width_ratio = max(left_w, right_w) / max(1.0, min(left_w, right_w))
    height_ratio = max(left_h, right_h) / max(1.0, min(left_h, right_h))
    area_left = max(1.0, left_w * left_h)
    area_right = max(1.0, right_w * right_h)
    area_ratio = max(area_left, area_right) / max(1.0, min(area_left, area_right))
    return width_ratio <= 1.75 and height_ratio <= 1.75 and area_ratio <= 2.40


def _same_body_source(left: dict, right: dict) -> bool:
    return bool(left.get("estimated_from_face")) == bool(right.get("estimated_from_face")) and str(
        left.get("detector") or ""
    ) == str(right.get("detector") or "")


def _embedding_similarity(left: list[float] | None, right: list[float] | None) -> float | None:
    if left is None or right is None:
        return None
    left_arr = np.asarray(left, dtype=np.float32).reshape(-1)
    right_arr = np.asarray(right, dtype=np.float32).reshape(-1)
    if left_arr.size == 0 or left_arr.size != right_arr.size:
        return None
    denominator = float(np.linalg.norm(left_arr) * np.linalg.norm(right_arr))
    if denominator < 1e-8:
        return None
    return float(np.dot(left_arr, right_arr) / denominator)


class UpperColorTemporalCache:
    def __init__(
        self,
        *,
        max_age_sec: float | None = None,
        iou_threshold: float | None = None,
        center_threshold: float | None = None,
        face_max_age_sec: float | None = None,
        face_similarity_threshold: float | None = None,
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
        self.center_threshold = (
            float(settings.upper_color_temporal_cache_center_threshold)
            if center_threshold is None
            else float(center_threshold)
        )
        self.face_max_age_sec = (
            float(settings.upper_color_temporal_cache_face_max_age_sec)
            if face_max_age_sec is None
            else float(face_max_age_sec)
        )
        self.face_similarity_threshold = (
            float(settings.upper_color_temporal_cache_face_similarity_threshold)
            if face_similarity_threshold is None
            else float(face_similarity_threshold)
        )
        self._entries: list[_UpperColorCacheEntry] = []

    def _prune(self, timestamp_sec: float) -> None:
        max_age = max(self.max_age_sec, self.face_max_age_sec)
        self._entries = [
            entry
            for entry in self._entries
            if 0.0 <= timestamp_sec - entry.timestamp_sec <= max_age
        ]

    def get(
        self,
        body: dict,
        *,
        timestamp_sec: float,
        used_entry_indexes: set[int],
        face_embedding: list[float] | None = None,
    ) -> person_analysis.RegionResult | None:
        self._prune(timestamp_sec)
        best: tuple[float, int, _UpperColorCacheEntry] | None = None
        for index, entry in enumerate(self._entries):
            if index in used_entry_indexes:
                continue
            age = timestamp_sec - entry.timestamp_sec
            if age < 0.0:
                continue

            similarity = _embedding_similarity(face_embedding, entry.face_embedding)
            if similarity is not None and age <= self.face_max_age_sec:
                if similarity >= self.face_similarity_threshold:
                    score = 2.0 + similarity - min(0.25, age / max(1.0, self.face_max_age_sec) * 0.25)
                    if best is None or score > best[0]:
                        best = (score, index, entry)

            if age > self.max_age_sec or not _same_body_source(body, entry.body):
                continue
            iou = _bbox_iou(body, entry.body)
            center_ratio = _center_distance_ratio(body, entry.body)
            center_match = center_ratio <= self.center_threshold and _similar_box_size(body, entry.body)
            if iou < self.iou_threshold and not center_match:
                continue
            center_score = max(0.0, 1.0 - center_ratio / max(1e-6, self.center_threshold))
            score = max(iou, center_score * 0.75)
            if best is None or score > best[0]:
                best = (score, index, entry)
        if best is None:
            return None
        used_entry_indexes.add(best[1])
        return best[2].prediction

    def put(
        self,
        body: dict,
        *,
        timestamp_sec: float,
        prediction: person_analysis.RegionResult,
        face_embedding: list[float] | None = None,
    ) -> None:
        self._prune(timestamp_sec)
        self._entries.append(
            _UpperColorCacheEntry(
                body=dict(body),
                timestamp_sec=timestamp_sec,
                prediction=prediction,
                face_embedding=list(face_embedding) if face_embedding is not None else None,
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


def _should_use_upper_backend_for_body(body: dict, *, has_face_context: bool = False) -> bool:
    if body.get("estimated_from_face") and not settings.enable_upper_color_backend_for_face_estimated_body:
        return False
    if not has_face_context and not settings.enable_upper_color_backend_for_body_only:
        return False
    return True


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
    allow_upper_backend: bool = True,
) -> dict[str, Any]:
    visibility = person_analysis.classify_body_visibility(frame, body, face)
    try:
        clothing = person_analysis.analyze_clothing(
            frame,
            body,
            visibility,
            upper_prediction=upper_prediction,
            allow_upper_backend=allow_upper_backend,
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
    face_embedding_by_body_id: dict[int, list[float]] | None = None,
) -> dict[int, person_analysis.RegionResult]:
    if not bodies or not settings.enable_clothing_detection or not settings.enable_upper_clothing_detection:
        return {}
    if settings.upper_color_backend != "clip_schp":
        return {}

    unique_bodies = []
    seen: set[int] = set()
    face_embedding_by_body_id = face_embedding_by_body_id or {}
    for body in bodies:
        body_key = id(body)
        if not _should_use_upper_backend_for_body(
            body,
            has_face_context=body_key in face_embedding_by_body_id,
        ):
            continue
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
                face_embedding=face_embedding_by_body_id.get(id(body)),
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
            cache.put(
                body,
                timestamp_sec=float(timestamp_sec),
                prediction=prediction,
                face_embedding=face_embedding_by_body_id.get(id(body)),
            )
    return results


def build_frame_observation_payloads(
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
    face_embedding_by_body_id: dict[int, list[float]] = {}
    for pair in match_result["pairs"]:
        face = faces[pair["face_index"]]
        embedding = face.get("embedding")
        if embedding is not None:
            face_embedding_by_body_id[id(bodies[pair["body_index"]])] = embedding

    for face_index in match_result["unmatched_face_indices"]:
        estimated_body = _estimated_body_from_face_if_visible(frame, faces[face_index])
        if estimated_body is not None:
            estimated_body_by_face_index[face_index] = estimated_body
            upper_prediction_bodies.append(estimated_body)
            embedding = faces[face_index].get("embedding")
            if embedding is not None:
                face_embedding_by_body_id[id(estimated_body)] = embedding
    for body_index in match_result["unmatched_body_indices"]:
        upper_prediction_bodies.append(bodies[body_index])
    upper_predictions = _batch_upper_predictions(
        frame,
        upper_prediction_bodies,
        timestamp_sec=video_timestamp_sec,
        cache=upper_color_cache,
        face_embedding_by_body_id=face_embedding_by_body_id,
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
            allow_upper_backend=_should_use_upper_backend_for_body(body, has_face_context=True),
        )
        observation = {
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
                allow_upper_backend=_should_use_upper_backend_for_body(
                    estimated_body,
                    has_face_context=True,
                ),
            )
            body_model_version = ESTIMATED_BODY_MODEL_VERSION
            observation_type = "face_and_body"

        observation = {
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
        observations.append(observation)

    for body_index in match_result["unmatched_body_indices"]:
        body = bodies[body_index]
        body_payload = _body_observation_payload(
            frame=frame,
            body=body,
            face=None,
            upper_prediction=upper_predictions.get(id(body)),
            allow_upper_backend=_should_use_upper_backend_for_body(body, has_face_context=False),
        )
        observation = {
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
        observations.append(observation)

    return observations


def persist_frame_observations(observation_payloads: list[dict]) -> list[dict]:
    return db.add_person_observations(observation_payloads)


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
    return persist_frame_observations(
        build_frame_observation_payloads(
            frame=frame,
            video_id=video_id,
            camera_id=camera_id,
            frame_path=frame_path,
            video_timestamp_sec=video_timestamp_sec,
            captured_at=captured_at,
            frame_index=frame_index,
            faces=faces,
            bodies=bodies,
            live_source_id=live_source_id,
            upper_color_cache=upper_color_cache,
        )
    )
