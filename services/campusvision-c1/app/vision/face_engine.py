from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache
from queue import LifoQueue
import threading
from typing import Protocol

import numpy as np

from app.core.config import settings


_FACE_ENGINE_INIT_LOCK = threading.Lock()


class FaceEngine(Protocol):
    name: str

    def detect_faces(self, image_bgr: np.ndarray) -> list[dict]:
        """Return list of boxes: {"x1": int, "y1": int, "x2": int, "y2": int, "score": float}."""
        ...

    def embed_faces(self, image_bgr: np.ndarray, boxes: list[dict]) -> list[list[float]]:
        """Return one normalized embedding for each box."""
        ...

    def detect_faces_with_embeddings(self, image_bgr: np.ndarray) -> tuple[list[dict], list[list[float]]]:
        """Return aligned face boxes and normalized embeddings from one backend pass."""
        ...


class _PooledFaceEngine:
    def __init__(self, engines: list[FaceEngine]) -> None:
        if not engines:
            raise ValueError("face engine pool requires at least one engine")
        self.name = f"{engines[0].name}_pool"
        self._pool: LifoQueue[FaceEngine] = LifoQueue(maxsize=len(engines))
        for engine in engines:
            self._pool.put(engine)

    @contextmanager
    def _borrow(self):
        engine = self._pool.get()
        try:
            yield engine
        finally:
            self._pool.put(engine)

    def detect_faces(self, image_bgr: np.ndarray) -> list[dict]:
        with self._borrow() as engine:
            return engine.detect_faces(image_bgr)

    def embed_faces(self, image_bgr: np.ndarray, boxes: list[dict]) -> list[list[float]]:
        with self._borrow() as engine:
            return engine.embed_faces(image_bgr, boxes)

    def detect_faces_with_embeddings(self, image_bgr: np.ndarray) -> tuple[list[dict], list[list[float]]]:
        with self._borrow() as engine:
            return engine.detect_faces_with_embeddings(image_bgr)


@lru_cache(maxsize=1)
def _get_face_engine_cached() -> FaceEngine:
    if settings.face_engine != "insightface":
        raise ValueError("CampusVision production mode only supports FACE_ENGINE=insightface.")

    from app.vision.engines.insightface_engine import InsightFaceEngine

    pool_size = max(1, int(settings.insightface_engine_pool_size or 1))
    if pool_size == 1:
        return InsightFaceEngine()
    return _PooledFaceEngine([InsightFaceEngine() for _index in range(pool_size)])


def get_face_engine() -> FaceEngine:
    with _FACE_ENGINE_INIT_LOCK:
        return _get_face_engine_cached()


def default_similarity_threshold() -> float:
    return 0.30


def confident_similarity_threshold() -> float:
    return 0.40
