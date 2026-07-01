from __future__ import annotations

import json
import shutil
import subprocess
import sys
import threading
import uuid
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import cv2

from app.core.config import settings
from app.services import person_service, video_service
from app.storage import db

_analysis_lock = threading.Lock()
_workers_lock = threading.Lock()
_workers: dict[str, "_LiveMonitorWorker"] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _live_analysis_context():
    return _analysis_lock if settings.serialize_live_analysis else nullcontext()


def _iso_from_dt(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _ffmpeg_path() -> str:
    candidate = Path(sys.executable).with_name("ffmpeg")
    if candidate.exists():
        return str(candidate)
    found = shutil.which("ffmpeg")
    if found:
        return found
    raise RuntimeError("ffmpeg not found in PATH or next to the Python executable")


def _ffprobe_path() -> str:
    candidate = Path(sys.executable).with_name("ffprobe")
    if candidate.exists():
        return str(candidate)
    found = shutil.which("ffprobe")
    if found:
        return found
    raise RuntimeError("ffprobe not found in PATH or next to the Python executable")


def _has_video_stream(path: Path) -> bool:
    if not path.exists() or path.stat().st_size <= 1024:
        return False

    cmd = [
        _ffprobe_path(),
        "-hide_banner",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=codec_type,width,height",
        "-of",
        "json",
        str(path),
    ]
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=15)
        data = json.loads(result.stdout or "{}")
    except Exception:
        return False
    return bool(data.get("streams"))


def _run_capture(cmd: list[str], timeout: float) -> None:
    subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=timeout)


def _safe_source_type(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in {"rtsp", "http", "mjpeg", "file"}:
        raise ValueError(f"unsupported source_type: {value}")
    return normalized


def upsert_live_source(payload: dict[str, Any]) -> dict[str, Any]:
    source_type = _safe_source_type(payload.get("source_type", "rtsp"))
    camera = db.upsert_camera(
        {
            "camera_id": payload["camera_id"],
            "name": payload.get("name") or payload["camera_id"],
            "location": payload.get("location"),
            "lat": payload.get("lat"),
            "lng": payload.get("lng"),
        }
    )
    source = db.upsert_live_source(
        {
            "source_id": payload["source_id"],
            "camera_id": camera["camera_id"],
            "name": payload.get("name") or camera["name"],
            "source_type": source_type,
            "url": payload["url"],
            "enabled": payload.get("enabled", True),
        }
    )
    return source | {
        "location": camera.get("location"),
        "lat": camera.get("lat"),
        "lng": camera.get("lng"),
    }


def list_live_sources() -> list[dict[str, Any]]:
    cameras = {camera["camera_id"]: camera for camera in db.list_cameras()}
    items = []
    for source in db.list_live_sources():
        camera = cameras.get(source["camera_id"], {})
        items.append(
            source
            | {
                "location": camera.get("location"),
                "lat": camera.get("lat"),
                "lng": camera.get("lng"),
            }
        )
    return items


def probe_live_source(source_id: str, read_timeout_sec: float = 5.0) -> dict[str, Any]:
    source = db.get_live_source(source_id)
    if not source:
        raise KeyError(f"source_id not found: {source_id}")

    cap = cv2.VideoCapture(source["url"])
    if hasattr(cv2, "CAP_PROP_OPEN_TIMEOUT_MSEC"):
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, int(read_timeout_sec * 1000))
    if hasattr(cv2, "CAP_PROP_READ_TIMEOUT_MSEC"):
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, int(read_timeout_sec * 1000))

    if not cap.isOpened():
        cap.release()
        return {
            "source_id": source_id,
            "camera_id": source["camera_id"],
            "reachable": False,
            "source_type": source["source_type"],
            "url": source["url"],
            "message": "source could not be opened",
        }

    ok, _ = cap.read()
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0) or None
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0) or None
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0) or None
    cap.release()

    return {
        "source_id": source_id,
        "camera_id": source["camera_id"],
        "reachable": bool(ok),
        "source_type": source["source_type"],
        "url": source["url"],
        "width": width,
        "height": height,
        "fps": fps,
        "message": None if ok else "source opened but did not return a frame",
    }


