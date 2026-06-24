from __future__ import annotations

import importlib
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_api_key_prefers_campusvision_api_key(monkeypatch) -> None:
    monkeypatch.setenv("CAMPUSVISION_API_KEY", "primary-token")
    monkeypatch.setenv("C1_API_KEY", "fallback-token")

    import app.core.config as config

    reloaded = importlib.reload(config)

    assert reloaded.settings.api_key == "primary-token"


def test_api_key_falls_back_to_c1_api_key(monkeypatch) -> None:
    monkeypatch.delenv("CAMPUSVISION_API_KEY", raising=False)
    monkeypatch.setenv("C1_API_KEY", "fallback-token")

    import app.core.config as config

    reloaded = importlib.reload(config)

    assert reloaded.settings.api_key == "fallback-token"


def test_api_key_required_for_sensitive_read_paths() -> None:
    from app.api.security import c1_api_key_required_for_path

    for path in (
        "/api/v1/persons",
        "/api/v1/persons/gallery",
        "/api/v1/searches/search001",
        "/api/v1/media/frame/face001",
        "/api/v1/media/face/face001",
        "/api/v1/query/person-attributes",
        "/api/v1/live-sources/source001/status",
        "/api/v1/events/event001",
        "/api/v1/records",
        "/api/v1/videos",
        "/api/v1/videos/video001",
    ):
        assert c1_api_key_required_for_path(path, "GET")


def test_api_key_required_for_camera_metadata_mutation() -> None:
    from app.api.security import c1_api_key_required_for_path

    assert c1_api_key_required_for_path("/api/v1/cameras", "POST")


def test_api_key_not_required_for_public_health() -> None:
    from app.api.security import c1_api_key_required_for_path

    assert not c1_api_key_required_for_path("/health", "GET")
    assert not c1_api_key_required_for_path("/api/v2/videos", "GET")


def test_delete_face_records_by_ids_preserves_existing_video_records(monkeypatch, tmp_path: Path) -> None:
    from app.core.config import settings
    from app.storage import db

    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(settings, "uploads_dir", tmp_path / "uploads")
    monkeypatch.setattr(settings, "video_uploads_dir", tmp_path / "uploads" / "videos")
    monkeypatch.setattr(settings, "query_uploads_dir", tmp_path / "uploads" / "query_images")
    monkeypatch.setattr(settings, "frames_dir", tmp_path / "frames")
    monkeypatch.setattr(settings, "db_path", tmp_path / "campusvision.sqlite3")

    db.init_db()
    frame_path = str(tmp_path / "frame.jpg")
    face_record = {
        "video_id": "video-001",
        "camera_id": "cam-001",
        "frame_path": frame_path,
        "video_timestamp_sec": 1.0,
        "captured_at": "2026-06-22T10:00:00Z",
        "bbox": {"x1": 1, "y1": 2, "x2": 30, "y2": 40},
        "embedding": [1.0, 0.0, 0.0],
    }
    db.add_face_record({"face_id": "old-face", **face_record})
    db.add_face_record({"face_id": "new-face", **face_record, "video_timestamp_sec": 2.0})
    db.add_person(
        {
            "person_id": "person-001",
            "representative_face_id": "old-face",
            "representative_frame_path": frame_path,
            "embedding": [1.0, 0.0, 0.0],
            "face_count": 2,
        }
    )
    db.add_person_face("person-001", "old-face", 0.99)
    db.add_person_face("person-001", "new-face", 0.88)

    db.delete_face_records_by_ids(["new-face"])

    assert db.get_face_record("old-face") is not None
    assert db.get_face_record("new-face") is None
    with db.get_conn() as conn:
        remaining_faces = [
            row["face_id"]
            for row in conn.execute("SELECT face_id FROM person_faces ORDER BY face_id").fetchall()
        ]
    assert remaining_faces == ["old-face"]


def _configure_temp_db(monkeypatch, tmp_path: Path) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(settings, "uploads_dir", tmp_path / "uploads")
    monkeypatch.setattr(settings, "video_uploads_dir", tmp_path / "uploads" / "videos")
    monkeypatch.setattr(settings, "query_uploads_dir", tmp_path / "uploads" / "query_images")
    monkeypatch.setattr(settings, "frames_dir", tmp_path / "frames")
    monkeypatch.setattr(settings, "db_path", tmp_path / "campusvision.sqlite3")


def _seed_event_with_observation(db, frame_path: str) -> None:
    db.add_face_record(
        {
            "face_id": "face-001",
            "video_id": "video-001",
            "camera_id": "cam-001",
            "frame_path": frame_path,
            "video_timestamp_sec": 1.0,
            "captured_at": "2026-06-22T10:00:00",
            "bbox": {"x1": 1, "y1": 2, "x2": 30, "y2": 40},
            "embedding": [1.0, 0.0, 0.0],
            "observation_id": "obs-001",
        }
    )
    observation = db.add_person_observation(
        {
            "observation_id": "obs-001",
            "camera_id": "cam-001",
            "video_id": "video-001",
            "frame_index": 1,
            "video_timestamp_sec": 1.0,
            "captured_at": "2026-06-22T10:00:00",
            "frame_path": frame_path,
            "observation_type": "face_body",
            "body_visibility": "upper_body",
            "person_bbox": {"x1": 4, "y1": 8, "x2": 44, "y2": 88},
            "face_record_id": "face-001",
            "person_id": "person-001",
            "upper_color": "black",
            "upper_color_confidence": 0.9,
            "upper_visible": True,
        }
    )
    db.add_event(
        {
            "event_id": "event-001",
            "camera_id": "cam-001",
            "video_id": "video-001",
            "person_id": "person-001",
            "start_time": "2026-06-22T10:00:00",
            "end_time": "2026-06-22T10:00:01",
            "start_timestamp_sec": 1.0,
            "end_timestamp_sec": 1.0,
            "observation_count": 1,
            "face_count": 1,
            "representative_observation_id": "obs-001",
            "representative_face_id": "face-001",
            "representative_frame_path": frame_path,
            "upper_color": "black",
            "upper_color_confidence": 0.9,
            "upper_visible": True,
        },
        [observation],
    )


