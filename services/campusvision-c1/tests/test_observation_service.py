from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services import observation_service  # noqa: E402


def _capture_observations(monkeypatch):
    observations = []

    def add_person_observation(payload):
        observations.append(payload)
        return payload

    def add_person_observations(payloads):
        observations.extend(payloads)
        return payloads

    monkeypatch.setattr(observation_service.db, "add_person_observation", add_person_observation)
    monkeypatch.setattr(observation_service.db, "add_person_observations", add_person_observations)
    monkeypatch.setattr(observation_service.db, "update_face_record_observation", lambda *_args, **_kwargs: None)
    return observations


def test_unmatched_face_uses_estimated_body_when_torso_space_exists(monkeypatch):
    observations = _capture_observations(monkeypatch)
    image = np.zeros((220, 120, 3), dtype=np.uint8)
    face = {"face_id": "face_1", "x1": 45, "y1": 16, "x2": 75, "y2": 46, "score": 0.92}

    def analyze_clothing(_frame, _body, _visibility, **_kwargs):
        return {
            "upper_color": "white",
            "upper_color_confidence": 0.8,
            "upper_visible": True,
            "upper_valid_pixel_ratio": 1.0,
            "lower_color": "unknown",
            "lower_color_confidence": None,
            "lower_visible": False,
            "lower_valid_pixel_ratio": None,
        }

    monkeypatch.setattr(observation_service.person_analysis, "analyze_clothing", analyze_clothing)

    observation_service.create_frame_observations(
        frame=image,
        video_id="video_1",
        camera_id="camera_1",
        frame_path="/tmp/frame.jpg",
        video_timestamp_sec=1.0,
        captured_at=None,
        frame_index=1,
        faces=[face],
        bodies=[],
    )

    assert len(observations) == 1
    observation = observations[0]
    assert observation["observation_type"] == "face_and_body"
    assert observation["body_visibility"] == "upper_body"
    assert observation["body_model_version"] == observation_service.ESTIMATED_BODY_MODEL_VERSION
    assert observation["person_bbox"]["estimated_from_face"] is True
    assert observation["upper_visible"] is True
    assert observation["upper_color"] == "white"


def test_unmatched_close_face_remains_face_only_unknown(monkeypatch):
    observations = _capture_observations(monkeypatch)
    image = np.zeros((80, 120, 3), dtype=np.uint8)
    face = {"face_id": "face_1", "x1": 45, "y1": 35, "x2": 75, "y2": 65, "score": 0.92}

    observation_service.create_frame_observations(
        frame=image,
        video_id="video_1",
        camera_id="camera_1",
        frame_path="/tmp/frame.jpg",
        video_timestamp_sec=1.0,
        captured_at=None,
        frame_index=1,
        faces=[face],
        bodies=[],
    )

    assert len(observations) == 1
    observation = observations[0]
    assert observation["observation_type"] == "face_only"
    assert observation["body_visibility"] == "face_only"
    assert observation["person_bbox"] is None
    assert observation["upper_visible"] is False
    assert observation["upper_color"] == "unknown"


def test_face_estimated_body_can_skip_expensive_upper_backend(monkeypatch):
    observations = _capture_observations(monkeypatch)
    image = np.zeros((220, 120, 3), dtype=np.uint8)
    face = {"face_id": "face_1", "x1": 45, "y1": 16, "x2": 75, "y2": 46, "score": 0.92}

    def classify_upper_colors(_frame, _body_boxes):
        raise AssertionError("face-estimated body should use the lightweight rule path")

    monkeypatch.setattr(observation_service.settings, "upper_color_backend", "clip_schp")
    monkeypatch.setattr(
        observation_service.settings,
        "enable_upper_color_backend_for_face_estimated_body",
        False,
    )
    monkeypatch.setattr(
        observation_service.person_analysis,
        "_classify_upper_colors_with_backend",
        classify_upper_colors,
    )

    observation_service.create_frame_observations(
        frame=image,
        video_id="video_1",
        camera_id="camera_1",
        frame_path="/tmp/frame.jpg",
        video_timestamp_sec=1.0,
        captured_at=None,
        frame_index=1,
        faces=[face],
        bodies=[],
    )

    assert len(observations) == 1
    assert observations[0]["body_model_version"] == observation_service.ESTIMATED_BODY_MODEL_VERSION
    assert observations[0]["upper_color"] == "black"