def capture_live_source(
    source_id: str,
    duration_sec: float = 10.0,
    frame_interval_sec: float | None = None,
    index: bool = False,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    source = db.get_live_source(source_id)
    if not source:
        raise KeyError(f"source_id not found: {source_id}")
    if not source.get("enabled", True):
        raise RuntimeError(f"live source is disabled: {source_id}")

    settings.ensure_dirs()
    duration = max(1.0, min(float(duration_sec), 300.0))
    video_id = f"live_{source_id}_{uuid.uuid4().hex[:12]}"
    dest = settings.video_uploads_dir / f"{video_id}.mp4"

    cmd = [_ffmpeg_path(), "-hide_banner", "-y"]
    if source["source_type"] == "rtsp":
        cmd.extend(["-rtsp_transport", "tcp"])
    cmd.extend(
        [
            "-i",
            source["url"],
            "-t",
            f"{duration:.3f}",
            "-an",
            "-c:v",
            "copy",
            str(dest),
        ]
    )

    try:
        _run_capture(cmd, timeout=duration + 30)
    except subprocess.CalledProcessError:
        pass

    if not _has_video_stream(dest):
        dest.unlink(missing_ok=True)
        # Live streams can be joined between keyframes. Remuxing may succeed but
        # produce an empty MP4, so transcode as the robust fallback.
        fallback_cmd = [_ffmpeg_path(), "-hide_banner", "-y"]
        if source["source_type"] == "rtsp":
            fallback_cmd.extend(["-rtsp_transport", "tcp"])
        fallback_cmd.extend(
            [
                "-i",
                source["url"],
                "-t",
                f"{duration:.3f}",
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-pix_fmt",
                "yuv420p",
                str(dest),
            ]
        )
        _run_capture(fallback_cmd, timeout=duration + 60)

    if not _has_video_stream(dest):
        dest.unlink(missing_ok=True)
        raise RuntimeError("ffmpeg capture completed but did not produce a playable video stream")

    video = db.add_video(
        {
            "video_id": video_id,
            "filename": dest.name,
            "camera_id": source["camera_id"],
            "recorded_at": recorded_at,
            "path": str(dest),
            "status": "captured",
            "frame_interval_sec": frame_interval_sec,
        }
    )

    indexed_faces = None
    status = video["status"]
    if index:
        with _live_analysis_context():
            result = video_service.index_video(video_id, frame_interval_sec=frame_interval_sec)
        indexed_faces = result["indexed_faces"]
        status = result["status"]
        video = db.get_video(video_id) or video

    return {
        "source_id": source_id,
        "camera_id": source["camera_id"],
        "video": video,
        "indexed_faces": indexed_faces,
        "status": status,
    }


class _LiveMonitorWorker:
    def __init__(
        self,
        source_id: str,
        *,
        segment_sec: float,
        frame_interval_sec: float,
        update_person_index: bool,
        person_update_interval_segments: int,
        retention_hours: float | None,
        cleanup_interval_segments: int,
        merge_threshold: float | None,
        person_match_threshold: float,
        min_faces: int,
        min_face_area: float,
        min_detection_score: float,
    ) -> None:
        self.source_id = source_id
        self.segment_sec = max(1.0, min(float(segment_sec), 300.0))
        self.frame_interval_sec = max(0.1, min(float(frame_interval_sec), 60.0))
        self.update_person_index = bool(update_person_index)
        self.person_update_interval_segments = max(1, int(person_update_interval_segments))
        self.retention_hours = None if retention_hours is None else max(0.1, float(retention_hours))
        self.cleanup_interval_segments = max(1, int(cleanup_interval_segments))
        self.merge_threshold = None if merge_threshold is None else max(0.0, min(float(merge_threshold), 1.0))
        self.person_match_threshold = max(0.0, min(float(person_match_threshold), 1.0))
        self.min_faces = max(1, int(min_faces))
        self.min_face_area = max(1.0, float(min_face_area))
        self.min_detection_score = max(0.0, min(float(min_detection_score), 1.0))
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self._run, name=f"live-monitor-{source_id}", daemon=True)
        self.state: dict[str, Any] = {
            "source_id": source_id,
            "camera_id": None,
            "running": False,
            "stopping": False,
            "segment_sec": self.segment_sec,
            "frame_interval_sec": self.frame_interval_sec,
            "update_person_index": self.update_person_index,
            "person_update_interval_segments": self.person_update_interval_segments,
            "retention_hours": self.retention_hours,
            "cleanup_interval_segments": self.cleanup_interval_segments,
            "merge_threshold": self.merge_threshold,
            "person_match_threshold": self.person_match_threshold,
            "min_faces": self.min_faces,
            "min_face_area": self.min_face_area,
            "min_detection_score": self.min_detection_score,
            "started_at": None,
            "stopped_at": None,
            "last_capture_at": None,
            "last_video_id": None,
            "last_indexed_faces": None,
            "last_status": None,
            "last_person_update_at": None,
            "last_person_update_result": None,
            "last_cleanup_at": None,
            "last_cleanup_result": None,
            "processed_segments": 0,
            "failed_segments": 0,
            "last_error": None,
        }

    def start(self) -> None:
        with self.lock:
            self.state["running"] = True
            self.state["stopping"] = False
            self.state["started_at"] = _now_iso()
            self.state["stopped_at"] = None
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        with self.lock:
            if self.state["running"]:
                self.state["stopping"] = True

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return dict(self.state)

    def _merge_state(self, values: dict[str, Any]) -> None:
        with self.lock:
            self.state.update(values)

    def _cleanup_retention(self, camera_id: str) -> dict[str, Any] | None:
        if self.retention_hours is None:
            return None

        cutoff = _iso_from_dt(datetime.now(timezone.utc) - timedelta(hours=self.retention_hours))
        result = db.purge_live_videos(camera_id, before_created_at=cutoff)
        videos = result.pop("videos")
        touched_person_ids = set(result.get("touched_person_ids") or [])
        removed_video_files = 0
        removed_frame_dirs = 0
        for video in videos:
            video_path = Path(video["path"])
            if video_path.exists():
                video_path.unlink()
                removed_video_files += 1

            frame_dir = settings.frames_dir / video["video_id"]
            if frame_dir.exists():
                shutil.rmtree(frame_dir)
                removed_frame_dirs += 1

        result = result | {
            "camera_id": camera_id,
            "cutoff": cutoff,
            "removed_video_files": removed_video_files,
            "removed_frame_dirs": removed_frame_dirs,
        }

        if result["deleted_faces"] > 0 and self.update_person_index:
            with _analysis_lock:
                rebuild_result = person_service.rebuild_person_index(
                    merge_threshold=self.merge_threshold,
                    min_faces=self.min_faces,
                    min_face_area=self.min_face_area,
                    min_detection_score=self.min_detection_score,
                )
            result["rebuilt_person_index"] = rebuild_result
        elif touched_person_ids:
            from app.services import event_service

            result["refreshed_person_index"] = person_service.refresh_persons_from_remaining_faces(
                touched_person_ids
            )
            result["rebuilt_appearance_sessions"] = event_service.rebuild_appearance_sessions_for_persons(
                touched_person_ids
            )

        return result

    def _run(self) -> None:
        while not self.stop_event.is_set():
            captured_at = _now_iso()
            try:
                result = capture_live_source(
                    self.source_id,
                    duration_sec=self.segment_sec,
                    frame_interval_sec=self.frame_interval_sec,
                    index=True,
                    recorded_at=captured_at,
                )
                snapshot = self.snapshot()
                processed_segments = int(snapshot["processed_segments"]) + 1
                should_update_person_index = (
                    self.update_person_index
                    and processed_segments % self.person_update_interval_segments == 0
                )
                person_update_result = snapshot.get("last_person_update_result")
                person_update_at = snapshot.get("last_person_update_at")
                cleanup_result = snapshot.get("last_cleanup_result")
                cleanup_at = snapshot.get("last_cleanup_at")
                if should_update_person_index:
                    with _analysis_lock:
                        person_update_result = person_service.update_person_index(
                            merge_threshold=self.merge_threshold,
                            person_match_threshold=self.person_match_threshold,
                            min_faces=self.min_faces,
                            min_face_area=self.min_face_area,
                            min_detection_score=self.min_detection_score,
                        )
                    person_update_at = _now_iso()

                if processed_segments % self.cleanup_interval_segments == 0:
                    cleanup_result = self._cleanup_retention(result["camera_id"])
                    cleanup_at = _now_iso() if cleanup_result is not None else cleanup_at

                self._merge_state(
                    {
                        "camera_id": result["camera_id"],
                        "last_capture_at": captured_at,
                        "last_video_id": result["video"]["video_id"],
                        "last_indexed_faces": result["indexed_faces"],
                        "last_status": result["status"],
                        "last_person_update_at": person_update_at,
                        "last_person_update_result": person_update_result,
                        "last_cleanup_at": cleanup_at,
                        "last_cleanup_result": cleanup_result,
                        "processed_segments": processed_segments,
                        "last_error": None,
                    }
                )
            except Exception as exc:
                self._merge_state(
                    {
                        "last_capture_at": captured_at,
                        "last_status": "failed",
                        "failed_segments": self.snapshot()["failed_segments"] + 1,
                        "last_error": str(exc),
                    }
                )
                self.stop_event.wait(min(5.0, self.segment_sec))

        self._merge_state({"running": False, "stopping": False, "stopped_at": _now_iso()})


