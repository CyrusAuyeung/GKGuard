from __future__ import annotations

import ctypes
import gc
import shutil
import sys
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import BinaryIO

import cv2

from app.core import config
from app.services import event_build_queue, event_service, observation_service, person_service
from app.services.upload_limits import copy_upload_with_limit
from app.storage import db
from app.vision.body_detector import get_body_detector
from app.vision.face_engine import get_face_engine
from app.vision.frame_sampler import iter_video_frames


_MEMORY_CLEANUP_LOCK = threading.Lock()
_INDEX_COMPLETION_COUNT = 0


class _IndexPerformanceProfile:
    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled
        self.started_at = time.perf_counter()
        self.stages: dict[str, dict[str, float | int]] = {}
        self.counts: dict[str, int] = {}

    @contextmanager
    def stage(self, name: str):
        if not self.enabled:
            yield
            return
        started = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - started
            entry = self.stages.setdefault(name, {"elapsed_sec": 0.0, "calls": 0})
            entry["elapsed_sec"] = float(entry["elapsed_sec"]) + elapsed
            entry["calls"] = int(entry["calls"]) + 1

    def count(self, name: str, amount: int = 1) -> None:
        if self.enabled:
            self.counts[name] = self.counts.get(name, 0) + int(amount)

    def summary(self, *, processing_duration_sec: float | None = None) -> dict | None:
        if not self.enabled:
            return None
        total_sec = time.perf_counter() - self.started_at
        denominator = processing_duration_sec or total_sec or 1e-9
        stages = {}
        for name, entry in self.stages.items():
            elapsed = float(entry["elapsed_sec"])
            calls = int(entry["calls"])
            stages[name] = {
                "elapsed_sec": round(elapsed, 6),
                "calls": calls,
                "avg_sec": round(elapsed / calls, 6) if calls else None,
                "processing_pct": round((elapsed / denominator) * 100.0, 3),
            }
        return {
            "schema_version": "c1_index_performance_profile_v1",
            "total_wall_sec": round(total_sec, 6),
            "processing_duration_sec": round(processing_duration_sec, 6)
            if processing_duration_sec is not None
            else None,
            "stages": dict(sorted(stages.items(), key=lambda item: item[1]["elapsed_sec"], reverse=True)),
            "counts": dict(sorted(self.counts.items())),
        }


def _settings():
    return config.settings


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
    settings = _settings()
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


def _event_persistence_mode() -> str:
    settings = _settings()
    if not settings.enable_event_persistence:
        return "disabled"
    mode = (settings.event_persistence_mode or "sync").strip().lower()
    if mode not in {"sync", "async", "disabled"}:
        raise ValueError("EVENT_PERSISTENCE_MODE must be one of: sync, async, disabled")
    return mode


def _cleanup_process_memory_after_index() -> dict:
    global _INDEX_COMPLETION_COUNT
    settings = _settings()
    if not settings.enable_post_index_memory_cleanup:
        return {"enabled": False, "triggered": False}

    interval = max(1, int(settings.post_index_memory_cleanup_interval or 1))
    with _MEMORY_CLEANUP_LOCK:
        _INDEX_COMPLETION_COUNT += 1
        completion_count = _INDEX_COMPLETION_COUNT
        if completion_count % interval != 0:
            return {
                "enabled": True,
                "triggered": False,
                "completion_count": completion_count,
                "interval": interval,
            }

        collected = gc.collect()
        trimmed = False
        if sys.platform.startswith("linux"):
            try:
                libc = ctypes.CDLL("libc.so.6")
                trimmed = bool(libc.malloc_trim(0))
            except Exception:
                trimmed = False
        return {
            "enabled": True,
            "triggered": True,
            "completion_count": completion_count,
            "interval": interval,
            "gc_collected": collected,
            "malloc_trim": trimmed,
        }


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


def _restore_previous_video_index(db_backup: Path | None, frame_dir: Path, frame_backup_dir: Path | None) -> bool:
    settings = _settings()
    restored = False
    if frame_dir.exists():
        shutil.rmtree(frame_dir)
    if frame_backup_dir and frame_backup_dir.exists():
        shutil.move(str(frame_backup_dir), str(frame_dir))
        restored = True
    if db_backup and db_backup.exists():
        shutil.copy2(db_backup, settings.db_path)
        restored = True
    return restored


def _video_has_index_artifacts(video_id: str, frame_dir: Path) -> bool:
    if frame_dir.exists():
        return True

    with db.get_conn() as conn:
        for sql in (
            "SELECT 1 FROM face_records WHERE video_id = ? LIMIT 1",
            "SELECT 1 FROM person_observations WHERE video_id = ? LIMIT 1",
            "SELECT 1 FROM events WHERE video_id = ? LIMIT 1",
        ):
            row = conn.execute(sql, (video_id,)).fetchone()
            if row is not None:
                return True
    return False


