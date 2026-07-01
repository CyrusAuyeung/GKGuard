from pathlib import Path
import sys

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

pytest.importorskip("cv2")

from app.services import video_service  # noqa: E402


def test_detect_faces_and_embeddings_prefers_single_pass_backend():
    class Engine:
        def __init__(self):
            self.single_pass_calls = 0
            self.detect_calls = 0
            self.embed_calls = 0

        def detect_faces_with_embeddings(self, _frame):
            self.single_pass_calls += 1
            return [{"x1": 1, "y1": 2, "x2": 3, "y2": 4, "score": 0.9}], [[1.0, 0.0]]

        def detect_faces(self, _frame):
            self.detect_calls += 1
            return []

        def embed_faces(self, _frame, _boxes):
            self.embed_calls += 1
            return []

    engine = Engine()
    boxes, embeddings = video_service._detect_faces_and_embeddings(engine, np.zeros((8, 8, 3), dtype=np.uint8))

    assert boxes == [{"x1": 1, "y1": 2, "x2": 3, "y2": 4, "score": 0.9}]
    assert embeddings == [[1.0, 0.0]]
    assert engine.single_pass_calls == 1
    assert engine.detect_calls == 0
    assert engine.embed_calls == 0


def test_detect_faces_and_embeddings_falls_back_to_two_step_backend():
    class Engine:
        def __init__(self):
            self.detect_calls = 0
            self.embed_calls = 0

        def detect_faces(self, _frame):
            self.detect_calls += 1
            return [{"x1": 1, "y1": 2, "x2": 3, "y2": 4, "score": 0.9}]

        def embed_faces(self, _frame, boxes):
            self.embed_calls += 1
            assert boxes
            return [[1.0, 0.0]]

    engine = Engine()
    boxes, embeddings = video_service._detect_faces_and_embeddings(engine, np.zeros((8, 8, 3), dtype=np.uint8))

    assert boxes == [{"x1": 1, "y1": 2, "x2": 3, "y2": 4, "score": 0.9}]
    assert embeddings == [[1.0, 0.0]]
    assert engine.detect_calls == 1
    assert engine.embed_calls == 1


def test_index_performance_profile_is_opt_in():
    disabled = video_service._IndexPerformanceProfile(enabled=False)
    with disabled.stage("hidden"):
        disabled.count("items")
    assert disabled.summary(processing_duration_sec=1.0) is None

    enabled = video_service._IndexPerformanceProfile(enabled=True)
    with enabled.stage("visible"):
        enabled.count("items", 2)
    summary = enabled.summary(processing_duration_sec=1.0)

    assert summary is not None
    assert summary["schema_version"] == "c1_index_performance_profile_v1"
    assert summary["counts"]["items"] == 2
    assert summary["stages"]["visible"]["calls"] == 1
    assert summary["stages"]["visible"]["elapsed_sec"] >= 0.0
