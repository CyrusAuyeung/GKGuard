from __future__ import annotations

import uuid
from typing import Any

import numpy as np

from app.core.config import settings
from app.storage import db
from app.vision import person_analysis


ESTIMATED_BODY_MODEL_VERSION = "face_estimated_body_v1"


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
) -> dict[str, Any]:
    visibility = person_analysis.classify_body_visibility(frame, body, face)
    try:
        clothing = person_analysis.analyze_clothing(frame, body, visibility)
    except Exception:
        clothing = _unknown_clothing()
    return {
        "body_visibility": visibility,
        "person_bbox": body,
        "person_detection_confidence": body.get("score"),
        **clothing,
    }


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
) -> list[dict]:
    match_result = person_analysis.match_faces_to_bodies(faces, bodies)
    observations = []

    for pair in match_result["pairs"]:
        face = faces[pair["face_index"]]
        body = bodies[pair["body_index"]]
        body_payload = _body_observation_payload(frame=frame, body=body, face=face)
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
        estimated_body = _estimated_body_from_face_if_visible(frame, face)
        body_payload = None
        body_model_version = settings.body_model_version
        observation_type = "face_only"
        if estimated_body is not None:
            body_payload = _body_observation_payload(frame=frame, body=estimated_body, face=face)
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
        body_payload = _body_observation_payload(frame=frame, body=body, face=None)
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
