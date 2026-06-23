from __future__ import annotations

import os
import sys
import threading
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image

from app.core.config import PROJECT_ROOT, settings


COLORS = [
    "black",
    "white",
    "gray",
    "red",
    "orange",
    "yellow",
    "green",
    "blue",
    "purple",
    "brown",
    "pink",
    "striped",
]

LIP_INPUT_SIZE = [473, 473]
UPPER_LABELS = {5, 7}
DRESS_LABELS = {6, 10}
PROFILE_REALTIME_BALANCED_PROMPT_V2 = [
    ("ensemble_garment", "schp_upper_tight_masked", 0.50),
    ("ensemble_surveillance", "torso", 0.50),
]

_PIPELINE_LOCK = threading.Lock()
_PIPELINE: _ClipSchpUpperColorPipeline | None = None
_UNAVAILABLE_REASON: str | None = None


class UpperColorNoUsableCrop(ValueError):
    pass


@dataclass(frozen=True)
class UpperColorPrediction:
    color: str
    confidence: float
    visible: bool
    valid_pixel_ratio: float | None
    diagnostics: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "color": self.color,
            "confidence": self.confidence,
            "visible": self.visible,
            "valid_pixel_ratio": self.valid_pixel_ratio,
            "diagnostics": self.diagnostics,
        }


def predict_upper_color(image_bgr: np.ndarray, body_box: dict) -> dict[str, Any] | None:
    global _UNAVAILABLE_REASON
    if _UNAVAILABLE_REASON and settings.upper_color_clip_fail_open:
        return None
    try:
        pipeline = _get_pipeline()
        return pipeline.predict(image_bgr, body_box).as_dict()
    except UpperColorNoUsableCrop:
        return None
    except Exception as exc:
        if not settings.upper_color_clip_fail_open:
            raise
        _UNAVAILABLE_REASON = f"{type(exc).__name__}: {exc}"
        return None


def unavailable_reason() -> str | None:
    return _UNAVAILABLE_REASON


def reset_pipeline_for_tests() -> None:
    global _PIPELINE, _UNAVAILABLE_REASON
    with _PIPELINE_LOCK:
        _PIPELINE = None
        _UNAVAILABLE_REASON = None


def _get_pipeline() -> "_ClipSchpUpperColorPipeline":
    global _PIPELINE
    with _PIPELINE_LOCK:
        if _PIPELINE is None:
            _PIPELINE = _ClipSchpUpperColorPipeline()
        return _PIPELINE


