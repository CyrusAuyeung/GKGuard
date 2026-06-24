from pathlib import Path

import cv2
import numpy as np

from app.api import routes


def _resolve_snapshot_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return routes.settings.data_dir / path


def test_snapshot_manual_samples_writes_frame_body_and_face(monkeypatch, tmp_path):
    frame = np.full((120, 90, 3), 220, dtype=np.uint8)
    frame_path = tmp_path / "frame.jpg"
    assert cv2.imwrite(str(frame_path), frame)

    event = {
        "event_id": "event_1",
        "representative_observation_id": "obs_1",
        "representative_face_id": "face_1",
        "representative_frame_path": str(frame_path),
    }
    observation = {
        "observation_id": "obs_1",
        "frame_path": str(frame_path),
        "person_bbox": {"x1": 10, "y1": 12, "x2": 70, "y2": 110},
        "face_record_id": "face_1",
    }
    face = {
        "face_id": "face_1",
        "frame_path": str(frame_path),
        "bbox": {"x1": 25, "y1": 20, "x2": 50, "y2": 52},
    }

    monkeypatch.setattr(routes, "_MANUAL_SAMPLE_SNAPSHOT_DIR", tmp_path / "snapshots")
    monkeypatch.setattr(routes.db, "get_event", lambda event_id: event if event_id == "event_1" else None)
    monkeypatch.setattr(
        routes.db,
        "get_person_observation",
        lambda observation_id: observation if observation_id == "obs_1" else None,
    )
    monkeypatch.setattr(routes.db, "get_face_record", lambda face_id: face if face_id == "face_1" else None)

    snapshots = routes._snapshot_manual_samples(
        "manual_event_outfit_groups",
        "person_1",
        [{"event_id": "event_1", "observation_id": "obs_1", "manual_group": "A"}],
    )

    assert len(snapshots) == 1
    snapshot = snapshots[0]
    assert snapshot["snapshot_available"] is True
    assert snapshot["manual_group"] == "A"
    assert _resolve_snapshot_path(snapshot["snapshot_frame_path"]).is_file()
    assert _resolve_snapshot_path(snapshot["snapshot_body_path"]).is_file()
    assert _resolve_snapshot_path(snapshot["snapshot_face_path"]).is_file()
