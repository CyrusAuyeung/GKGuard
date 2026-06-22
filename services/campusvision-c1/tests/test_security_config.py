from __future__ import annotations

import importlib
from pathlib import Path


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
    assert not c1_api_key_required_for_path("/api/v1/videos-extra", "GET")


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
