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