def test_frame_observations_batch_upper_color_for_multiple_bodies(monkeypatch):
    observations = _capture_observations(monkeypatch)
    image = np.zeros((220, 180, 3), dtype=np.uint8)
    bodies = [
        {"x1": 10, "y1": 10, "x2": 70, "y2": 190, "score": 0.9},
        {"x1": 95, "y1": 12, "x2": 160, "y2": 195, "score": 0.88},
    ]
    calls = []

    def classify_upper_colors(_frame, body_boxes):
        calls.append(list(body_boxes))
        return [
            observation_service.person_analysis.RegionResult("black", 0.8, True, 1.0),
            observation_service.person_analysis.RegionResult("white", 0.7, True, 1.0),
        ]

    monkeypatch.setattr(observation_service.settings, "upper_color_backend", "clip_schp")
    monkeypatch.setattr(
        observation_service.person_analysis,
        "_classify_upper_colors_with_backend",
        classify_upper_colors,
    )

    observation_service.create_frame_observations(
        frame=image,
        video_id="video_1",
        camera_id="camera_1",
        frame_path="/tmp/frame.jpg",
        video_timestamp_sec=1.0,
        captured_at=None,
        frame_index=1,
        faces=[],
        bodies=bodies,
    )

    assert len(calls) == 1
    assert calls[0] == bodies
    assert [item["upper_color"] for item in observations] == ["black", "white"]


def test_upper_color_temporal_cache_reuses_overlapping_body(monkeypatch):
    observations = _capture_observations(monkeypatch)
    image = np.zeros((220, 180, 3), dtype=np.uint8)
    cache = observation_service.UpperColorTemporalCache(max_age_sec=2.5, iou_threshold=0.50)
    calls = []

    def classify_upper_colors(_frame, body_boxes):
        calls.append(list(body_boxes))
        return [
            observation_service.person_analysis.RegionResult("black", 0.8, True, 1.0)
            for _body in body_boxes
        ]

    monkeypatch.setattr(observation_service.settings, "upper_color_backend", "clip_schp")
    monkeypatch.setattr(observation_service.settings, "enable_upper_color_temporal_cache", True)
    monkeypatch.setattr(
        observation_service.person_analysis,
        "_classify_upper_colors_with_backend",
        classify_upper_colors,
    )

    observation_service.create_frame_observations(
        frame=image,
        video_id="video_1",
        camera_id="camera_1",
        frame_path="/tmp/frame1.jpg",
        video_timestamp_sec=1.0,
        captured_at=None,
        frame_index=1,
        faces=[],
        bodies=[{"x1": 10, "y1": 10, "x2": 70, "y2": 190, "score": 0.9, "detector": "opencv_hog"}],
        upper_color_cache=cache,
    )
    observation_service.create_frame_observations(
        frame=image,
        video_id="video_1",
        camera_id="camera_1",
        frame_path="/tmp/frame2.jpg",
        video_timestamp_sec=2.0,
        captured_at=None,
        frame_index=2,
        faces=[],
        bodies=[{"x1": 12, "y1": 12, "x2": 72, "y2": 192, "score": 0.9, "detector": "opencv_hog"}],
        upper_color_cache=cache,
    )

    assert len(calls) == 1
    assert len(calls[0]) == 1
    assert [item["upper_color"] for item in observations] == ["black", "black"]


