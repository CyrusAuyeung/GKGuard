from __future__ import annotations

from functools import lru_cache
from typing import Protocol

import numpy as np

from app.core.config import settings


class FaceEngine(Protocol):
    name: str

    def detect_faces(self, image_bgr: np.ndarray) -> list[dict]:
        """Return list of boxes: {"x1": int, "y1": int, "x2": int, "y2": int, "score": float}."""
        ...

    def embed_faces(self, image_bgr: np.ndarray, boxes: list[dict]) -> list[list[float]]:
        """Return one normalized embedding for each box."""
        ...


@lru_cache(maxsize=1)
def get_face_engine() -> FaceEngine:
    if settings.face_engine != "insightface":
        raise ValueError("CampusVision production mode only supports FACE_ENGINE=insightface.")

    from app.vision.engines.insightface_engine import InsightFaceEngine

    return InsightFaceEngine()


def default_similarity_threshold() -> float:
    return 0.30


def confident_similarity_threshold() -> float:
    return 0.40