def index_video(video_id: str, frame_interval_sec: float | None = None, *, collect_profile: bool = False) -> dict:
    settings = _settings()
    profile = _IndexPerformanceProfile(collect_profile)
    with profile.stage("db_get_video"):
        video = db.get_video(video_id)
    if not video:
        raise KeyError(f"video_id not found: {video_id}")

    interval = frame_interval_sec or video.get("frame_interval_sec") or settings.default_frame_interval_sec
    with profile.stage("face_engine_get"):
        engine = get_face_engine()
    with profile.stage("body_detector_get"):
        body_detector = get_body_detector()

    processing_started = time.perf_counter()
    with profile.stage("db_start_video_processing"):
        db.start_video_processing(video_id)

    indexed = 0
    sampled_frames = 0
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
    had_previous_index = _video_has_index_artifacts(video_id, video_frame_dir)
    commit_started = False
    commit_succeeded = False
    restore_succeeded = False
    sampled_items: list[dict] = []
    upper_color_cache = (
        observation_service.UpperColorTemporalCache()
        if settings.enable_upper_color_temporal_cache
        else None
    )
    body_detection_frame_stride = max(1, int(settings.body_detection_frame_stride or 1))
    clothing_analysis_frame_stride = max(1, int(settings.clothing_analysis_frame_stride or 1))
    event_persistence_mode = _event_persistence_mode()

    try:
        staging_frame_dir.mkdir(parents=True, exist_ok=True)
        frame_iterator = iter_video_frames(video["path"], every_seconds=float(interval))
        frame_index = 0
        while True:
            with profile.stage("frame_decode_sample"):
                try:
                    timestamp_sec, frame = next(frame_iterator)
                except StopIteration:
                    break
            sampled_frames += 1
            profile.count("sampled_frames")
            if sampled_frames > settings.max_index_frames:
                raise RuntimeError(f"Indexing exceeded the {settings.max_index_frames} frame limit.")

            with profile.stage("face_detect_embed"):
                boxes, embeddings = _detect_faces_and_embeddings(engine, frame)
            profile.count("detected_faces", len(boxes))
            usable_face_count = len(boxes) if embeddings and len(embeddings) == len(boxes) else 0
            profile.count("usable_faces", usable_face_count)

            if frame_index % body_detection_frame_stride == 0:
                try:
                    with profile.stage("body_detect"):
                        bodies = body_detector.detect_people(frame)
                except Exception:
                    bodies = []
            else:
                bodies = []
                profile.count("body_detection_skipped_by_stride")
            detected_bodies += len(bodies)
            profile.count("detected_bodies", len(bodies))

            if usable_face_count <= 0 and not bodies:
                profile.count("skipped_empty_frames")
                frame_index += 1
                continue

            frame_file = staging_frame_dir / f"{timestamp_sec:.2f}-{uuid.uuid4().hex}.jpg"
            with profile.stage("frame_write"):
                if not cv2.imwrite(str(frame_file), frame):
                    raise RuntimeError("Failed to write sampled frame.")
            created_frame_files.append(frame_file)
            profile.count("retained_frames")

            sampled_items.append(
                {
                    "frame_index": frame_index,
                    "timestamp_sec": float(timestamp_sec),
                    "staging_frame_file": frame_file,
                    "boxes": boxes[:usable_face_count],
                    "embeddings": embeddings[:usable_face_count],
                    "bodies": bodies,
                }
            )
            frame_index += 1

        for sampled_item in sampled_items:
            timestamp_sec = sampled_item["timestamp_sec"]
            frame_index = sampled_item["frame_index"]
            staging_frame_file = sampled_item["staging_frame_file"]
            final_frame_file = video_frame_dir / staging_frame_file.name
            with profile.stage("observation_frame_read"):
                frame = cv2.imread(str(staging_frame_file))
            if frame is None:
                raise RuntimeError(f"Failed to read staged frame: {staging_frame_file.name}")

            captured_at = _captured_at(video.get("recorded_at"), timestamp_sec)
            analyze_clothing = frame_index % clothing_analysis_frame_stride == 0
            if not analyze_clothing:
                profile.count("clothing_analysis_skipped_by_stride")
            face_items = []
            face_records = []
            for box, embedding in zip(sampled_item["boxes"], sampled_item["embeddings"]):
                face_id = uuid.uuid4().hex
                face_records.append(
                    {
                        "face_id": face_id,
                        "video_id": video_id,
                        "camera_id": video["camera_id"],
                        "frame_path": str(final_frame_file),
                        "video_timestamp_sec": float(timestamp_sec),
                        "captured_at": captured_at,
                        "bbox": box,
                        "embedding": embedding,
                    }
                )
                face_items.append({"face_id": face_id, "embedding": embedding, **box})

            with profile.stage("observation_payload_build"):
                observation_payloads = observation_service.build_frame_observation_payloads(
                    frame=frame,
                    video_id=video_id,
                    camera_id=video["camera_id"],
                    frame_path=str(final_frame_file),
                    video_timestamp_sec=float(timestamp_sec),
                    captured_at=captured_at,
                    frame_index=frame_index,
                    faces=face_items,
                    bodies=sampled_item["bodies"],
                    upper_color_cache=upper_color_cache,
                    analyze_clothing=analyze_clothing,
                )
            sampled_item["face_records"] = face_records
            sampled_item["observation_payloads"] = observation_payloads
            profile.count("observation_payloads_built", len(observation_payloads))

        with profile.stage("commit_total"):
            with db.write_lock():
                if settings.db_path.exists():
                    with profile.stage("commit_db_backup"):
                        shutil.copy2(settings.db_path, db_backup)
                    previous_db_backed_up = True
                if video_frame_dir.exists():
                    with profile.stage("commit_frame_dir_backup"):
                        shutil.move(str(video_frame_dir), str(backup_frame_dir))
                    previous_frame_dir_backed_up = True

                commit_started = True
                with profile.stage("commit_clear_previous_index"):
                    _clear_previous_video_index(video_id, video_frame_dir)
                with profile.stage("commit_promote_frames"):
                    shutil.move(str(staging_frame_dir), str(video_frame_dir))

                for sampled_item in sampled_items:
                    with profile.stage("commit_face_record_write"):
                        written_faces = db.add_face_records(sampled_item["face_records"])
                    indexed += written_faces
                    profile.count("face_records_written", written_faces)

                    with profile.stage("commit_observation_write"):
                        observations = observation_service.persist_frame_observations(
                            sampled_item["observation_payloads"]
                        )
                    observed += len(observations)
                    profile.count("observations_written", len(observations))

                if event_persistence_mode == "sync":
                    with profile.stage("commit_event_rebuild"):
                        event_result = event_service.rebuild_events_for_video(video_id)
                    if event_result:
                        profile.count("events_written", int(event_result.get("events") or 0))

                processing_duration = time.perf_counter() - processing_started
                with profile.stage("db_finish_video_processing"):
                    db.finish_video_processing(
                        video_id,
                        status="indexed",
                        duration_sec=processing_duration,
                    )
                commit_succeeded = True
    except Exception as exc:
        if commit_started:
            with db.write_lock():
                if previous_db_backed_up or previous_frame_dir_backed_up:
                    restore_succeeded = _restore_previous_video_index(
                        db_backup if previous_db_backed_up else None,
                        video_frame_dir,
                        backup_frame_dir if previous_frame_dir_backed_up else None,
                    )
                elif video_frame_dir.exists():
                    shutil.rmtree(video_frame_dir)

                status = (video.get("status") or "uploaded") if had_previous_index and restore_succeeded else "failed"
                db.finish_video_processing(
                    video_id,
                    status=status,
                    duration_sec=time.perf_counter() - processing_started,
                    error=str(exc),
                )
        else:
            for frame_file in created_frame_files:
                frame_file.unlink(missing_ok=True)
            if staging_frame_dir.exists():
                shutil.rmtree(staging_frame_dir)
            status = (video.get("status") or "uploaded") if had_previous_index else "failed"
            db.finish_video_processing(
                video_id,
                status=status,
                duration_sec=time.perf_counter() - processing_started,
                error=str(exc),
            )
        raise
    finally:
        with profile.stage("cleanup_temp_artifacts"):
            if staging_frame_dir.exists():
                shutil.rmtree(staging_frame_dir)
            can_remove_backups = commit_succeeded or restore_succeeded or not commit_started
            if backup_frame_dir.exists() and can_remove_backups:
                shutil.rmtree(backup_frame_dir)
            if db_backup.exists() and can_remove_backups:
                db_backup.unlink()

    if commit_succeeded and event_persistence_mode == "async":
        with profile.stage("event_rebuild_queue"):
            event_result = event_build_queue.enqueue_video_event_rebuild(video_id)

    with profile.stage("release_working_sets"):
        sampled_items.clear()
        created_frame_files.clear()
        upper_color_cache = None
        sampled_item = None
        frame = None
        boxes = None
        embeddings = None
        bodies = None
        face_items = None
        face_records = None
        observation_payloads = None

    with profile.stage("post_index_memory_cleanup"):
        memory_cleanup = _cleanup_process_memory_after_index()

    processing_duration = time.perf_counter() - processing_started
    performance_profile = profile.summary(processing_duration_sec=processing_duration)

    result = {
        "video_id": video_id,
        "indexed_faces": indexed,
        "indexed_observations": observed,
        "detected_bodies": detected_bodies,
        "event_result": event_result,
        "memory_cleanup": memory_cleanup,
        "status": "indexed",
    }
    if performance_profile is not None:
        result["performance_profile"] = performance_profile
    return result
