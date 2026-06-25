from __future__ import annotations

import shutil
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import BinaryIO

import cv2

from app.core.config import settings
from app.services import event_service, observation_service, person_service
from app.services.upload_limits import copy_upload_with_limit
from app.storage import db
from app.vision.body_detector import get_body_detector
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

    copy_upload_with_limit(fileobj, dest, settings.max_video_upload_bytes, label="Video upload")

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


def _detect_faces_and_embeddings(engine, frame) -> tuple[list[dict], list[list[float]]]:
    detect_with_embeddings = getattr(engine, "detect_faces_with_embeddings", None)
    if callable(detect_with_embeddings):
        return detect_with_embeddings(frame)

    boxes = engine.detect_faces(frame)
    embeddings = engine.embed_faces(frame, boxes) if boxes else []
    return boxes, embeddings


def _clear_previous_video_index(video_id: str, frame_dir: Path) -> None:
    affected_person_ids = set(db.list_person_ids_for_video_faces(video_id))
    affected_person_ids.update(db.delete_events_for_video(video_id))
    affected_person_ids.update(db.delete_person_observations_for_video(video_id))
    db.delete_face_records_for_video(video_id)
    if affected_person_ids:
        person_service.refresh_persons_from_remaining_faces(affected_person_ids)
        event_service.rebuild_appearance_sessions_for_persons(affected_person_ids)
    if frame_dir.exists():
        shutil.rmtree(frame_dir)


def _restore_previous_video_index(db_backup: Path | None, frame_dir: Path, frame_backup_dir: Path | None) -> None:
    if frame_dir.exists():
        shutil.rmtree(frame_dir)
    if frame_backup_dir and frame_backup_dir.exists():
        shutil.move(str(frame_backup_dir), str(frame_dir))
    if db_backup and db_backup.exists():
        shutil.copy2(db_backup, settings.db_path)


