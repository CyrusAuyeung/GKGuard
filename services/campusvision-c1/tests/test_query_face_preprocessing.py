from pathlib import Path
import sys
import importlib.util

import pytest
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CV2_AVAILABLE = importlib.util.find_spec("cv2") is not None
pytestmark = pytest.mark.skipif(not CV2_AVAILABLE, reason="CampusVision C1 tests require opencv-python")

if CV2_AVAILABLE:
    from app.services import search_service  # noqa: E402


class RetryEngine:
    name = "retry-face"

    def __init__(self):
        self.detect_calls = []

    def detect_faces(self, image_bgr):
        height, width = image_bgr.shape[:2]
        self.detect_calls.append((width, height))
        if len(self.detect_calls) == 1:
            return []
        return [{"x1": 58, "y1": 67, "x2": 182, "y2": 235, "score": 0.82}]

    def embed_faces(self, image_bgr, boxes):
        return [[1.0, 0.0, 0.0] for _ in boxes]


def test_detect_query_faces_retries_with_padding_and_maps_bbox(monkeypatch, tmp_path):
    image_path = tmp_path / "tight-headshot.jpg"
    Image.new("RGB", (120, 160), (245, 248, 255)).save(image_path)
    engine = RetryEngine()
    monkeypatch.setattr(search_service, "get_face_engine", lambda: engine)

    result = search_service.detect_query_faces([str(image_path)])

    assert result["face_count"] == 1
    assert result["query_faces"][0]["detection_attempt"] == "padded-16"
    assert result["query_faces"][0]["bbox"]["x1"] == 11
    assert result["query_faces"][0]["bbox"]["y1"] == 8
    assert result["query_faces"][0]["bbox"]["width"] == 62
    assert result["diagnostics"]["images"][0]["attempts"][0]["face_count"] == 0
    assert result["diagnostics"]["images"][0]["attempts"][1]["face_count"] == 1


def test_load_embeddings_uses_retry_variant(monkeypatch, tmp_path):
    image_path = tmp_path / "tight-headshot.jpg"
    Image.new("RGB", (120, 160), (245, 248, 255)).save(image_path)
    engine = RetryEngine()
    monkeypatch.setattr(search_service, "get_face_engine", lambda: engine)

    embeddings = search_service.load_embeddings_from_images([str(image_path)], query_face_index=0)

    assert embeddings == [[1.0, 0.0, 0.0]]
