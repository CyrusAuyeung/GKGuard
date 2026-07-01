from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

pytest.importorskip("cv2")

from app.services import event_service  # noqa: E402


def test_body_only_event_bucket_is_mergeable_for_adjacent_observations():
    first = {
        "observation_id": "obs_1",
        "camera_id": "cam_1",
        "video_id": "video_1",
        "person_bbox": {"x1": 100, "y1": 100, "x2": 180, "y2": 260},
    }
    second = {
        "observation_id": "obs_2",
        "camera_id": "cam_1",
        "video_id": "video_1",
        "person_bbox": {"x1": 108, "y1": 102, "x2": 188, "y2": 262},
    }

    assert event_service._event_bucket_key(first) == event_service._event_bucket_key(second)


def test_face_estimated_upper_color_conflict_still_blocks_event_merge(monkeypatch):
    monkeypatch.setattr(
        event_service.settings,
        "enable_upper_color_backend_for_face_estimated_body",
        False,
    )
    first = {
        "camera_id": "cam_1",
        "video_id": "video_1",
        "video_timestamp_sec": 1.0,
        "person_bbox": {"x1": 100, "y1": 100, "x2": 180, "y2": 260},
        "body_model_version": "face_estimated_body_v1",
        "upper_visible": True,
        "upper_color": "black",
    }
    second = {
        "camera_id": "cam_1",
        "video_id": "video_1",
        "video_timestamp_sec": 2.0,
        "person_bbox": {"x1": 104, "y1": 102, "x2": 184, "y2": 262},
        "body_model_version": "face_estimated_body_v1",
        "upper_visible": True,
        "upper_color": "white",
    }

    assert event_service._can_merge(first, second) is False


def test_detector_upper_color_conflict_blocks_event_merge(monkeypatch):
    monkeypatch.setattr(
        event_service.settings,
        "enable_upper_color_backend_for_face_estimated_body",
        False,
    )
    first = {
        "camera_id": "cam_1",
        "video_id": "video_1",
        "video_timestamp_sec": 1.0,
        "person_bbox": {"x1": 100, "y1": 100, "x2": 180, "y2": 260},
        "body_model_version": "opencv_hog_v1",
        "upper_visible": True,
        "upper_color": "black",
    }
    second = {
        "camera_id": "cam_1",
        "video_id": "video_1",
        "video_timestamp_sec": 2.0,
        "person_bbox": {"x1": 104, "y1": 102, "x2": 184, "y2": 262},
        "body_model_version": "opencv_hog_v1",
        "upper_visible": True,
        "upper_color": "white",
    }

    assert event_service._can_merge(first, second) is False