class _ClipSchpUpperColorPipeline:
    def __init__(self) -> None:
        import torch
        from transformers import CLIPModel, CLIPProcessor

        if settings.upper_color_clip_backend != "hf":
            raise ValueError(f"unsupported online CLIP backend: {settings.upper_color_clip_backend}")
        if settings.upper_color_clip_profile != "profile_realtime_balanced_prompt_v2":
            raise ValueError(f"unsupported online CLIP profile: {settings.upper_color_clip_profile}")

        self.torch = torch
        self.device = _resolve_device(settings.upper_color_clip_device, torch)
        model_dir = settings.upper_color_clip_model_dir
        if not model_dir.exists():
            raise FileNotFoundError(f"CLIP model directory not found: {model_dir}")

        self.clip_model = CLIPModel.from_pretrained(str(model_dir), local_files_only=True).to(self.device)
        self.clip_processor = CLIPProcessor.from_pretrained(str(model_dir), local_files_only=True)
        self.clip_model.eval()
        self.temperature = float(settings.upper_color_clip_temperature)
        self._ensemble_features: dict[str, Any] = {}
        self.schp_model = self._load_schp_model()

    def predict(self, image_bgr: np.ndarray, body_box: dict) -> UpperColorPrediction:
        variants = self._crop_variants(image_bgr, body_box)
        weighted_probs: list[np.ndarray] = []
        weights: list[float] = []
        used: list[str] = []
        for ensemble_name, crop_name, weight in PROFILE_REALTIME_BALANCED_PROMPT_V2:
            roi = variants.get(crop_name)
            if roi is None:
                continue
            probs = self._predict_probs(roi, ensemble_name)
            weighted_probs.append(probs * float(weight))
            weights.append(float(weight))
            used.append(f"{ensemble_name}_{crop_name}")

        if not weighted_probs:
            raise UpperColorNoUsableCrop("no usable CLIP/SCHP upper-color crop")

        probs = np.stack(weighted_probs).sum(axis=0) / max(1e-6, sum(weights))
        total = float(probs.sum())
        if total > 0:
            probs = probs / total
        index = int(np.argmax(probs))
        color = COLORS[index]
        confidence = round(float(probs[index]), 6)
        visible = color in settings.clothing_color_labels and confidence >= settings.upper_color_clip_min_confidence
        valid_pixel_ratio = variants.get("_schp_upper_valid_ratio")
        if valid_pixel_ratio is None and "torso" in variants:
            valid_pixel_ratio = 1.0
        return UpperColorPrediction(
            color=color if visible else "unknown",
            confidence=confidence,
            visible=visible,
            valid_pixel_ratio=round(float(valid_pixel_ratio), 4) if valid_pixel_ratio is not None else None,
            diagnostics={
                "backend": "clip_schp",
                "model": "laion_CLIP-ViT-H-14-laion2B-s32B-b79K",
                "profile": settings.upper_color_clip_profile,
                "profile_spec": used,
                "temperature": self.temperature,
                "probs": {color_name: round(float(probs[i]), 6) for i, color_name in enumerate(COLORS)},
            },
        )

    def _predict_probs(self, roi_bgr: np.ndarray, ensemble_name: str) -> np.ndarray:
        text_features = self._text_features(ensemble_name)
        image_feature = self._image_feature(roi_bgr)
        scores = image_feature @ text_features.T
        probs = self.torch.softmax(scores * self.temperature, dim=0).detach().cpu().numpy()
        return probs.astype(np.float32)

    def _image_feature(self, roi_bgr: np.ndarray):
        image = _roi_to_pil(roi_bgr)
        inputs = self.clip_processor(images=image, return_tensors="pt").to(self.device)
        with self.torch.no_grad():
            features = self.clip_model.get_image_features(**inputs)
            features = features / features.norm(dim=-1, keepdim=True)
        return features[0]

    def _text_features(self, ensemble_name: str):
        cached = self._ensemble_features.get(ensemble_name)
        if cached is not None:
            return cached
        prompt_by_color = _prompt_ensembles()[ensemble_name]
        color_features = []
        for color in COLORS:
            prompts = prompt_by_color[color]
            inputs = self.clip_processor(text=prompts, return_tensors="pt", padding=True).to(self.device)
            with self.torch.no_grad():
                features = self.clip_model.get_text_features(**inputs)
                features = features / features.norm(dim=-1, keepdim=True)
            feature = features.mean(dim=0)
            feature = feature / feature.norm(dim=-1, keepdim=True)
            color_features.append(feature)
        text_features = self.torch.stack(color_features, dim=0)
        self._ensemble_features[ensemble_name] = text_features
        return text_features

    def _load_schp_model(self):
        _ensure_schp_import_path()
        import networks  # noqa: WPS433

        checkpoint_path = _resolve_schp_checkpoint()
        if not checkpoint_path.exists():
            raise FileNotFoundError(f"SCHP checkpoint not found: {checkpoint_path}")

        checkpoint = self.torch.load(str(checkpoint_path), map_location="cpu")
        state_dict = OrderedDict()
        for key, value in checkpoint["state_dict"].items():
            state_dict[key[7:] if key.startswith("module.") else key] = value

        model = networks.init_model("resnet101", num_classes=20, pretrained=None)
        model.load_state_dict(state_dict)
        model.to(self.device)
        model.eval()
        return model

    def _crop_variants(self, image_bgr: np.ndarray, body_box: dict) -> dict[str, np.ndarray | float]:
        variants: dict[str, np.ndarray | float] = {}
        torso = _crop_box_ratio(image_bgr, body_box, y_start=0.22, y_end=0.62, x_keep=0.72)
        if torso is not None:
            variants["torso"] = _square_pad_bgr(torso)

        body_crop = _body_crop(image_bgr, body_box)
        if body_crop is None:
            return variants

        pred = self._predict_parsing(body_crop)
        upper_mask = _upper_mask(pred)
        if int(upper_mask.sum()) < settings.upper_color_schp_min_mask_pixels:
            return variants

        kernel = np.ones((3, 3), dtype=np.uint8)
        upper_mask = cv2.morphologyEx(upper_mask.astype(np.uint8), cv2.MORPH_CLOSE, kernel).astype(bool)
        bounds = _mask_bounds(upper_mask)
        if not bounds:
            return variants
        x1, y1, x2, y2 = bounds
        tight_raw = body_crop[y1:y2, x1:x2]
        tight_mask = upper_mask[y1:y2, x1:x2]
        if tight_raw.size:
            variants["schp_upper_tight_masked"] = _square_pad_bgr(_masked_crop(tight_raw, tight_mask))
            variants["_schp_upper_valid_ratio"] = float(upper_mask.sum() / max(1, upper_mask.size))
        return variants

    def _predict_parsing(self, image_bgr: np.ndarray) -> np.ndarray:
        import torchvision.transforms as transforms

        _ensure_schp_import_path()
        from utils.transforms import get_affine_transform, transform_logits  # noqa: WPS433

        height, width = image_bgr.shape[:2]
        center, scale = _box_to_center_scale(width, height, LIP_INPUT_SIZE)
        trans = get_affine_transform(center, scale, 0, np.asarray(LIP_INPUT_SIZE))
        warped = cv2.warpAffine(
            image_bgr,
            trans,
            (int(LIP_INPUT_SIZE[1]), int(LIP_INPUT_SIZE[0])),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0),
        )
        transform = transforms.Compose(
            [
                transforms.ToTensor(),
                transforms.Normalize(mean=[0.406, 0.456, 0.485], std=[0.225, 0.224, 0.229]),
            ]
        )
        image_tensor = transform(warped).unsqueeze(0).to(self.device)
        with self.torch.no_grad():
            output = self.schp_model(image_tensor)
            upsample = self.torch.nn.functional.interpolate(
                output[0][-1],
                size=LIP_INPUT_SIZE,
                mode="bilinear",
                align_corners=True,
            )
        logits = upsample[0].permute(1, 2, 0).detach().cpu().numpy()
        logits = transform_logits(logits, center, scale, width, height, input_size=LIP_INPUT_SIZE)
        return np.argmax(logits, axis=2).astype(np.uint8)


