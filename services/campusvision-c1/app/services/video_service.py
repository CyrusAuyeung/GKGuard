from __future__ import annotations

import shutil
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import BinaryIO

import cv2

from app.core.config import settings
from app.storage import db
from app.vision.face_engine import get_face_engine
from app.vision.frame_sampler import iter_video_frames


def _safe_suffix(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    return suffix if suffix else ".mp4"


def save_uploaded_video(
    fileobj: BinaryIO,
    filename: str,
    camera_id: str,
    recorded_at: str | None,
    frame_interval_sec: float | None,
) -> dict:
    settings.ensure_dirs()

    if not db.get_camera(camera_id):
        # Allow fast local testing even if the camera was not created first.
        db.upsert_camera(
            {
                "camera_id": camera_id,
                "name": camera_id,
                "location": None,
                "lat": None,
                "lng": None,
            }
        )

    video_id = uuid.uuid4().hex
    dest = settings.video_uploads_dir / f"{video_id}{_safe_suffix(filename)}"

    with dest.open("wb") as f:
        shutil.copyfileobj(fileobj, f)

    return db.add_video(
        {
            "video_id": video_id,
            "filename": filename,
            "camera_id": camera_id,
            "recorded_at": recorded_at,
            "path": str(dest),
            "status": "uploaded",
            "frame_interval_sec": frame_interval_sec,
        }
    )


def _captured_at(recorded_at: str | None, offset_sec: float) -> str | None:
    if not recorded_at:
        return None

    raw = recorded_at.replace("Z", "")
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None

    return (dt + timedelta(seconds=float(offset_sec))).replace(microsecond=0).isoformat()


def index_video(video_id: str, frame_interval_sec: float | None = None) -> dict:
    video = db.get_video(video_id)
    if not video:
        raise KeyError(f"video_id not found: {video_id}")

    interval = frame_interval_sec or video.get("frame_interval_sec") or settings.default_frame_interval_sec
    engine = get_face_engine()

    db.update_video_status(video_id, "indexing")

    indexed = 0
    video_frame_dir = settings.frames_dir / video_id
    video_frame_dir.mkdir(parents=True, exist_ok=True)

    try:
        for timestamp_sec, frame in iter_video_frames(video["path"], every_seconds=float(interval)):
            boxes = engine.detect_faces(frame)
            if not boxes:
                continue

            embeddings = engine.embed_faces(frame, boxes)
            if not embeddings:
                continue
            if len(embeddings) != len(boxes):
                continue

            frame_file = video_frame_dir / f"{timestamp_sec:.2f}.jpg"
            cv2.imwrite(str(frame_file), frame)

            for box, embedding in zip(boxes, embeddings):
                face_id = uuid.uuid4().hex
                db.add_face_record(
                    {
                        "face_id": face_id,
                        "video_id": video_id,
                        "camera_id": video["camera_id"],
                        "frame_path": str(frame_file),
                        "video_timestamp_sec": float(timestamp_sec),
                        "captured_at": _captured_at(video.get("recorded_at"), timestamp_sec),
                        "bbox": box,
                        "embedding": embedding,
                    }
                )
                indexed += 1

        db.update_video_status(video_id, "indexed")
    except Exception:
        db.update_video_status(video_id, "failed")
        raise

    return {
        "video_id": video_id,
        "indexed_faces": indexed,
        "status": "indexed",
    }
