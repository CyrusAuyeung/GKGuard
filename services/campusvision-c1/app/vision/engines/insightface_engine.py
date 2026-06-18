from __future__ import annotations

import numpy as np

from app.core.config import settings


def _normalize(vec: np.ndarray) -> np.ndarray:
    vec = vec.astype("float32").reshape(-1)
    norm = float(np.linalg.norm(vec))
    if norm < 1e-8:
        return vec
    return vec / norm


def _iou(left: dict, right: dict) -> float:
    x1 = max(float(left["x1"]), float(right["x1"]))
    y1 = max(float(left["y1"]), float(right["y1"]))
    x2 = min(float(left["x2"]), float(right["x2"]))
    y2 = min(float(left["y2"]), float(right["y2"]))
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    left_area = max(0.0, float(left["x2"] - left["x1"])) * max(0.0, float(left["y2"] - left["y1"]))
    right_area = max(0.0, float(right["x2"] - right["x1"])) * max(0.0, float(right["y2"] - right["y1"]))
    union = left_area + right_area - inter
    return inter / union if union > 0 else 0.0


class InsightFaceEngine:
    """InsightFace/ArcFace backend for real-world face detection and embedding."""

    name = "insightface"

    def __init__(self):
        try:
            from insightface.app import FaceAnalysis
        except Exception as exc:
            raise RuntimeError(
                "FACE_ENGINE=insightface requires insightface and onnxruntime. "
                "Run: pip install -r requirements.txt"
            ) from exc

        try:
            import onnxruntime as ort

            providers = ort.get_available_providers()
        except Exception:
            providers = ["CPUExecutionProvider"]

        ctx_id = 0 if "CUDAExecutionProvider" in providers else -1
        det_size = max(640, int(settings.insightface_det_size or 1280))
        self.app = FaceAnalysis(name="buffalo_l", providers=providers)
        self.app.prepare(ctx_id=ctx_id, det_size=(det_size, det_size))

    def _faces(self, image_bgr: np.ndarray):
        if image_bgr is None:
            return []
        return self.app.get(image_bgr)

    def detect_faces(self, image_bgr: np.ndarray) -> list[dict]:
        out = []
        for face in self._faces(image_bgr):
            x1, y1, x2, y2 = [int(v) for v in face.bbox.tolist()]
            score = float(getattr(face, "det_score", 0.0))
            out.append({"x1": x1, "y1": y1, "x2": x2, "y2": y2, "score": score})
        return out

    def embed_faces(self, image_bgr: np.ndarray, boxes: list[dict]) -> list[list[float]]:
        if not boxes:
            return []

        detected = []
        for face in self._faces(image_bgr):
            x1, y1, x2, y2 = [int(v) for v in face.bbox.tolist()]
            embedding = getattr(face, "normed_embedding", None)
            if embedding is None:
                embedding = getattr(face, "embedding", None)
            if embedding is None:
                continue
            detected.append(
                {
                    "box": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
                    "embedding": _normalize(np.asarray(embedding)).tolist(),
                }
            )

        embeddings: list[list[float]] = []
        used: set[int] = set()
        for box in boxes:
            best_index = None
            best_iou = -1.0
            for index, face in enumerate(detected):
                if index in used:
                    continue
                score = _iou(box, face["box"])
                if score > best_iou:
                    best_iou = score
                    best_index = index
            if best_index is not None and best_iou >= 0.30:
                used.add(best_index)
                embeddings.append(detected[best_index]["embedding"])
        return embeddings
