from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np
from PIL import Image

from app.core.config import settings


MODEL_VERSION = "glasses_status_clip_h14_face_zero_shot_v1"
STATUS_LABELS = {
    "glasses": "戴眼镜",
    "no_glasses": "未戴眼镜",
    "unknown": "无法判断",
}
MODEL_CLASSES = ("glasses", "no_glasses")
PROMPTS = {
    "glasses": [
        "wearing glasses",
        "with eyeglasses",
        "with spectacles",
        "glasses",
    ],
    "no_glasses": [
        "not wearing glasses",
        "without eyeglasses",
        "without spectacles",
        "no glasses",
    ],
}

_PIPELINE_LOCK = threading.Lock()
_PIPELINE: _ClipGlassesStatusPipeline | None = None
_UNAVAILABLE_REASON: str | None = None


@dataclass(frozen=True)
class GlassesStatusSample:
    image_bgr: np.ndarray
    sample_id: str = ""
    event_id: str = ""
    observation_id: str = ""
    camera_id: str = ""


def predict_person_samples(samples: list[dict[str, Any] | GlassesStatusSample]) -> dict[str, Any]:
    global _UNAVAILABLE_REASON
    if not settings.enable_glasses_status_detection:
        return _unknown_prediction("disabled", samples=[])
    normalized = [_normalize_sample(sample) for sample in samples]
    normalized = [sample for sample in normalized if sample is not None]
    if not normalized:
        return _unknown_prediction("no_usable_face_samples", samples=[])
    if _UNAVAILABLE_REASON and settings.glasses_status_fail_open:
        return _unknown_prediction(_UNAVAILABLE_REASON, samples=normalized)
    try:
        return _get_pipeline().predict(normalized)
    except Exception as exc:
        if not settings.glasses_status_fail_open:
            raise
        _UNAVAILABLE_REASON = f"{type(exc).__name__}: {exc}"
        return _unknown_prediction(_UNAVAILABLE_REASON, samples=normalized)


def unavailable_reason() -> str | None:
    return _UNAVAILABLE_REASON


def reset_pipeline_for_tests() -> None:
    global _PIPELINE, _UNAVAILABLE_REASON
    with _PIPELINE_LOCK:
        _PIPELINE = None
        _UNAVAILABLE_REASON = None


def _get_pipeline() -> "_ClipGlassesStatusPipeline":
    global _PIPELINE
    with _PIPELINE_LOCK:
        if _PIPELINE is None:
            _PIPELINE = _ClipGlassesStatusPipeline()
        return _PIPELINE


def _normalize_sample(sample: dict[str, Any] | GlassesStatusSample) -> GlassesStatusSample | None:
    if isinstance(sample, GlassesStatusSample):
        image_bgr = sample.image_bgr
        if image_bgr is None or getattr(image_bgr, "size", 0) <= 0:
            return None
        return sample

    image_bgr = sample.get("image_bgr")
    if image_bgr is None and sample.get("image_path"):
        image_bgr = cv2.imread(str(sample["image_path"]))
    if image_bgr is None or getattr(image_bgr, "size", 0) <= 0:
        return None
    return GlassesStatusSample(
        image_bgr=image_bgr,
        sample_id=str(sample.get("sample_id") or ""),
        event_id=str(sample.get("event_id") or ""),
        observation_id=str(sample.get("observation_id") or ""),
        camera_id=str(sample.get("camera_id") or ""),
    )