def index_video(video_id: str, frame_interval_sec: float | None = None) -> dict:
    video = db.get_video(video_id)
    if not video:
        raise KeyError(f"video_id not found: {video_id}")

    interval = frame_interval_sec or video.get("frame_interval_sec") or settings.default_frame_interval_sec
    engine = get_face_engine()
    body_detector = get_body_detector()

    processing_started = time.perf_counter()
    db.start_video_processing(video_id)

    indexed = 0
    sampled_frames = 0
    created_face_ids: list[str] = []
    created_frame_files: list[Path] = []
    observed = 0
    detected_bodies = 0
    event_result = None
    video_frame_dir = settings.frames_dir / video_id
    staging_frame_dir = settings.frames_dir / f".{video_id}.indexing-{uuid.uuid4().hex}"
    backup_frame_dir = settings.frames_dir / f".{video_id}.previous-{uuid.uuid4().hex}"
    db_backup = settings.data_dir / f".{video_id}.previous-{uuid.uuid4().hex}.sqlite3"
    previous_frame_dir_backed_up = False
    previous_db_backed_up = False
    sampled_items: list[dict] = []
    upper_color_cache = (
        observation_service.UpperColorTemporalCache()
        if settings.enable_upper_color_temporal_cache
        else None
    )

    try:
        staging_frame_dir.mkdir(parents=True, exist_ok=True)
        for frame_index, (timestamp_sec, frame) in enumerate(
            iter_video_frames(video["path"], every_seconds=float(interval))
        ):
            sampled_frames += 1
            if sampled_frames > settings.max_index_frames:
                raise RuntimeError(f"Indexing exceeded the {settings.max_index_frames} frame limit.")

            boxes, embeddings = _detect_faces_and_embeddings(engine, frame)
            usable_face_count = len(boxes) if embeddings and len(embeddings) == len(boxes) else 0

            try:
                bodies = body_detector.detect_people(frame)
            except Exception:
                bodies = []
            detected_bodies += len(bodies)

            if usable_face_count <= 0 and not bodies:
                continue

            frame_file = staging_frame_dir / f"{timestamp_sec:.2f}-{uuid.uuid4().hex}.jpg"
            if not cv2.imwrite(str(frame_file), frame):
                raise RuntimeError("Failed to write sampled frame.")
            created_frame_files.append(frame_file)

            sampled_items.append(
                {
                    "frame_index": frame_index,
                    "timestamp_sec": float(timestamp_sec),
                    "frame": frame,
                    "staging_frame_file": frame_file,
                    "boxes": boxes[:usable_face_count],
                    "embeddings": embeddings[:usable_face_count],
                    "bodies": bodies,
                }
            )

        if settings.db_path.exists():
            shutil.copy2(settings.db_path, db_backup)
            previous_db_backed_up = True
        if video_frame_dir.exists():
            shutil.move(str(video_frame_dir), str(backup_frame_dir))
            previous_frame_dir_backed_up = True
        _clear_previous_video_index(video_id, video_frame_dir)
        shutil.move(str(staging_frame_dir), str(video_frame_dir))

        for sampled_item in sampled_items:
            timestamp_sec = sampled_item["timestamp_sec"]
            frame = sampled_item["frame"]
            frame_index = sampled_item["frame_index"]
            frame_file = video_frame_dir / sampled_item["staging_frame_file"].name

            face_items = []
            for box, embedding in zip(sampled_item["boxes"], sampled_item["embeddings"]):
                face_id = uuid.uuid4().hex
                captured_at = _captured_at(video.get("recorded_at"), timestamp_sec)
                db.add_face_record(
                    {
                        "face_id": face_id,
                        "video_id": video_id,
                        "camera_id": video["camera_id"],
                        "frame_path": str(frame_file),
                        "video_timestamp_sec": float(timestamp_sec),
                        "captured_at": captured_at,
                        "bbox": box,
                        "embedding": embedding,
                    }
                )
                created_face_ids.append(face_id)
                face_items.append({"face_id": face_id, **box})
                indexed += 1

            observations = observation_service.create_frame_observations(
                frame=frame,
                video_id=video_id,
                camera_id=video["camera_id"],
                frame_path=str(frame_file),
                video_timestamp_sec=float(timestamp_sec),
                captured_at=_captured_at(video.get("recorded_at"), timestamp_sec),
                frame_index=frame_index,
                faces=face_items,
                bodies=sampled_item["bodies"],
                upper_color_cache=upper_color_cache,
            )
            observed += len(observations)

        if settings.enable_event_persistence:
            event_result = event_service.rebuild_events_for_video(video_id)

        db.finish_video_processing(
            video_id,
            status="indexed",
            duration_sec=time.perf_counter() - processing_started,
        )
    except Exception as exc:
        db.delete_events_for_video(video_id)
        db.delete_person_observations_for_video(video_id)
        db.delete_face_records_by_ids(created_face_ids)
        if previous_db_backed_up or previous_frame_dir_backed_up:
            _restore_previous_video_index(
                db_backup if previous_db_backed_up else None,
                video_frame_dir,
                backup_frame_dir if previous_frame_dir_backed_up else None,
            )
            db.finish_video_processing(
                video_id,
                status=video.get("status") or "uploaded",
                duration_sec=time.perf_counter() - processing_started,
                error=str(exc),
            )
        else:
            for frame_file in created_frame_files:
                frame_file.unlink(missing_ok=True)
            try:
                staging_frame_dir.rmdir()
            except OSError:
                pass
            db.finish_video_processing(
                video_id,
                status="failed",
                duration_sec=time.perf_counter() - processing_started,
                error=str(exc),
            )
        raise
    finally:
        if staging_frame_dir.exists():
            shutil.rmtree(staging_frame_dir)
        if backup_frame_dir.exists():
            shutil.rmtree(backup_frame_dir)
        if db_backup.exists():
            db_backup.unlink()

    return {
        "video_id": video_id,
        "indexed_faces": indexed,
        "indexed_observations": observed,
        "detected_bodies": detected_bodies,
        "event_result": event_result,
        "status": "indexed",
    }
