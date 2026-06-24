from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

pytest.importorskip("cv2")

from app.services import live_service  # noqa: E402


def test_start_live_monitor_does_not_replace_stopping_worker(monkeypatch):
    class Worker:
        def __init__(self):
            self.thread = self

        def snapshot(self):
            return {"source_id": "source_1", "running": False, "stopping": True}

        def is_alive(self):
            return True

    worker = Worker()
    monkeypatch.setitem(live_service._workers, "source_1", worker)
    monkeypatch.setattr(
        live_service.db,
        "get_live_source",
        lambda source_id: {"source_id": source_id, "camera_id": "cam_1", "enabled": True},
    )

    result = live_service.start_live_monitor("source_1")

    assert result["stopping"] is True
    assert live_service._workers["source_1"] is worker


def test_cleanup_retention_refreshes_people_when_index_update_is_disabled(monkeypatch):
    worker = live_service._LiveMonitorWorker(
        "source_1",
        segment_sec=10,
        frame_interval_sec=1,
        update_person_index=False,
        person_update_interval_segments=3,
        retention_hours=1,
        cleanup_interval_segments=1,
        merge_threshold=0.8,
        person_match_threshold=0.82,
        min_faces=4,
        min_face_area=1800,
        min_detection_score=0.75,
    )
    monkeypatch.setattr(
        live_service.db,
        "purge_live_videos",
        lambda *_args, **_kwargs: {
            "deleted_videos": 1,
            "deleted_faces": 2,
            "deleted_person_faces": 2,
            "deleted_observations": 2,
            "deleted_events": 1,
            "deleted_event_observations": 1,
            "touched_person_ids": ["person_1"],
            "videos": [],
        },
    )
    monkeypatch.setattr(
        live_service.person_service,
        "refresh_persons_from_remaining_faces",
        lambda person_ids: {"persons": len(person_ids), "refreshed": 1, "deleted": 0},
    )

    from app.services import event_service

    monkeypatch.setattr(
        event_service,
        "rebuild_appearance_sessions_for_persons",
        lambda person_ids: {"persons": len(person_ids), "sessions": 1, "updated_events": 1},
    )

    result = worker._cleanup_retention("cam_1")

    assert result["refreshed_person_index"]["refreshed"] == 1
    assert result["rebuilt_appearance_sessions"]["sessions"] == 1