def start_live_monitor(
    source_id: str,
    *,
    segment_sec: float = 10.0,
    frame_interval_sec: float = 1.0,
    update_person_index: bool = True,
    person_update_interval_segments: int = 3,
    retention_hours: float | None = 24.0,
    cleanup_interval_segments: int = 360,
    merge_threshold: float | None = 0.80,
    person_match_threshold: float = 0.82,
    min_faces: int = 4,
    min_face_area: float = 1800.0,
    min_detection_score: float = 0.75,
) -> dict[str, Any]:
    source = db.get_live_source(source_id)
    if not source:
        raise KeyError(f"source_id not found: {source_id}")
    if not source.get("enabled", True):
        raise RuntimeError(f"live source is disabled: {source_id}")

    with _workers_lock:
        existing = _workers.get(source_id)
        if existing and (
            existing.snapshot().get("running")
            or existing.snapshot().get("stopping")
            or existing.thread.is_alive()
        ):
            return existing.snapshot()

        worker = _LiveMonitorWorker(
            source_id,
            segment_sec=segment_sec,
            frame_interval_sec=frame_interval_sec,
            update_person_index=update_person_index,
            person_update_interval_segments=person_update_interval_segments,
            retention_hours=retention_hours,
            cleanup_interval_segments=cleanup_interval_segments,
            merge_threshold=merge_threshold,
            person_match_threshold=person_match_threshold,
            min_faces=min_faces,
            min_face_area=min_face_area,
            min_detection_score=min_detection_score,
        )
        worker._merge_state({"camera_id": source["camera_id"]})
        _workers[source_id] = worker
        worker.start()
        return worker.snapshot()