def test_upper_color_temporal_cache_reuses_moving_body_by_center(monkeypatch):
    observations = _capture_observations(monkeypatch)
    image = np.zeros((220, 180, 3), dtype=np.uint8)
    cache = observation_service.UpperColorTemporalCache(
        max_age_sec=2.5,
        iou_threshold=0.50,
        center_threshold=0.30,
    )
    calls = []

    def classify_upper_colors(_frame, body_boxes):
        calls.append(list(body_boxes))
        return [
            observation_service.person_analysis.RegionResult("black", 0.8, True, 1.0)
            for _body in body_boxes
        ]

    monkeypatch.setattr(observation_service.settings, "upper_color_backend", "clip_schp")
    monkeypatch.setattr(observation_service.settings, "enable_upper_color_temporal_cache", True)
    monkeypatch.setattr(
        observation_service.person_analysis,
        "_classify_upper_colors_with_backend",
        classify_upper_colors,
    )

    observation_service.create_frame_observations(
        frame=image,
        video_id="video_1",
        camera_id="camera_1",
        frame_path="/tmp/frame1.jpg",
        video_timestamp_sec=1.0,
        captured_at=None,
        frame_index=1,
        faces=[],
        bodies=[{"x1": 10, "y1": 10, "x2": 70, "y2": 190, "score": 0.9, "detector": "opencv_hog"}],
        upper_color_cache=cache,
    )
    observation_service.create_frame_observations(
        frame=image,
        video_id="video_1",
        camera_id="camera_1",
        frame_path="/tmp/frame2.jpg",
        video_timestamp_sec=2.0,
        captured_at=None,
        frame_index=2,
        faces=[],
        bodies=[{"x1": 50, "y1": 10, "x2": 110, "y2": 190, "score": 0.9, "detector": "opencv_hog"}],
        upper_color_cache=cache,
    )

    assert len(calls) == 1
    assert len(calls[0]) == 1
    assert [item["upper_color"] for item in observations] == ["black", "black"]


def test_upper_color_temporal_cache_does_not_reuse_one_entry_for_two_bodies(monkeypatch):
    observations = _capture_observations(monkeypatch)
    image = np.zeros((220, 180, 3), dtype=np.uint8)
    cache = observation_service.UpperColorTemporalCache(max_age_sec=2.5, iou_threshold=0.50)
    calls = []

    def classify_upper_colors(_frame, body_boxes):
        calls.append(list(body_boxes))
        colors = ["black", "white"]
        return [
            observation_service.person_analysis.RegionResult(colors[index], 0.8, True, 1.0)
            for index, _body in enumerate(body_boxes)
        ]

    monkeypatch.setattr(observation_service.settings, "upper_color_backend", "clip_schp")
    monkeypatch.setattr(observation_service.settings, "enable_upper_color_temporal_cache", True)
    monkeypatch.setattr(
        observation_service.person_analysis,
        "_classify_upper_colors_with_backend",
        classify_upper_colors,
    )

    observation_service.create_frame_observations(
        frame=image,
        video_id="video_1",
        camera_id="camera_1",
        frame_path="/tmp/frame1.jpg",
        video_timestamp_sec=1.0,
        captured_at=None,
        frame_index=1,
        faces=[],
        bodies=[{"x1": 10, "y1": 10, "x2": 70, "y2": 190, "score": 0.9, "detector": "opencv_hog"}],
        upper_color_cache=cache,
    )
    observation_service.create_frame_observations(
        frame=image,
        video_id="video_1",
        camera_id="camera_1",
        frame_path="/tmp/frame2.jpg",
        video_timestamp_sec=2.0,
        captured_at=None,
        frame_index=2,
        faces=[],
        bodies=[
            {"x1": 12, "y1": 12, "x2": 72, "y2": 192, "score": 0.9, "detector": "opencv_hog"},
            {"x1": 14, "y1": 14, "x2": 74, "y2": 194, "score": 0.9, "detector": "opencv_hog"},
        ],
        upper_color_cache=cache,
    )

    assert len(calls) == 2
    assert len(calls[0]) == 1
    assert len(calls[1]) == 1
    assert [item["upper_color"] for item in observations] == ["black", "black", "black"]