def _resolve_device(device: str, torch_module) -> str:
    selected = device.strip() or "cpu"
    if selected.startswith("cuda") and not torch_module.cuda.is_available():
        return "cpu"
    return selected


def _resolve_schp_checkpoint() -> Path:
    checkpoint = settings.upper_color_schp_checkpoint
    if checkpoint.exists():
        return checkpoint
    fallback = PROJECT_ROOT / "data" / "models" / "schp" / "checkpoints" / "exp-schp-201908261155-lip.pth"
    return fallback.resolve()


def _ensure_schp_import_path() -> None:
    root = str(settings.upper_color_schp_root)
    os.environ["PATH"] = f"{sys.prefix}/bin:{os.environ.get('PATH', '')}"
    if root not in sys.path:
        sys.path.insert(0, root)


def _prompt_ensembles() -> dict[str, dict[str, list[str]]]:
    color_words = {
        "black": ["black"],
        "white": ["white"],
        "gray": ["gray", "grey"],
        "red": ["red"],
        "orange": ["orange"],
        "yellow": ["yellow"],
        "green": ["green"],
        "blue": ["blue"],
        "purple": ["purple", "violet"],
        "brown": ["brown", "tan"],
        "pink": ["pink"],
        "striped": ["striped", "stripe patterned", "with stripes"],
    }
    surveillance_templates = [
        "a cropped surveillance image of a person wearing a {color} upper garment",
        "a surveillance photo of a person wearing a {color} shirt",
        "a low resolution security camera image of a {color} top",
        "a photo of a person wearing a {color} top",
        "the upper body clothing is {color}",
    ]
    garment_templates = [
        "a {color} shirt",
        "a {color} jacket",
        "a {color} hoodie",
        "a {color} coat",
        "a {color} upper garment",
    ]
    return {
        "ensemble_surveillance": {
            color: [template.format(color=word) for word in color_words[color] for template in surveillance_templates]
            for color in COLORS
        },
        "ensemble_garment": {
            color: [template.format(color=word) for word in color_words[color] for template in garment_templates]
            for color in COLORS
        },
    }