def stop_live_monitor(source_id: str) -> dict[str, Any]:
    with _workers_lock:
        worker = _workers.get(source_id)
    if not worker:
        source = db.get_live_source(source_id)
        return {
            "source_id": source_id,
            "camera_id": source["camera_id"] if source else None,
            "running": False,
            "processed_segments": 0,
            "failed_segments": 0,
        }

    worker.stop()
    worker.thread.join(timeout=max(5.0, min(worker.segment_sec + 2.0, 30.0)))
    snapshot = worker.snapshot()
    if not worker.thread.is_alive():
        with _workers_lock:
            if _workers.get(source_id) is worker:
                _workers.pop(source_id, None)
    return snapshot


def live_monitor_status(source_id: str) -> dict[str, Any]:
    with _workers_lock:
        worker = _workers.get(source_id)
    if worker:
        return worker.snapshot()

    source = db.get_live_source(source_id)
    if not source:
        raise KeyError(f"source_id not found: {source_id}")
    return {
        "source_id": source_id,
        "camera_id": source["camera_id"],
        "running": False,
        "processed_segments": 0,
        "failed_segments": 0,
    }


def list_live_monitors() -> list[dict[str, Any]]:
    with _workers_lock:
        return [worker.snapshot() for worker in _workers.values()]


def stop_all_live_monitors() -> None:
    with _workers_lock:
        workers = list(_workers.values())
    for worker in workers:
        worker.stop()
    for worker in workers:
        worker.thread.join(timeout=1.0)