def test_list_events_batches_representative_observations(monkeypatch, tmp_path: Path) -> None:
    from app.storage import db

    _configure_temp_db(monkeypatch, tmp_path)
    db.init_db()
    _seed_event_with_observation(db, str(tmp_path / "frame.jpg"))

    def fail_get_observation(_observation_id: str):
        raise AssertionError("list_events should batch-load representative observations")

    monkeypatch.setattr(db, "get_person_observation", fail_get_observation)

    events = db.list_events()
    scan_events = db.list_events(include_representative_observation=False)

    assert events[0]["representative_body_crop_url"] == "/api/v1/media/event/body/event-001"
    assert events[0]["body_visibility"] == "upper_body"
    assert scan_events[0]["representative_body_crop_url"] is None


def test_list_events_can_scan_latest_events_first(monkeypatch, tmp_path: Path) -> None:
    from app.storage import db

    _configure_temp_db(monkeypatch, tmp_path)
    db.init_db()
    _seed_event_with_observation(db, str(tmp_path / "frame.jpg"))
    db.add_event(
        {
            "event_id": "event-002",
            "camera_id": "cam-001",
            "video_id": "video-002",
            "person_id": "person-002",
            "start_time": "2026-06-23T10:00:00",
            "end_time": "2026-06-23T10:00:01",
            "start_timestamp_sec": 1.0,
            "end_timestamp_sec": 1.0,
            "observation_count": 0,
            "face_count": 0,
        },
        [],
    )

    assert [event["event_id"] for event in db.list_events(limit=2)] == ["event-001", "event-002"]
    assert [event["event_id"] for event in db.list_events(limit=2, latest_first=True)] == [
        "event-002",
        "event-001",
    ]


def test_delete_person_observations_for_video_cleans_rollback_artifacts(monkeypatch, tmp_path: Path) -> None:
    from app.storage import db

    _configure_temp_db(monkeypatch, tmp_path)
    db.init_db()
    _seed_event_with_observation(db, str(tmp_path / "frame.jpg"))

    touched = db.delete_person_observations_for_video("video-001")

    assert touched == {"person-001"}
    assert db.get_person_observation("obs-001") is None
    assert db.get_face_record("face-001")["observation_id"] is None
    with db.get_conn() as conn:
        remaining_links = conn.execute("SELECT COUNT(*) AS count FROM event_observations").fetchone()["count"]
    assert remaining_links == 0


def test_person_events_route_honors_limit_without_loading_vision_dependencies() -> None:
    route_source = (Path(__file__).resolve().parents[1] / "app" / "api" / "routes.py").read_text(
        encoding="utf-8"
    )

    assert "limit: int = Query(100, ge=1, le=5000)" in route_source
    assert "event_service.list_events(person_id=person_id, limit=limit)" in route_source
    assert "person_service.person_events(person_id, max_gap_sec=max_gap_sec)[:limit]" in route_source


def test_attribute_query_rehydrates_page_media_after_scan_without_loading_vision_dependencies() -> None:
    service_source = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "services"
        / "person_attribute_query_service.py"
    ).read_text(encoding="utf-8")

    assert "include_representative_observation=False" in service_source
    assert "latest_first=True" in service_source
    assert "def _hydrate_page_media" in service_source
    assert "event = db.get_event(str(event_id))" in service_source
    assert "_hydrate_page_media(page)" in service_source


def test_attribute_query_matches_requested_unknown_choice() -> None:
    from app.services import person_attribute_query_service

    score, failure = person_attribute_query_service._choice_condition(
        field="glasses_status",
        expected=["unknown"],
        actual="unknown",
    )

    assert score == 1.0
    assert failure is None


def test_face_image_query_uses_upload_limit_guard() -> None:
    route_source = (Path(__file__).resolve().parents[1] / "app" / "api" / "routes.py").read_text(encoding="utf-8")
    route_segment = route_source.split('@router.post("/query/face-image")', 1)[1].split(
        '@router.post("/query/person-attributes")',
        1,
    )[0]

    assert "_validate_query_upload_count(files)" in route_segment
    assert "except search_service.QueryImageTooLarge" in route_segment
    assert "_cleanup_query_uploads(paths, temp_search_id)" in route_segment


def test_manual_live_capture_stamps_recorded_at() -> None:
    route_source = (Path(__file__).resolve().parents[1] / "app" / "api" / "routes.py").read_text(encoding="utf-8")
    route_segment = route_source.split('@router.post("/live-sources/{source_id}/capture"', 1)[1].split(
        '@router.post("/live-sources/{source_id}/monitor/start"',
        1,
    )[0]

    assert "recorded_at: Optional[str] = None" in route_segment
    assert "capture_recorded_at = recorded_at or datetime.now(timezone.utc)" in route_segment
    assert "recorded_at=capture_recorded_at" in route_segment
