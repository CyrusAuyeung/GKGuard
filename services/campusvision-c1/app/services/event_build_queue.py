from __future__ import annotations

from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor, wait
from datetime import datetime
import logging
import threading
import uuid
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.services import event_service


LOGGER = logging.getLogger(__name__)

_EXECUTOR_LOCK = threading.Lock()
_EXECUTOR: ThreadPoolExecutor | None = None
_PENDING: dict[str, Future[dict[str, Any]]] = {}
_COMPLETED: deque[dict[str, Any]] = deque(maxlen=200)


def _utc_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _get_executor() -> ThreadPoolExecutor:
    global _EXECUTOR
    with _EXECUTOR_LOCK:
        if _EXECUTOR is None:
            workers = max(1, int(settings.event_build_worker_count or 1))
            _EXECUTOR = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="c1-event-build")
        return _EXECUTOR


def _rebuild_video_events(job_id: str, video_id: str, db_path: str) -> dict[str, Any]:
    if str(Path(settings.db_path)) != db_path:
        LOGGER.warning(
            "event build job %s started after db_path changed: queued=%s current=%s",
            job_id,
            db_path,
            settings.db_path,
        )
    started_at = _utc_now()
    result = event_service.rebuild_events_for_video(video_id)
    return {
        "job_id": job_id,
        "mode": "async",
        "status": "done",
        "video_id": video_id,
        "started_at": started_at,
        "finished_at": _utc_now(),
        "result": result,
    }


def _record_completion(job_id: str, video_id: str, future: Future[dict[str, Any]]) -> None:
    with _EXECUTOR_LOCK:
        _PENDING.pop(job_id, None)
    try:
        _COMPLETED.append(future.result())
    except Exception as exc:
        LOGGER.exception("event build job %s failed for video %s", job_id, video_id)
        _COMPLETED.append(
            {
                "job_id": job_id,
                "mode": "async",
                "status": "failed",
                "video_id": video_id,
                "finished_at": _utc_now(),
                "error": f"{type(exc).__name__}: {exc}",
            }
        )


def enqueue_video_event_rebuild(video_id: str) -> dict[str, Any]:
    job_id = "event_build_" + uuid.uuid4().hex
    db_path = str(Path(settings.db_path))
    future = _get_executor().submit(_rebuild_video_events, job_id, video_id, db_path)
    with _EXECUTOR_LOCK:
        _PENDING[job_id] = future
    future.add_done_callback(lambda item: _record_completion(job_id, video_id, item))
    return {
        "job_id": job_id,
        "mode": "async",
        "status": "queued",
        "video_id": video_id,
        "queued_at": _utc_now(),
    }


def wait_for_idle(timeout: float | None = None) -> dict[str, Any]:
    with _EXECUTOR_LOCK:
        futures = list(_PENDING.values())
    if futures:
        wait(futures, timeout=timeout)
    with _EXECUTOR_LOCK:
        pending_count = len(_PENDING)
    return {
        "pending": pending_count,
        "completed_recent": len(_COMPLETED),
        "completed": list(_COMPLETED),
    }


def queue_status() -> dict[str, Any]:
    with _EXECUTOR_LOCK:
        pending = [
            {
                "job_id": job_id,
                "done": future.done(),
            }
            for job_id, future in _PENDING.items()
        ]
    return {
        "pending": pending,
        "pending_count": len(pending),
        "completed_recent": list(_COMPLETED),
    }
