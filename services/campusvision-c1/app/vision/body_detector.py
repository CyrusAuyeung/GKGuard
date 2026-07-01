from __future__ import annotations

from functools import lru_cache
import threading

import cv2
import numpy as np

from app.core.config import settings
from app.vision import person_analysis


_BODY_DETECTOR_INIT_LOCK = threading.Lock()


class BodyDetector:
    name = "disabled"

    def detect_people(self, image_bgr: np.ndarray) -> list[dict]:
        return []


def _nms(detections: list[dict], threshold: float) -> list[dict]:
    if not detections:
        return []

    boxes = np.asarray(
        [
            [
                float(det["x1"]),
                float(det["y1"]),
                float(det["x2"] - det["x1"]),
                float(det["y2"] - det["y1"]),
            ]
            for det in detections
        ],
        dtype=np.float32,
    )
    scores = [float(det.get("score") or 0.0) for det in detections]
    indices = cv2.dnn.NMSBoxes(boxes.tolist(), scores, 0.0, float(threshold))
    if len(indices) == 0:
        return []
    return [detections[int(index)] for index in np.asarray(indices).reshape(-1)]


class OpenCVHogPersonDetector(BodyDetector):
    name = "opencv_hog"

    def __init__(self) -> None:
        self.hog = cv2.HOGDescriptor()
        self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

    def detect_people(self, image_bgr: np.ndarray) -> list[dict]:
        if image_bgr is None or image_bgr.size == 0:
            return []

        rects, weights = self.hog.detectMultiScale(
            image_bgr,
            hitThreshold=0.0,
            winStride=(8, 8),
            padding=(16, 16),
            scale=1.05,
        )

        detections = []
        height, width = image_bgr.shape[:2]
        for index, (x, y, w, h) in enumerate(rects):
            raw_score = float(weights[index]) if len(weights) > index else 0.0
            score = float(1.0 / (1.0 + np.exp(-raw_score)))
            x1 = max(0, min(width - 1, int(x)))
            y1 = max(0, min(height - 1, int(y)))
            x2 = max(x1 + 1, min(width, int(x + w)))
            y2 = max(y1 + 1, min(height, int(y + h)))
            if x2 - x1 < settings.min_person_box_width or y2 - y1 < settings.min_person_box_height:
                continue
            if score < settings.person_detection_confidence_threshold:
                continue
            detections.append(
                {
                    "x1": x1,
                    "y1": y1,
                    "x2": x2,
                    "y2": y2,
                    "score": score,
                    "class_id": 0,
                    "class_name": "person",
                    "detector": self.name,
                }
            )

        return _nms(detections, settings.person_detection_nms_threshold)


class UltralyticsPersonDetector(BodyDetector):
    name = "ultralytics_yolo"

    def __init__(self) -> None:
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError("ultralytics is required for BODY_DETECTION_BACKEND=ultralytics_yolo") from exc

        model_path = settings.ultralytics_model_path
        if not model_path.exists():
            raise FileNotFoundError(f"Ultralytics model not found: {model_path}")
        self.model = YOLO(str(model_path))
        max_concurrent = max(1, int(settings.ultralytics_max_concurrent_inferences or 1))
        self._inference_semaphore = threading.BoundedSemaphore(max_concurrent)

    def detect_people(self, image_bgr: np.ndarray) -> list[dict]:
        if image_bgr is None or image_bgr.size == 0:
            return []

        with self._inference_semaphore:
            results = self.model.predict(
                source=image_bgr,
                classes=[0],
                conf=settings.person_detection_confidence_threshold,
                iou=settings.person_detection_nms_threshold,
                imgsz=settings.ultralytics_imgsz,
                max_det=settings.ultralytics_max_detections,
                device=settings.ultralytics_device,
                verbose=False,
            )
        if not results:
            return []

        height, width = image_bgr.shape[:2]
        detections = []
        boxes = results[0].boxes
        if boxes is None:
            return []
        for box in boxes:
            cls = int(box.cls.item()) if box.cls is not None else 0
            if cls != 0:
                continue
            x1, y1, x2, y2 = [float(value) for value in box.xyxy[0].tolist()]
            score = float(box.conf.item()) if box.conf is not None else 0.0
            clamped = person_analysis.clamp_bbox(
                {
                    "x1": x1,
                    "y1": y1,
                    "x2": x2,
                    "y2": y2,
                    "score": score,
                    "class_id": 0,
                    "class_name": "person",
                    "detector": self.name,
                },
                width,
                height,
            )
            if clamped["width"] < settings.min_person_box_width or clamped["height"] < settings.min_person_box_height:
                continue
            detections.append(clamped)
        return detections


@lru_cache(maxsize=1)
def _get_body_detector_cached() -> BodyDetector:
    if not settings.enable_body_detection:
        return BodyDetector()
    if settings.body_detection_backend == "opencv_hog":
        return OpenCVHogPersonDetector()
    if settings.body_detection_backend in {"ultralytics", "ultralytics_yolo", "yolo"}:
        return UltralyticsPersonDetector()
    if settings.body_detection_backend in {"none", "disabled"}:
        return BodyDetector()
    raise ValueError(f"Unsupported BODY_DETECTION_BACKEND={settings.body_detection_backend}")


def get_body_detector() -> BodyDetector:
    with _BODY_DETECTOR_INIT_LOCK:
        return _get_body_detector_cached()
