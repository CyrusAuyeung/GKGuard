from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

pytest.importorskip("cv2")

from app.services import event_service  # noqa: E402


def _event(
    index: int,
    *,
    upper_color: str,
    upper_confidence: float,
    lower_color: str = "black",
    lower_confidence: float = 0.9,
) -> dict:
    return {
        "event_id": f"event_{index}",
        "person_id": "person_1",
        "camera_id": "cam_1",
        "video_id": "video_1",
        "start_timestamp_sec": float(index * 10),
        "end_timestamp_sec": float(index * 10 + 5),
        "raw_upper_color": upper_color,
        "raw_upper_color_confidence": upper_confidence,
        "raw_upper_visible": upper_color != "unknown",
        "raw_lower_color": lower_color,
        "raw_lower_color_confidence": lower_confidence,
        "raw_lower_visible": lower_color != "unknown",
    }


def test_low_confidence_event_color_uses_session_profile(monkeypatch):
    monkeypatch.setattr(event_service.settings, "appearance_session_min_support", 2)
    monkeypatch.setattr(event_service.settings, "appearance_session_profile_confidence", 0.58)
    monkeypatch.setattr(event_service.settings, "appearance_session_low_confidence_threshold", 0.55)

    events = [
        _event(1, upper_color="black", upper_confidence=0.92),
        _event(2, upper_color="black", upper_confidence=0.88),
        _event(3, upper_color="blue", upper_confidence=0.31),
    ]

    profile = event_service._session_profile(events)
    normalized, reason = event_service._normalize_part(events[-1], profile, "upper")

    assert profile["upper"]["color"] == "black"
    assert normalized["color"] == "black"
    assert reason["action"] == "override_low_confidence_with_appearance_session"


def test_event_color_confidence_keeps_absolute_source_confidence(monkeypatch):
    monkeypatch.setattr(event_service.settings, "upper_color_confidence_threshold", 0.35)

    color, confidence, visible = event_service._aggregate_color(
        [
            {
                "upper_visible": True,
                "upper_color": "blue",
                "upper_color_confidence": 0.42,
                "upper_valid_pixel_ratio": 1.0,
            }
        ],
        "upper",
    )

    assert color == "blue"
    assert confidence == 0.42
    assert visible is True


def test_session_profile_confidence_keeps_absolute_event_confidence():
    profile = event_service._session_profile(
        [
            _event(1, upper_color="blue", upper_confidence=0.42),
            _event(2, upper_color="blue", upper_confidence=0.40),
        ]
    )

    assert profile["upper"]["color"] == "blue"
    assert profile["upper"]["confidence"] == 0.41


def test_unobserved_clothing_part_is_not_filled_from_session_profile(monkeypatch):
    monkeypatch.setattr(event_service.settings, "enable_lower_clothing_core", True)
    monkeypatch.setattr(event_service.settings, "appearance_session_min_support", 2)
    monkeypatch.setattr(event_service.settings, "appearance_session_profile_confidence", 0.58)

    events = [
        _event(1, upper_color="black", upper_confidence=0.92, lower_color="blue"),
        _event(2, upper_color="black", upper_confidence=0.88, lower_color="blue"),
        _event(3, upper_color="black", upper_confidence=0.91, lower_color="unknown"),
    ]

    profile = event_service._session_profile(events)
    normalized, reason = event_service._normalize_part(events[-1], profile, "lower")

    assert profile["lower"]["color"] == "blue"
    assert normalized["color"] == "unknown"
    assert normalized["visible"] is False
    assert reason["action"] == "keep_unobserved"


def test_lower_clothing_is_not_core_profile_by_default(monkeypatch):
    monkeypatch.setattr(event_service.settings, "enable_lower_clothing_core", False)
    events = [
        _event(1, upper_color="black", upper_confidence=0.92, lower_color="blue"),
        _event(2, upper_color="black", upper_confidence=0.88, lower_color="blue"),
    ]

    profile = event_service._session_profile(events)
    normalized, reason = event_service._normalize_part(events[0], profile, "lower")

    assert profile["upper"]["color"] == "black"
    assert profile["lower"]["color"] == "unknown"
    assert profile["lower"]["visible"] is False
    assert normalized == {"color": "unknown", "confidence": None, "visible": False}
    assert reason["action"] == "ignore_lower_clothing_core_disabled"


def test_event_keeps_raw_lower_but_core_lower_is_disabled(monkeypatch):
    monkeypatch.setattr(event_service.settings, "enable_lower_clothing_core", False)
    monkeypatch.setattr(event_service.settings, "lower_color_confidence_threshold", 0.35)
    event = event_service._event_from_observations(
        [
            {
                "observation_id": "obs_1",
                "camera_id": "cam_1",
                "video_id": "video_1",
                "video_timestamp_sec": 1.0,
                "frame_path": "/tmp/frame.jpg",
                "person_bbox": {"x1": 0, "y1": 0, "x2": 100, "y2": 200},
                "upper_visible": True,
                "upper_color": "black",
                "upper_color_confidence": 0.9,
                "upper_valid_pixel_ratio": 1.0,
                "lower_visible": True,
                "lower_color": "blue",
                "lower_color_confidence": 0.9,
                "lower_valid_pixel_ratio": 1.0,
            }
        ]
    )

    assert event["lower_color"] == "unknown"
    assert event["lower_visible"] is False
    assert event["raw_lower_color"] == "blue"
    assert event["raw_lower_visible"] is True


def test_high_confidence_partial_clothing_change_starts_new_session(monkeypatch):
    monkeypatch.setattr(event_service.settings, "appearance_session_min_support", 2)
    monkeypatch.setattr(event_service.settings, "appearance_session_profile_confidence", 0.58)
    monkeypatch.setattr(event_service.settings, "appearance_session_change_confidence", 0.82)

    groups = event_service._appearance_session_groups(
        [
            _event(1, upper_color="black", upper_confidence=0.92, lower_color="black"),
            _event(2, upper_color="black", upper_confidence=0.88, lower_color="black"),
            _event(3, upper_color="white", upper_confidence=0.91, lower_color="black"),
        ]
    )

    assert len(groups) == 2
    assert [event["event_id"] for event in groups[0]] == ["event_1", "event_2"]
    assert [event["event_id"] for event in groups[1]] == ["event_3"]
