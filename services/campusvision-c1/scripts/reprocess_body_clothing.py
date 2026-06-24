from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from hashlib import sha1
from pathlib import Path
from typing import Any

import cv2


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import settings  # noqa: E402
from app.services import event_service  # noqa: E402
from app.storage import db  # noqa: E402
from app.vision import person_analysis  # noqa: E402
from app.vision.body_detector import get_body_detector  # noqa: E402


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


def _person_lookup() -> dict[str, str]:
    with db.get_conn() as conn:
        rows = conn.execute("SELECT face_id, person_id FROM person_faces").fetchall()
    return {row["face_id"]: row["person_id"] for row in rows}


def _face_records(video_ids: set[str] | None = None) -> list[dict[str, Any]]:
    params: list[Any] = []
    where = ""
    if video_ids:
        placeholders = ",".join("?" for _ in video_ids)
        where = f"WHERE video_id IN ({placeholders})"
        params.extend(sorted(video_ids))

    sql = f"""
        SELECT face_id, video_id, camera_id, frame_path, video_timestamp_sec,
               captured_at, bbox_json, observation_id, created_at
        FROM face_records
        {where}
        ORDER BY frame_path, video_timestamp_sec, face_id
    """
    with db.get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()

    records = []
    for row in rows:
        record = dict(row)
        record["bbox"] = json.loads(record.pop("bbox_json"))
        records.append(record)
    return records


def _existing_observation(record: dict[str, Any]) -> dict[str, Any] | None:
    observation_id = record.get("observation_id") or f"obs_face_{record['face_id']}"
    observation = db.get_person_observation(observation_id)
    if observation:
        return observation

    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT observation_id FROM person_observations WHERE face_record_id = ?",
            (record["face_id"],),
        ).fetchone()
    if not row:
        return None
    return db.get_person_observation(row["observation_id"])


def _body_payload(frame, body: dict, face: dict | None) -> dict[str, Any]:
    visibility = person_analysis.classify_body_visibility(frame, body, face)
    if body.get("estimated_from_face") and body.get("estimated_bottom_clipped") and visibility == "full_body":
        visibility = "upper_body"

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


def _face_observation_payload(
    *,
    record: dict[str, Any],
    existing: dict[str, Any] | None,
    person_id: str | None,
    frame_index: int | None,
    body_payload: dict[str, Any] | None,
    body_model_version: str,
) -> dict[str, Any]:
    if body_payload is None:
        body_payload = {
            "body_visibility": "face_only",
            "person_bbox": None,
            "person_detection_confidence": None,
            **_unknown_clothing(),
        }

    return {
        "observation_id": (existing or {}).get("observation_id") or record.get("observation_id") or f"obs_face_{record['face_id']}",
        "camera_id": record["camera_id"],
        "video_id": record["video_id"],
        "live_source_id": (existing or {}).get("live_source_id"),
        "frame_index": (existing or {}).get("frame_index", frame_index),
        "video_timestamp_sec": record.get("video_timestamp_sec"),
        "captured_at": record.get("captured_at"),
        "frame_path": record["frame_path"],
        "track_id": (existing or {}).get("track_id"),
        "observation_type": "face_and_body" if body_payload.get("person_bbox") else "face_only",
        "face_record_id": record["face_id"],
        "person_id": person_id,
        "clothing_model_version": settings.clothing_model_version,
        "body_model_version": body_model_version,
        "created_at": (existing or {}).get("created_at"),
        **body_payload,
    }


def _body_only_id(frame_path: str, body_index: int, body: dict) -> str:
    raw = "|".join(
        [
            frame_path,
            str(body_index),
            str(int(body.get("x1", 0))),
            str(int(body.get("y1", 0))),
            str(int(body.get("x2", 0))),
            str(int(body.get("y2", 0))),
        ]
    )
    return "obs_body_" + sha1(raw.encode("utf-8")).hexdigest()[:20]


def _body_only_observation_payload(
    *,
    record: dict[str, Any],
    frame_index: int | None,
    body_index: int,
    body: dict,
    body_payload: dict[str, Any],
) -> dict[str, Any]:
    existing = db.get_person_observation(_body_only_id(record["frame_path"], body_index, body))
    return {
        "observation_id": _body_only_id(record["frame_path"], body_index, body),
        "camera_id": record["camera_id"],
        "video_id": record["video_id"],
        "live_source_id": (existing or {}).get("live_source_id"),
        "frame_index": (existing or {}).get("frame_index", frame_index),
        "video_timestamp_sec": record.get("video_timestamp_sec"),
        "captured_at": record.get("captured_at"),
        "frame_path": record["frame_path"],
        "track_id": (existing or {}).get("track_id"),
        "observation_type": "body_only",
        "face_record_id": None,
        "person_id": None,
        "clothing_model_version": settings.clothing_model_version,
        "body_model_version": settings.body_model_version,
        "created_at": (existing or {}).get("created_at"),
        **body_payload,
    }