def _roi_to_pil(roi_bgr: np.ndarray) -> Image.Image:
    rgb = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)


def _clamp_bbox(box: dict, width: int, height: int) -> dict:
    x1 = max(0, min(width - 1, int(round(float(box["x1"])))))
    y1 = max(0, min(height - 1, int(round(float(box["y1"])))))
    x2 = max(x1 + 1, min(width, int(round(float(box["x2"])))))
    y2 = max(y1 + 1, min(height, int(round(float(box["y2"])))))
    return {"x1": x1, "y1": y1, "x2": x2, "y2": y2, "width": x2 - x1, "height": y2 - y1}


def _crop_box_ratio(
    image_bgr: np.ndarray,
    body_box: dict,
    *,
    y_start: float,
    y_end: float,
    x_keep: float,
) -> np.ndarray | None:
    height, width = image_bgr.shape[:2]
    box = _clamp_bbox(body_box, width, height)
    body_w = max(1, int(box["width"]))
    body_h = max(1, int(box["height"]))
    cx = float(box["x1"]) + body_w / 2.0
    keep = max(0.1, min(1.0, x_keep))
    x1 = int(round(cx - body_w * keep / 2.0))
    x2 = int(round(cx + body_w * keep / 2.0))
    y1 = int(round(float(box["y1"]) + body_h * y_start))
    y2 = int(round(float(box["y1"]) + body_h * y_end))
    x1 = max(0, min(width - 1, x1))
    x2 = max(x1 + 1, min(width, x2))
    y1 = max(0, min(height - 1, y1))
    y2 = max(y1 + 1, min(height, y2))
    if (x2 - x1) * (y2 - y1) < settings.min_clothing_roi_area:
        return None
    return image_bgr[y1:y2, x1:x2]


def _body_crop(image_bgr: np.ndarray, body_box: dict) -> np.ndarray | None:
    height, width = image_bgr.shape[:2]
    box = _clamp_bbox(body_box, width, height)
    crop = image_bgr[box["y1"] : box["y2"], box["x1"] : box["x2"]]
    return crop if crop.size else None


def _square_pad_bgr(image_bgr: np.ndarray, *, value: int = 128) -> np.ndarray:
    height, width = image_bgr.shape[:2]
    side = max(height, width)
    out = np.full((side, side, 3), value, dtype=image_bgr.dtype)
    y1 = (side - height) // 2
    x1 = (side - width) // 2
    out[y1 : y1 + height, x1 : x1 + width] = image_bgr
    return out


def _masked_crop(crop_bgr: np.ndarray, mask: np.ndarray, *, background: int = 128) -> np.ndarray:
    out = np.full_like(crop_bgr, background)
    out[mask] = crop_bgr[mask]
    return out


def _mask_bounds(mask: np.ndarray, *, pad_ratio: float = 0.10) -> tuple[int, int, int, int] | None:
    ys, xs = np.where(mask)
    if ys.size == 0 or xs.size == 0:
        return None
    y1, y2 = int(ys.min()), int(ys.max()) + 1
    x1, x2 = int(xs.min()), int(xs.max()) + 1
    height, width = mask.shape[:2]
    pad_y = int(round((y2 - y1) * pad_ratio))
    pad_x = int(round((x2 - x1) * pad_ratio))
    y1 = max(0, y1 - pad_y)
    y2 = min(height, y2 + pad_y)
    x1 = max(0, x1 - pad_x)
    x2 = min(width, x2 + pad_x)
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


def _box_to_center_scale(width: int, height: int, input_size: list[int]) -> tuple[np.ndarray, np.ndarray]:
    aspect_ratio = input_size[1] / input_size[0]
    w = float(width - 1)
    h = float(height - 1)
    center = np.asarray([w * 0.5, h * 0.5], dtype=np.float32)
    if w > aspect_ratio * h:
        h = w / aspect_ratio
    elif w < aspect_ratio * h:
        w = h * aspect_ratio
    scale = np.asarray([w, h], dtype=np.float32)
    return center, scale


def _upper_mask(pred: np.ndarray) -> np.ndarray:
    height = pred.shape[0]
    y_indices = np.arange(height)[:, None]
    return np.isin(pred, list(UPPER_LABELS)) | (
        np.isin(pred, list(DRESS_LABELS)) & (y_indices < int(height * 0.58))
    )