class _ClipGlassesStatusPipeline:
    def __init__(self) -> None:
        import torch
        from transformers import CLIPModel, CLIPProcessor

        self.torch = torch
        self.device = _resolve_device(settings.glasses_status_device, torch)
        model_dir = settings.glasses_status_model_dir
        if not model_dir.exists():
            raise FileNotFoundError(f"glasses status CLIP model directory not found: {model_dir}")

        self.clip_model = CLIPModel.from_pretrained(str(model_dir), local_files_only=True).to(self.device)
        self.clip_processor = CLIPProcessor.from_pretrained(str(model_dir), local_files_only=True)
        self.clip_model.eval()
        self.temperature = float(settings.glasses_status_temperature)
        self._text_features = self._build_text_features()

    def predict(self, samples: list[GlassesStatusSample]) -> dict[str, Any]:
        images = [_bgr_to_pil(sample.image_bgr) for sample in samples]
        features = self._image_features(images)
        sample_predictions = []
        scores_by_sample = []
        for sample, feature in zip(samples, features):
            scores = (feature @ self._text_features.T).detach().cpu().numpy().astype(np.float32)
            probs = _softmax(scores * self.temperature)
            class_index = int(np.argmax(scores))
            sample_predictions.append(
                {
                    "sample_id": sample.sample_id,
                    "event_id": sample.event_id,
                    "observation_id": sample.observation_id,
                    "camera_id": sample.camera_id,
                    "glasses_status": MODEL_CLASSES[class_index],
                    "confidence": round(float(probs[class_index]), 6),
                    "score_margin": round(float(abs(scores[0] - scores[1])), 6),
                    "scores": {
                        label: round(float(scores[index]), 6)
                        for index, label in enumerate(MODEL_CLASSES)
                    },
                    "probabilities": {
                        label: round(float(probs[index]), 6)
                        for index, label in enumerate(MODEL_CLASSES)
                    },
                }
            )
            scores_by_sample.append(scores)

        aggregate_scores = np.stack(scores_by_sample).mean(axis=0)
        aggregate_probs = _softmax(aggregate_scores * self.temperature)
        return _prediction_from_scores(
            aggregate_scores,
            aggregate_probs,
            sample_predictions=sample_predictions,
        )

    def _image_features(self, images: list[Image.Image]):
        features = []
        batch_size = 32
        for index in range(0, len(images), batch_size):
            inputs = self.clip_processor(images=images[index : index + batch_size], return_tensors="pt").to(self.device)
            with self.torch.no_grad():
                batch = self.clip_model.get_image_features(**inputs)
                batch = batch / batch.norm(dim=-1, keepdim=True)
            features.extend(batch)
        return features

    def _build_text_features(self):
        features = []
        for label in MODEL_CLASSES:
            inputs = self.clip_processor(text=PROMPTS[label], return_tensors="pt", padding=True).to(self.device)
            with self.torch.no_grad():
                prompt_features = self.clip_model.get_text_features(**inputs)
                prompt_features = prompt_features / prompt_features.norm(dim=-1, keepdim=True)
                feature = prompt_features.mean(dim=0)
                feature = feature / feature.norm(dim=-1, keepdim=True)
            features.append(feature)
        return self.torch.stack(features, dim=0)


def _prediction_from_scores(
    scores: np.ndarray,
    probabilities: np.ndarray | None = None,
    *,
    sample_predictions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    probabilities = _softmax(scores * float(settings.glasses_status_temperature)) if probabilities is None else probabilities
    class_index = int(np.argmax(scores))
    status = MODEL_CLASSES[class_index]
    sample_predictions = sample_predictions or []
    votes = {
        value: sum(1 for item in sample_predictions if item.get("glasses_status") == value)
        for value in MODEL_CLASSES
    }
    consistency = max(votes.values()) / len(sample_predictions) if sample_predictions else None
    return {
        "glasses_status": status,
        "glasses_status_label": STATUS_LABELS[status],
        "confidence": round(float(probabilities[class_index]), 6),
        "score_margin": round(float(abs(scores[0] - scores[1])), 6),
        "evidence_quality": _evidence_quality(len(sample_predictions), consistency),
        "evidence_quality_label": _evidence_quality_label(_evidence_quality(len(sample_predictions), consistency)),
        "sample_count": len(sample_predictions),
        "sample_votes": votes,
        "sample_consistency": round(float(consistency), 6) if consistency is not None else None,
        "scores": {
            class_name: round(float(scores[index]), 6)
            for index, class_name in enumerate(MODEL_CLASSES)
        },
        "probabilities": {
            class_name: round(float(probabilities[index]), 6)
            for index, class_name in enumerate(MODEL_CLASSES)
        },
        "sample_predictions": sample_predictions,
        "model_version": MODEL_VERSION,
    }


def _unknown_prediction(reason: str, *, samples: list[GlassesStatusSample]) -> dict[str, Any]:
    return {
        "glasses_status": "unknown",
        "glasses_status_label": STATUS_LABELS["unknown"],
        "confidence": 0.0,
        "score_margin": 0.0,
        "evidence_quality": "poor",
        "evidence_quality_label": _evidence_quality_label("poor"),
        "sample_count": len(samples),
        "sample_votes": {},
        "sample_consistency": None,
        "scores": {},
        "probabilities": {},
        "sample_predictions": [],
        "model_version": MODEL_VERSION,
        "uncertainty_reason": reason,
    }


def _evidence_quality(sample_count: int, consistency: float | None) -> str:
    if sample_count <= 0:
        return "poor"
    if sample_count >= 6 and consistency is not None and consistency >= 0.80:
        return "clear"
    return "partial"


def _evidence_quality_label(value: str) -> str:
    return {
        "clear": "清晰",
        "partial": "部分可见",
        "poor": "画质较差",
    }.get(value, "画质较差")


def _softmax(values: np.ndarray) -> np.ndarray:
    values = values.astype(np.float32)
    shifted = values - float(values.max())
    exp = np.exp(shifted)
    return exp / max(1e-9, float(exp.sum()))


def _bgr_to_pil(image_bgr: np.ndarray) -> Image.Image:
    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)


def _resolve_device(device: str, torch_module) -> str:
    selected = device.strip() or "cpu"
    if selected.startswith("cuda") and not torch_module.cuda.is_available():
        return "cpu"
    return selected