def reprocess(
    *,
    video_ids: set[str] | None = None,
    estimate_missing_body: bool = True,
    include_body_only: bool = False,
    limit_frames: int | None = None,
    print_every: int = 25,
) -> dict[str, Any]:
    db.init_db()
    face_to_person = _person_lookup()
    records = _face_records(video_ids)
    frames: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        frames[record["frame_path"]].append(record)

    body_detector = get_body_detector()
    touched_videos: set[str] = set()
    stats = {
        "frames_total": len(frames),
        "frames_processed": 0,
        "frames_failed": 0,
        "face_records": len(records),
        "hog_bodies": 0,
        "hog_face_matches": 0,
        "estimated_face_bodies": 0,
        "face_only": 0,
        "body_only_upserts": 0,
        "upper_visible": 0,
        "lower_visible": 0,
    }

    for frame_index, (frame_path, frame_records) in enumerate(frames.items()):
        if limit_frames is not None and stats["frames_processed"] >= limit_frames:
            break

        frame = cv2.imread(frame_path)
        if frame is None:
            stats["frames_failed"] += 1
            continue

        faces = []
        for record in frame_records:
            faces.append({"face_id": record["face_id"], **record["bbox"]})

        try:
            bodies = body_detector.detect_people(frame)
        except Exception:
            bodies = []
        stats["hog_bodies"] += len(bodies)

        match_result = person_analysis.match_faces_to_bodies(faces, bodies)
        matched_body_by_face = {
            pair["face_index"]: bodies[pair["body_index"]]
            for pair in match_result["pairs"]
        }
        stats["hog_face_matches"] += len(matched_body_by_face)

        height, width = frame.shape[:2]
        for face_index, record in enumerate(frame_records):
            face = faces[face_index]
            body = matched_body_by_face.get(face_index)
            body_model_version = settings.body_model_version
            if body is None and estimate_missing_body:
                body = person_analysis.estimate_body_bbox_from_face(face, width, height)
                body_model_version = ESTIMATED_BODY_MODEL_VERSION
                stats["estimated_face_bodies"] += 1

            body_payload = _body_payload(frame, body, face) if body else None
            if body_payload is None:
                stats["face_only"] += 1
            else:
                stats["upper_visible"] += 1 if body_payload.get("upper_visible") else 0
                stats["lower_visible"] += 1 if body_payload.get("lower_visible") else 0

            existing = _existing_observation(record)
            observation = db.add_person_observation(
                _face_observation_payload(
                    record=record,
                    existing=existing,
                    person_id=face_to_person.get(record["face_id"]),
                    frame_index=frame_index,
                    body_payload=body_payload,
                    body_model_version=body_model_version,
                )
            )
            db.update_face_record_observation(record["face_id"], observation["observation_id"])
            touched_videos.add(record["video_id"])

        if include_body_only:
            for body_index in match_result["unmatched_body_indices"]:
                body = bodies[body_index]
                body_payload = _body_payload(frame, body, None)
                db.add_person_observation(
                    _body_only_observation_payload(
                        record=frame_records[0],
                        frame_index=frame_index,
                        body_index=body_index,
                        body=body,
                        body_payload=body_payload,
                    )
                )
                stats["body_only_upserts"] += 1
                stats["upper_visible"] += 1 if body_payload.get("upper_visible") else 0
                stats["lower_visible"] += 1 if body_payload.get("lower_visible") else 0
                touched_videos.add(frame_records[0]["video_id"])

        stats["frames_processed"] += 1
        if print_every > 0 and stats["frames_processed"] % print_every == 0:
            print({"progress": stats["frames_processed"], "frames_total": stats["frames_total"]}, flush=True)

    event_result = event_service.rebuild_events_for_videos(touched_videos)
    stats["videos_rebuilt"] = event_result["videos"]
    stats["events"] = event_result["events"]
    stats["source_observations"] = event_result["source_observations"]
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Re-run person body and clothing analysis on existing C1 frames.")
    parser.add_argument("--video-id", action="append", default=None, help="Limit to one video_id. Can be repeated.")
    parser.add_argument("--no-estimate-missing-body", action="store_true", help="Do not estimate body boxes from faces.")
    parser.add_argument("--include-body-only", action="store_true", help="Also persist unmatched body-only detections.")
    parser.add_argument("--limit-frames", type=int, default=None, help="Debug limit for processed frames.")
    parser.add_argument("--print-every", type=int, default=25, help="Progress print interval in frames.")
    args = parser.parse_args()

    stats = reprocess(
        video_ids=set(args.video_id) if args.video_id else None,
        estimate_missing_body=not args.no_estimate_missing_body,
        include_body_only=args.include_body_only,
        limit_frames=args.limit_frames,
        print_every=args.print_every,
    )
    print(stats)


if __name__ == "__main__":
    main()