def test_upper_color_temporal_cache_reuses_large_motion_by_face_embedding(monkeypatch):
    observations = _capture_observations(monkeypatch)
    image = np.zeros((220, 220, 3), dtype=np.uint8)
    cache = observation_service.UpperColorTemporalCache(
        max_age_sec=2.5,
        iou_threshold=0.50,
        center_threshold=0.20,
        face_max_age_sec=30.0,
        face_similarity_threshold=0.90,
    )
    calls = []

    def classify_upper_colors(_frame, body_boxes):
        calls.append(list(body_boxes))
        return [
            observation_service.person_analysis.RegionResult("black", 0.8, True, 1.0)
            for _body in body_boxes
        ]

    monkeypatch.setattr(observation_service.settings, "upper_color_backend", "clip_schp")
    monkeypatch.setattr(observation_service.settings, "enable_upper_color_temporal_cache", True)
    monkeypatch.setattr(
        observation_service.person_analysis,
        "_classify_upper_colors_with_backend",
        classify_upper_colors,
    )

    observation_service.create_frame_observations(
        frame=image,
        video_id="video_1",
        camera_id="camera_1",
        frame_path="/tmp/frame1.jpg",
        video_timestamp_sec=1.0,
        captured_at=None,
        frame_index=1,
        faces=[{"face_id": "face_1", "x1": 30, "y1": 20, "x2": 50, "y2": 40, "score": 0.9, "embedding": [1.0, 0.0]}],
        bodies=[{"x1": 10, "y1": 10, "x2": 70, "y2": 190, "score": 0.9, "detector": "opencv_hog"}],
        upper_color_cache=cache,
    )
    observation_service.create_frame_observations(
        frame=image,
        video_id="video_1",
        camera_id="camera_1",
        frame_path="/tmp/frame2.jpg",
        video_timestamp_sec=12.0,
        captured_at=None,
        frame_index=2,
        faces=[{"face_id": "face_2", "x1": 130, "y1": 20, "x2": 150, "y2": 40, "score": 0.9, "embedding": [0.98, 0.02]}],
        bodies=[{"x1": 110, "y1": 10, "x2": 170, "y2": 190, "score": 0.9, "detector": "opencv_hog"}],
        upper_color_cache=cache,
    )

    assert len(calls) == 1
    assert [item["upper_color"] for item in observations] == ["black", "black"]


def test_upper_color_temporal_cache_does_not_reuse_large_motion_for_different_face(monkeypatch):
    observations = _capture_observations(monkeypatch)
    image = np.zeros((220, 220, 3), dtype=np.uint8)
    cache = observation_service.UpperColorTemporalCache(
        max_age_sec=2.5,
        iou_threshold=0.50,
        center_threshold=0.20,
        face_max_age_sec=30.0,
        face_similarity_threshold=0.90,
    )
    calls = []

    def classify_upper_colors(_frame, body_boxes):
        calls.append(list(body_boxes))
        color = "black" if len(calls) == 1 else "white"
        return [
            observation_service.person_analysis.RegionResult(color, 0.8, True, 1.0)
            for _body in body_boxes
        ]

    monkeypatch.setattr(observation_service.settings, "upper_color_backend", "clip_schp")
    monkeypatch.setattr(observation_service.settings, "enable_upper_color_temporal_cache", True)
    monkeypatch.setattr(
        observation_service.person_analysis,
        "_classify_upper_colors_with_backend",
        classify_upper_colors,
    )

    observation_service.create_frame_observations(
        frame=image,
        video_id="video_1",
        camera_id="camera_1",
        frame_path="/tmp/frame1.jpg",
        video_timestamp_sec=1.0,
        captured_at=None,
        frame_index=1,
        faces=[{"face_id": "face_1", "x1": 30, "y1": 20, "x2": 50, "y2": 40, "score": 0.9, "embedding": [1.0, 0.0]}],
        bodies=[{"x1": 10, "y1": 10, "x2": 70, "y2": 190, "score": 0.9, "detector": "opencv_hog"}],
        upper_color_cache=cache,
    )
    observation_service.create_frame_observations(
        frame=image,
        video_id="video_1",
        camera_id="camera_1",
        frame_path="/tmp/frame2.jpg",
        video_timestamp_sec=12.0,
        captured_at=None,
        frame_index=2,
        faces=[{"face_id": "face_2", "x1": 130, "y1": 20, "x2": 150, "y2": 40, "score": 0.9, "embedding": [0.0, 1.0]}],
        bodies=[{"x1": 110, "y1": 10, "x2": 170, "y2": 190, "score": 0.9, "detector": "opencv_hog"}],
        upper_color_cache=cache,
    )

    assert len(calls) == 2
    assert [item["upper_color"] for item in observations] == ["black", "white"]
