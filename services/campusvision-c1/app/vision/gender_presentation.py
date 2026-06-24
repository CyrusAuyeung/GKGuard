from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np
from PIL import Image

from app.core.config import settings


MODEL_VERSION = "gender_presentation_clip_h14_zero_shot_v1"
PRESENTATION_LABELS = {
    "masculine": "偏男性",
    "feminine": "偏女性",
    "neutral": "中性风",
    "unknown": "无法判断",
}
MODEL_CLASSES = ("masculine", "feminine", "neutral")
SAMPLE_WEIGHTS = {
    "body": 0.45,
    "face": 0.45,
    "frame": 0.10,
}
PROMPTS = {
    "masculine": [
        "a surveillance photo of a masculine-presenting person",
        "a security camera image of a male-presenting person",
        "a person who appears male from face body clothing and hairstyle",
        "a man in a surveillance camera image",
    ],
    "feminine": [
        "a surveillance photo of a feminine-presenting person",
        "a security camera image of a female-presenting person",
        "a person who appears female from face body clothing and hairstyle",
        "a woman in a surveillance camera image",
    ],
    "neutral": [
        "a surveillance photo of an androgynous person",
        "a security camera image of a gender-neutral presenting person",
        "a person whose gender presentation is ambiguous",
        "a person with unclear gender presentation",
    ],
}

_PIPELINE_LOCK = threading.Lock()
_PIPELINE: _ClipGenderPresentationPipeline | None = None
_UNAVAILABLE_REASON: str | None = None


@dataclass(frozen=True)
class GenderPresentationSample:
    image_bgr: np.ndarray
    sample_type: str
    sample_id: str = ""
    event_id: str = ""
    observation_id: str = ""
    camera_id: str = ""


def predict_person_samples(samples: list[dict[str, Any] | GenderPresentationSample]) -> dict[str, Any]:
    global _UNAVAILABLE_REASON
    if not settings.enable_gender_presentation_detection:
        return _unknown_prediction("disabled", samples=[])
    normalized = [_normalize_sample(sample) for sample in samples]
    normalized = [sample for sample in normalized if sample is not None]
    if not normalized:
        return _unknown_prediction("no_usable_samples", samples=[])
    if _UNAVAILABLE_REASON and settings.gender_presentation_fail_open:
        return _unknown_prediction(_UNAVAILABLE_REASON, samples=normalized)
    try:
        return _get_pipeline().predict(normalized)
    except Exception as exc:
        if not settings.gender_presentation_fail_open:
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


def _get_pipeline() -> "_ClipGenderPresentationPipeline":
    global _PIPELINE
    with _PIPELINE_LOCK:
        if _PIPELINE is None:
            _PIPELINE = _ClipGenderPresentationPipeline()
        return _PIPELINE


def _normalize_sample(sample: dict[str, Any] | GenderPresentationSample) -> GenderPresentationSample | None:
    if isinstance(sample, GenderPresentationSample):
        image_bgr = sample.image_bgr
        if image_bgr is None or getattr(image_bgr, "size", 0) <= 0:
            return None
        return sample

    image_bgr = sample.get("image_bgr")
    if image_bgr is None and sample.get("image_path"):
        image_bgr = cv2.imread(str(sample["image_path"]))
    if image_bgr is None or getattr(image_bgr, "size", 0) <= 0:
        return None
    sample_type = str(sample.get("sample_type") or sample.get("type") or "body")
    return GenderPresentationSample(
        image_bgr=image_bgr,
        sample_type=sample_type if sample_type in SAMPLE_WEIGHTS else "body",
        sample_id=str(sample.get("sample_id") or ""),
        event_id=str(sample.get("event_id") or ""),
        observation_id=str(sample.get("observation_id") or ""),
        camera_id=str(sample.get("camera_id") or ""),
    )


class _ClipGenderPresentationPipeline:
    def __init__(self) -> None:
        import torch
        from transformers import CLIPModel, CLIPProcessor

        self.torch = torch
        self.device = _resolve_device(settings.gender_presentation_device, torch)
        model_dir = settings.gender_presentation_model_dir
        if not model_dir.exists():
            raise FileNotFoundError(f"gender presentation CLIP model directory not found: {model_dir}")

        self.clip_model = CLIPModel.from_pretrained(str(model_dir), local_files_only=True).to(self.device)
        self.clip_processor = CLIPProcessor.from_pretrained(str(model_dir), local_files_only=True)
        self.clip_model.eval()
        self.temperature = float(settings.gender_presentation_temperature)
        self._text_features = self._build_text_features()

    def predict(self, samples: list[GenderPresentationSample]) -> dict[str, Any]:
        images = [_bgr_to_pil(sample.image_bgr) for sample in samples]
        features = self._image_features(images)
        sample_predictions = []
        weighted_scores = []
        weights = []
        for sample, feature in zip(samples, features):
            scores = (feature @ self._text_features.T).detach().cpu().numpy().astype(np.float32)
            probs = _softmax(scores * self.temperature)
            class_index = int(np.argmax(scores))
            sample_prediction = {
                "sample_id": sample.sample_id,
                "sample_type": sample.sample_type,
                "event_id": sample.event_id,
                "observation_id": sample.observation_id,
                "camera_id": sample.camera_id,
                "gender_presentation": MODEL_CLASSES[class_index],
                "confidence": round(float(probs[class_index]), 6),
                "scores": {
                    label: round(float(scores[index]), 6)
                    for index, label in enumerate(MODEL_CLASSES)
                },
                "probabilities": {
                    label: round(float(probs[index]), 6)
                    for index, label in enumerate(MODEL_CLASSES)
                },
            }
            sample_predictions.append(sample_prediction)
            weight = float(SAMPLE_WEIGHTS.get(sample.sample_type, 0.25))
            weighted_scores.append(scores * weight)
            weights.append(weight)

        aggregate_scores = np.stack(weighted_scores).sum(axis=0) / max(1e-6, float(sum(weights)))
        aggregate_probs = _softmax(aggregate_scores * self.temperature)
        return _prediction_from_scores(
            aggregate_scores,
            aggregate_probs,
            sample_predictions=sample_predictions,
            sample_type_counts=_sample_type_counts(samples),
        )

    def _image_features(self, images: list[Image.Image]):
        features = []
        batch_size = 24
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
    sample_type_counts: dict[str, int] | None = None,
) -> dict[str, Any]:
    probabilities = _softmax(scores * float(settings.gender_presentation_temperature)) if probabilities is None else probabilities
    order = np.argsort(-scores)
    best_index = int(order[0])
    second_index = int(order[1]) if len(order) > 1 else best_index
    label = MODEL_CLASSES[best_index]
    margin = float(scores[best_index] - scores[second_index])
    confidence = float(probabilities[best_index])
    sample_predictions = sample_predictions or []
    sample_type_counts = sample_type_counts or {}
    evidence_quality = _evidence_quality(sample_type_counts, len(sample_predictions))
    return {
        "gender_presentation": label,
        "gender_presentation_label": PRESENTATION_LABELS[label],
        "confidence": round(confidence, 6),
        "score_margin": round(margin, 6),
        "evidence_quality": evidence_quality,
        "evidence_quality_label": _evidence_quality_label(evidence_quality),
        "sample_count": len(sample_predictions),
        "sample_type_counts": sample_type_counts,
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


def _unknown_prediction(reason: str, *, samples: list[GenderPresentationSample]) -> dict[str, Any]:
    counts = _sample_type_counts(samples)
    return {
        "gender_presentation": "unknown",
        "gender_presentation_label": PRESENTATION_LABELS["unknown"],
        "confidence": 0.0,
        "score_margin": 0.0,
        "evidence_quality": "poor",
        "evidence_quality_label": _evidence_quality_label("poor"),
        "sample_count": len(samples),
        "sample_type_counts": counts,
        "scores": {},
        "probabilities": {},
        "sample_predictions": [],
        "model_version": MODEL_VERSION,
        "uncertainty_reason": reason,
    }


def _sample_type_counts(samples: list[GenderPresentationSample]) -> dict[str, int]:
    counts = {key: 0 for key in SAMPLE_WEIGHTS}
    for sample in samples:
        counts[sample.sample_type] = counts.get(sample.sample_type, 0) + 1
    return {key: value for key, value in counts.items() if value}


def _evidence_quality(sample_type_counts: dict[str, int], sample_count: int) -> str:
    body_count = int(sample_type_counts.get("body") or 0)
    face_count = int(sample_type_counts.get("face") or 0)
    if sample_count <= 0:
        return "poor"
    if body_count >= 4 and face_count >= 4 and sample_count >= 8:
        return "clear"
    if body_count or face_count:
        return "partial"
    return "poor"


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
