from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import settings  # noqa: E402
from app.storage import db  # noqa: E402
from app.vision import person_analysis  # noqa: E402


DEFAULT_MODEL_DIR = ROOT / "data" / "models" / "clip" / "openai_clip-vit-base-patch32"
DEFAULT_LABEL_PATH = ROOT / "data" / "evals" / "manual_outfit_labels" / "outfit_labels.json"
DEFAULT_OUTPUT = ROOT / "data" / "evals" / "clip_upper_color" / "clip_upper_color_eval.json"

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

BASE_CROP_NAMES = ["upper_center", "upper_wide", "torso", "body_no_head", "full_body"]
SCHP_CROP_NAMES = [
    "schp_upper_masked",
    "schp_upper_tight_masked",
    "schp_upper_tight_filled",
    "schp_upper_tight_raw",
]
CROP_MODE_CHOICES = ["all", *BASE_CROP_NAMES, *SCHP_CROP_NAMES]


class ClipRunner:
    def __init__(
        self,
        model_dir: Path,
        *,
        backend: str,
        device: str,
        open_clip_model_name: str | None = None,
        open_clip_pretrained: str | None = None,
    ) -> None:
        self.model_dir = model_dir
        self.device = device
        self.image_feature_calls = 0
        self.image_feature_seconds = 0.0
        self.text_feature_calls = 0
        self.text_feature_seconds = 0.0
        selected = backend
        if selected == "auto":
            if (model_dir / "open_clip_model.safetensors").exists():
                selected = "open_clip"
            elif "siglip" in model_dir.name.lower():
                selected = "siglip"
            else:
                selected = "hf"
        self.backend = selected
        if self.backend == "open_clip":
            import open_clip

            if open_clip_model_name and open_clip_pretrained:
                self.model, _, self.preprocess = open_clip.create_model_and_transforms(
                    open_clip_model_name,
                    pretrained=open_clip_pretrained,
                    device=device,
                    output_dict=True,
                )
                self.tokenizer = open_clip.get_tokenizer(open_clip_model_name)
            else:
                checkpoint = model_dir / "open_clip_model.safetensors"
                if not checkpoint.exists():
                    raise FileNotFoundError(f"OpenCLIP checkpoint not found: {checkpoint}")
                self.model, _, self.preprocess = open_clip.create_model_and_transforms(
                    "ViT-B-16",
                    pretrained=str(checkpoint),
                    device=device,
                    output_dict=True,
                )
                self.tokenizer = open_clip.get_tokenizer("ViT-B-16")
            self.model.eval()
            return
        if self.backend == "siglip":
            from transformers import SiglipModel, SiglipProcessor

            self.model = SiglipModel.from_pretrained(str(model_dir), local_files_only=True).to(device)
            self.processor = SiglipProcessor.from_pretrained(str(model_dir), local_files_only=True)
            self.model.eval()
            return
        if self.backend != "hf":
            raise ValueError(f"unsupported CLIP backend: {backend}")
        self.model = CLIPModel.from_pretrained(str(model_dir), local_files_only=True).to(device)
        self.processor = CLIPProcessor.from_pretrained(str(model_dir), local_files_only=True)
        self.model.eval()

    def text_features(self, prompts: list[str]) -> torch.Tensor:
        started_at = time.perf_counter()
        if self.backend == "open_clip":
            tokens = self.tokenizer(prompts).to(self.device)
            with torch.no_grad():
                features = self.model.encode_text(tokens, normalize=True)
            out = features / features.norm(dim=-1, keepdim=True)
            self.text_feature_calls += 1
            self.text_feature_seconds += time.perf_counter() - started_at
            return out

        if self.backend == "siglip":
            inputs = self.processor(text=prompts, return_tensors="pt", padding=True).to(self.device)
            with torch.no_grad():
                features = self.model.get_text_features(**inputs)
            self.text_feature_calls += 1
            self.text_feature_seconds += time.perf_counter() - started_at
            return features

        inputs = self.processor(text=prompts, return_tensors="pt", padding=True).to(self.device)
        with torch.no_grad():
            features = self.model.get_text_features(**inputs)
        out = features / features.norm(dim=-1, keepdim=True)
        self.text_feature_calls += 1
        self.text_feature_seconds += time.perf_counter() - started_at
        return out

    def image_feature(self, roi_bgr: np.ndarray) -> torch.Tensor:
        started_at = time.perf_counter()
        image = _roi_to_pil(roi_bgr)
        if self.backend == "open_clip":
            inputs = self.preprocess(image).unsqueeze(0).to(self.device)
            with torch.no_grad():
                features = self.model.encode_image(inputs, normalize=True)
            out = features[0] / features[0].norm(dim=-1, keepdim=True)
            self.image_feature_calls += 1
            self.image_feature_seconds += time.perf_counter() - started_at
            return out

        if self.backend == "siglip":
            inputs = self.processor(images=image, return_tensors="pt").to(self.device)
            with torch.no_grad():
                features = self.model.get_image_features(**inputs)
            out = features[0]
            self.image_feature_calls += 1
            self.image_feature_seconds += time.perf_counter() - started_at
            return out

        inputs = self.processor(images=image, return_tensors="pt").to(self.device)
        with torch.no_grad():
            features = self.model.get_image_features(**inputs)
            features = features / features.norm(dim=-1, keepdim=True)
        out = features[0]
        self.image_feature_calls += 1
        self.image_feature_seconds += time.perf_counter() - started_at
        return out

    def similarity_scores(self, image_feature: torch.Tensor, text_features: torch.Tensor) -> torch.Tensor:
        scores = image_feature @ text_features.T
        if self.backend == "siglip":
            logit_scale = self.model.logit_scale.exp()
            logit_bias = self.model.logit_bias
            scores = scores * logit_scale + logit_bias
        return scores


@dataclass(frozen=True)
class SampleImage:
    image_bgr: np.ndarray
    body_box: dict
    source: str


def _prompt_sets() -> dict[str, list[str]]:
    return {
        "plain": [
            "black shirt",
            "white shirt",
            "gray shirt",
            "red shirt",
            "orange shirt",
            "yellow shirt",
            "green shirt",
            "blue shirt",
            "purple shirt",
            "brown shirt",
            "pink shirt",
            "striped shirt",
        ],
        "surveillance": [
            "a cropped surveillance image of a person wearing a black upper garment",
            "a cropped surveillance image of a person wearing a white upper garment",
            "a cropped surveillance image of a person wearing a gray upper garment",
            "a cropped surveillance image of a person wearing a red upper garment",
            "a cropped surveillance image of a person wearing an orange upper garment",
            "a cropped surveillance image of a person wearing a yellow upper garment",
            "a cropped surveillance image of a person wearing a green upper garment",
            "a cropped surveillance image of a person wearing a blue upper garment",
            "a cropped surveillance image of a person wearing a purple upper garment",
            "a cropped surveillance image of a person wearing a brown upper garment",
            "a cropped surveillance image of a person wearing a pink upper garment",
            "a cropped surveillance image of a person wearing a striped upper garment",
        ],
        "photo": [
            "a photo of a person wearing a black top",
            "a photo of a person wearing a white top",
            "a photo of a person wearing a gray top",
            "a photo of a person wearing a red top",
            "a photo of a person wearing an orange top",
            "a photo of a person wearing a yellow top",
            "a photo of a person wearing a green top",
            "a photo of a person wearing a blue top",
            "a photo of a person wearing a purple top",
            "a photo of a person wearing a brown top",
            "a photo of a person wearing a pink top",
            "a photo of a person wearing a striped top",
        ],
    }


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
    templates = [
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
    surveillance: dict[str, list[str]] = {}
    garment: dict[str, list[str]] = {}
    mixed: dict[str, list[str]] = {}
    for color in COLORS:
        words = color_words[color]
        surveillance[color] = [template.format(color=word) for word in words for template in templates]
        garment[color] = [template.format(color=word) for word in words for template in garment_templates]
        mixed[color] = surveillance[color] + garment[color]
    return {
        "ensemble_surveillance": surveillance,
        "ensemble_garment": garment,
        "ensemble_mixed": mixed,
    }


def _load_manual_items(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    labels = data.get("labels", {})
    if not isinstance(labels, dict):
        raise ValueError("manual outfit labels must contain a labels object")

    items: list[dict[str, Any]] = []
    for label in labels.values():
        if not isinstance(label, dict):
            continue
        if not (label.get("source") == "manual_person_outfit_grouping" or label.get("manual_grouping")):
            continue
        person_id = str(label.get("person_id") or "")
        assignments_by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for assignment in label.get("manual_split_assignments") or []:
            if not isinstance(assignment, dict):
                continue
            split_group = str(assignment.get("split_group") or "unassigned")
            if split_group in {"unassigned", "exclude"}:
                continue
            event_id = str(assignment.get("event_id") or "")
            observation_id = str(assignment.get("observation_id") or "")
            if not event_id and not observation_id:
                continue
            assignments_by_group[split_group].append(
                {
                    "event_id": event_id,
                    "observation_id": observation_id,
                }
            )

        for split_group, group_label in (label.get("manual_split_group_labels") or {}).items():
            if not isinstance(group_label, dict):
                continue
            color = str(group_label.get("upper_color") or "unknown")
            if color == "unknown":
                continue
            for assignment in assignments_by_group.get(str(split_group), []):
                sample_key = assignment.get("observation_id") or assignment.get("event_id")
                items.append(
                    {
                        "sample_key": sample_key,
                        "person_id": person_id,
                        "split_group": str(split_group),
                        "event_id": assignment.get("event_id") or "",
                        "observation_id": assignment.get("observation_id") or "",
                        "upper_color": color,
                    }
                )
    return items


def _roi_to_pil(roi_bgr: np.ndarray) -> Image.Image:
    rgb = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)


def _square_pad_bgr(image_bgr: np.ndarray, *, value: int = 128) -> np.ndarray:
    height, width = image_bgr.shape[:2]
    side = max(height, width)
    out = np.full((side, side, 3), value, dtype=image_bgr.dtype)
    y1 = (side - height) // 2
    x1 = (side - width) // 2
    out[y1 : y1 + height, x1 : x1 + width] = image_bgr
    return out


def _crop_box_ratio(
    image_bgr: np.ndarray,
    body_box: dict,
    *,
    y_start: float,
    y_end: float,
    x_keep: float,
) -> np.ndarray | None:
    height, width = image_bgr.shape[:2]
    box = person_analysis.clamp_bbox(body_box, width, height)
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
    box = person_analysis.clamp_bbox(body_box, width, height)
    crop = image_bgr[box["y1"] : box["y2"], box["x1"] : box["x2"]]
    return crop if crop.size else None


def _masked_crop(crop_bgr: np.ndarray, mask: np.ndarray, *, background: int = 128) -> np.ndarray:
    out = np.full_like(crop_bgr, background)
    out[mask] = crop_bgr[mask]
    return out


def _filled_mask_crop(crop_bgr: np.ndarray, mask: np.ndarray) -> np.ndarray:
    pixels = crop_bgr[mask]
    if pixels.size == 0:
        return _masked_crop(crop_bgr, mask)
    fill = np.median(pixels.reshape(-1, 3), axis=0).astype(np.uint8)
    out = np.empty_like(crop_bgr)
    out[:, :] = fill
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


def _schp_upper_variants(
    sample: SampleImage,
    *,
    schp_model: Any | None,
    device: str,
) -> dict[str, np.ndarray]:
    if schp_model is None:
        return {}
    body_crop = _body_crop(sample.image_bgr, sample.body_box)
    if body_crop is None:
        return {}

    from scripts.evaluate_schp_clothes import _part_masks, _predict_parsing  # noqa: WPS433

    pred = _predict_parsing(schp_model, body_crop, device)
    upper_mask, _ = _part_masks(pred)
    if int(upper_mask.sum()) < 250:
        return {}

    kernel = np.ones((3, 3), dtype=np.uint8)
    upper_mask = cv2.morphologyEx(upper_mask.astype(np.uint8), cv2.MORPH_CLOSE, kernel).astype(bool)
    masked = _masked_crop(body_crop, upper_mask)
    variants = {"schp_upper_masked": _square_pad_bgr(masked)}

    bounds = _mask_bounds(upper_mask)
    if bounds:
        x1, y1, x2, y2 = bounds
        tight_raw = body_crop[y1:y2, x1:x2]
        tight_mask = upper_mask[y1:y2, x1:x2]
        if tight_raw.size:
            variants["schp_upper_tight_raw"] = _square_pad_bgr(tight_raw)
            variants["schp_upper_tight_masked"] = _square_pad_bgr(_masked_crop(tight_raw, tight_mask))
            variants["schp_upper_tight_filled"] = _square_pad_bgr(_filled_mask_crop(tight_raw, tight_mask))
    return variants


def _crop_variants(
    sample: SampleImage,
    *,
    schp_model: Any | None = None,
    device: str = "cpu",
) -> dict[str, np.ndarray]:
    image = sample.image_bgr
    body = sample.body_box
    variants: dict[str, np.ndarray] = {}
    specs = {
        "upper_center": (
            settings.upper_roi_start_ratio,
            settings.upper_roi_end_ratio,
            settings.clothing_roi_center_width_ratio,
        ),
        "upper_wide": (0.18, 0.54, 0.82),
        "torso": (0.22, 0.62, 0.72),
        "body_no_head": (0.16, 0.72, 0.82),
        "full_body": (0.0, 0.98, 0.92),
    }
    for name, (y_start, y_end, x_keep) in specs.items():
        roi = _crop_box_ratio(image, body, y_start=y_start, y_end=y_end, x_keep=x_keep)
        if roi is not None and roi.size:
            variants[name] = _square_pad_bgr(roi)
    variants.update(_schp_upper_variants(sample, schp_model=schp_model, device=device))
    return variants


def _sample_image(item: dict[str, Any]) -> tuple[SampleImage | None, str]:
    observation = db.get_person_observation(item.get("observation_id") or "") if item.get("observation_id") else None
    event = db.get_event(item.get("event_id") or "") if item.get("event_id") else None
    source = "manual_observation"

    image = None
    body_box = None
    if observation and observation.get("frame_path"):
        image = cv2.imread(observation["frame_path"])
        body_box = observation.get("person_bbox")

    if image is None and event and event.get("representative_frame_path"):
        image = cv2.imread(event["representative_frame_path"])
        source = "event_representative"
    if body_box is None and event and event.get("representative_observation_id"):
        representative = db.get_person_observation(event["representative_observation_id"])
        if representative:
            body_box = representative.get("person_bbox")
            if image is None and representative.get("frame_path"):
                image = cv2.imread(representative["frame_path"])
                source = "event_observation"

    if image is None:
        return None, "frame_missing"

    if body_box is None:
        face_record = None
        if observation and observation.get("face_record_id"):
            face_record = db.get_face_record(observation["face_record_id"])
        if face_record is None and event and event.get("representative_face_id"):
            face_record = db.get_face_record(event["representative_face_id"])
        if face_record and face_record.get("bbox"):
            body_box = person_analysis.estimate_body_bbox_from_face(
                face_record["bbox"],
                image.shape[1],
                image.shape[0],
            )
            source = f"{source}_face_estimated"

    if body_box is None:
        return None, "body_missing"
    return SampleImage(image, body_box, source), source


def _text_features(
    *,
    runner: ClipRunner,
    prompts: list[str],
) -> torch.Tensor:
    return runner.text_features(prompts)


def _ensemble_text_features(
    *,
    runner: ClipRunner,
    prompt_by_color: dict[str, list[str]],
) -> torch.Tensor:
    color_features = []
    for color in COLORS:
        prompts = prompt_by_color[color]
        features = _text_features(runner=runner, prompts=prompts)
        feature = features.mean(dim=0)
        if runner.backend != "siglip":
            feature = feature / feature.norm(dim=-1, keepdim=True)
        color_features.append(feature)
    return torch.stack(color_features, dim=0)


def _image_feature(
    *,
    runner: ClipRunner,
    roi_bgr: np.ndarray,
) -> torch.Tensor:
    return runner.image_feature(roi_bgr)


def _predict(
    *,
    runner: ClipRunner,
    text_features: torch.Tensor,
    roi_bgr: np.ndarray,
    temperature: float,
) -> tuple[str, float, dict[str, float]]:
    image_features = runner.image_feature(roi_bgr)
    logits = runner.similarity_scores(image_features, text_features)
    probs = torch.softmax(logits * temperature, dim=0).detach().cpu().numpy()
    index = int(np.argmax(probs))
    return COLORS[index], float(probs[index]), {
        color: round(float(probs[i]), 6) for i, color in enumerate(COLORS)
    }


def _predict_from_scores(scores: np.ndarray, *, temperature: float) -> tuple[str, float, dict[str, float]]:
    logits = torch.from_numpy(scores.astype(np.float32))
    probs = torch.softmax(logits * temperature, dim=0).detach().cpu().numpy()
    return _predict_from_probs(probs)


def _predict_from_probs(probs: np.ndarray) -> tuple[str, float, dict[str, float]]:
    index = int(np.argmax(probs))
    return COLORS[index], float(probs[index]), {
        color: round(float(probs[i]), 6) for i, color in enumerate(COLORS)
    }


def _probs_from_scores(scores: np.ndarray, *, temperature: float) -> np.ndarray:
    logits = torch.from_numpy(scores.astype(np.float32))
    return torch.softmax(logits * temperature, dim=0).detach().cpu().numpy().astype(np.float32)


def _pixels_without_constant_background(roi_bgr: np.ndarray, *, background: int = 128) -> np.ndarray:
    if roi_bgr is None or roi_bgr.size == 0:
        return np.empty((0, 3), dtype=np.uint8)
    pixels = roi_bgr.reshape(-1, 3)
    keep = np.any(np.abs(pixels.astype(np.int16) - background) > 2, axis=1)
    return pixels[keep]


def _masked_rule_color(roi_bgr: np.ndarray | None) -> tuple[str, float, dict[str, float]]:
    if roi_bgr is None or roi_bgr.size == 0:
        return "unknown", 0.0, {"valid_pixel_ratio": 0.0}

    pixels = _pixels_without_constant_background(roi_bgr)
    valid_ratio = float(len(pixels) / max(1, roi_bgr.shape[0] * roi_bgr.shape[1]))
    if len(pixels) < 120 or valid_ratio < 0.03:
        return "unknown", 0.0, {"valid_pixel_ratio": round(valid_ratio, 4)}

    compact = pixels.reshape(1, -1, 3)
    hsv = cv2.cvtColor(compact, cv2.COLOR_BGR2HSV).reshape(-1, 3).astype(np.float32)
    lab = cv2.cvtColor(compact, cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.float32)
    bgr = pixels.astype(np.float32)

    h = hsv[:, 0]
    s = hsv[:, 1]
    v = hsv[:, 2]
    lab_l = lab[:, 0]
    lab_a = lab[:, 1]
    lab_b = lab[:, 2]
    spread = bgr.max(axis=1) - bgr.min(axis=1)
    chroma = np.sqrt((lab_a - 128.0) ** 2 + (lab_b - 128.0) ** 2)

    low_chroma_ratio = float(np.mean((chroma <= 26) | (s <= 50) | (spread <= 34)))
    dark_ratio = float(np.mean((v < 78) | (lab_l < 72)))
    deep_dark_ratio = float(np.mean((v < 58) | (lab_l < 55)))
    bright_ratio = float(np.mean((v >= 174) & ((s <= 86) | (spread <= 50) | (chroma <= 32))))
    very_bright_ratio = float(np.mean((v >= 190) & ((s <= 82) | (spread <= 44) | (chroma <= 30))))
    median_l = float(np.median(lab_l))
    median_s = float(np.median(s))
    median_chroma = float(np.median(chroma))

    stripe_score = person_analysis._striped_score(roi_bgr)
    if stripe_score >= 0.30 and len(pixels) >= 450:
        return "striped", round(min(0.98, stripe_score * (0.55 + min(valid_ratio, 0.45))), 4), {
            "valid_pixel_ratio": round(valid_ratio, 4),
            "stripe_score": round(float(stripe_score), 4),
        }

    if deep_dark_ratio >= 0.42 or (dark_ratio >= 0.58 and median_l < 82):
        confidence = max(deep_dark_ratio, dark_ratio * 0.86)
        return "black", round(min(0.98, confidence), 4), {
            "valid_pixel_ratio": round(valid_ratio, 4),
            "dark_ratio": round(dark_ratio, 4),
            "low_chroma_ratio": round(low_chroma_ratio, 4),
        }

    if very_bright_ratio >= 0.34 or (bright_ratio >= 0.48 and median_l >= 142):
        confidence = max(very_bright_ratio, bright_ratio * 0.92)
        return "white", round(min(0.96, confidence), 4), {
            "valid_pixel_ratio": round(valid_ratio, 4),
            "bright_ratio": round(bright_ratio, 4),
            "low_chroma_ratio": round(low_chroma_ratio, 4),
        }

    if low_chroma_ratio >= 0.62 or (median_s <= 58 and median_chroma <= 30):
        return "gray", round(min(0.95, max(low_chroma_ratio, 0.55)), 4), {
            "valid_pixel_ratio": round(valid_ratio, 4),
            "low_chroma_ratio": round(low_chroma_ratio, 4),
            "median_chroma": round(median_chroma, 4),
        }

    colorful = (s >= 58) & (v >= 45) & (spread >= 28)
    colorful_ratio = float(np.mean(colorful))
    if colorful_ratio < 0.12:
        return "unknown", 0.18, {
            "valid_pixel_ratio": round(valid_ratio, 4),
            "colorful_ratio": round(colorful_ratio, 4),
        }

    labels = [_color_from_hue_for_eval(float(hue), float(value)) for hue, value in zip(h[colorful], v[colorful])]
    counts = Counter(label for label in labels if label in COLORS)
    if not counts:
        return "unknown", 0.18, {"valid_pixel_ratio": round(valid_ratio, 4)}
    label, count = counts.most_common(1)[0]
    confidence = float(count / max(1, len(labels)))
    if confidence < 0.42:
        return "unknown", round(confidence, 4), {
            "valid_pixel_ratio": round(valid_ratio, 4),
            "colorful_ratio": round(colorful_ratio, 4),
        }
    return label, round(min(0.96, confidence), 4), {
        "valid_pixel_ratio": round(valid_ratio, 4),
        "colorful_ratio": round(colorful_ratio, 4),
    }


def _color_from_hue_for_eval(hue: float, value: float) -> str:
    if value < 135 and 8 <= hue <= 34:
        return "brown"
    if hue <= 7 or hue >= 170:
        return "red"
    if hue <= 18:
        return "orange"
    if hue <= 34:
        return "yellow"
    if hue <= 85:
        return "green"
    if hue <= 125:
        return "blue"
    if hue <= 145:
        return "purple"
    if hue <= 169:
        return "pink"
    return "unknown"


def _guarded_color(
    *,
    clip_color: str,
    clip_confidence: float,
    rule_color: str,
    rule_confidence: float,
) -> tuple[str, float, str]:
    if rule_color == "striped" and rule_confidence >= 0.24 and clip_confidence <= 0.20:
        return "striped", max(rule_confidence, clip_confidence), "masked_stripe_guard"
    if rule_color in {"black", "white", "gray"} and rule_confidence >= 0.62:
        if clip_color in {"blue", "purple", "red", "pink", "brown", "striped"} or clip_confidence <= 0.18:
            return rule_color, max(rule_confidence, clip_confidence), "masked_achromatic_guard"
    if rule_color in {"black", "white"} and rule_confidence >= 0.52 and clip_color in {"blue", "purple"}:
        return rule_color, max(rule_confidence, clip_confidence), "masked_blue_cast_guard"
    return clip_color, clip_confidence, "clip"


def _rule_color(roi_bgr: np.ndarray | None) -> tuple[str, float]:
    if roi_bgr is None or roi_bgr.size == 0:
        return "unknown", 0.0
    previous = settings.enable_upper_color_calibrator
    settings.enable_upper_color_calibrator = False
    try:
        result = person_analysis.classify_clothing_color(roi_bgr, part="upper")
    finally:
        settings.enable_upper_color_calibrator = previous
    return result.color or "unknown", float(result.confidence or 0.0)


def _fused_color(
    *,
    clip_color: str,
    clip_confidence: float,
    rule_color: str,
    rule_confidence: float,
) -> tuple[str, float, str]:
    if rule_color in {"black", "white", "gray"} and rule_confidence >= 0.48:
        return rule_color, max(rule_confidence, clip_confidence * 0.75), "achromatic_rule"
    if rule_color == "striped" and rule_confidence >= 0.35:
        return rule_color, max(rule_confidence, clip_confidence * 0.75), "stripe_rule"
    if clip_color in {"black", "white", "gray"} and rule_color in {"black", "white", "gray"}:
        if clip_color != rule_color and rule_confidence >= 0.36:
            return rule_color, max(rule_confidence, clip_confidence * 0.65), "achromatic_tie_rule"
    if clip_confidence < 0.26 and rule_color != "unknown" and rule_confidence >= 0.32:
        return rule_color, rule_confidence, "low_clip_rule"
    return clip_color, clip_confidence, "clip"


def _sample_metrics(items: list[dict[str, Any]], predicted_by_sample: dict[str, str]) -> dict[str, Any]:
    correct = 0
    confusion: Counter[tuple[str, str]] = Counter()
    for item in items:
        predicted = predicted_by_sample.get(item["sample_key"], "unknown")
        manual = item["upper_color"]
        is_correct = predicted == manual
        correct += 1 if is_correct else 0
        if not is_correct:
            confusion[(manual, predicted)] += 1
    total = len(items)
    return {
        "total": total,
        "correct": correct,
        "accuracy": round(correct / total, 4) if total else None,
        "confusion_top": [
            {"manual_color": manual, "predicted_color": predicted, "count": count}
            for (manual, predicted), count in confusion.most_common()
        ],
    }


def _group_metrics(items: list[dict[str, Any]], predicted_by_sample: dict[str, str]) -> dict[str, Any]:
    grouped: dict[tuple[str, str], list[str]] = defaultdict(list)
    truth: dict[tuple[str, str], str] = {}
    for item in items:
        key = (item["person_id"], item["split_group"])
        grouped[key].append(predicted_by_sample.get(item["sample_key"], "unknown"))
        truth[key] = item["upper_color"]

    correct = 0
    confusion: Counter[tuple[str, str]] = Counter()
    per_group = []
    for key, predictions in sorted(grouped.items()):
        predicted = Counter(predictions).most_common(1)[0][0] if predictions else "unknown"
        manual = truth[key]
        is_correct = predicted == manual
        correct += 1 if is_correct else 0
        if not is_correct:
            confusion[(manual, predicted)] += 1
        per_group.append(
            {
                "person_id": key[0],
                "split_group": key[1],
                "manual_upper_color": manual,
                "predicted_upper_color": predicted,
                "correct": is_correct,
                "prediction_counts": dict(Counter(predictions).most_common()),
            }
        )

    total = len(grouped)
    return {
        "total": total,
        "correct": correct,
        "accuracy": round(correct / total, 4) if total else None,
        "confusion_top": [
            {"manual_color": manual, "predicted_color": predicted, "count": count}
            for (manual, predicted), count in confusion.most_common()
        ],
        "per_group": per_group,
    }


def _score_group_metrics(
    items: list[dict[str, Any]],
    scores_by_sample: dict[str, np.ndarray],
    *,
    temperature: float,
) -> dict[str, Any]:
    grouped: dict[tuple[str, str], list[np.ndarray]] = defaultdict(list)
    truth: dict[tuple[str, str], str] = {}
    for item in items:
        key = (item["person_id"], item["split_group"])
        score = scores_by_sample.get(item["sample_key"])
        if score is not None:
            grouped[key].append(score.astype(np.float32))
        truth[key] = item["upper_color"]

    correct = 0
    confusion: Counter[tuple[str, str]] = Counter()
    per_group = []
    for key in sorted(truth):
        scores = grouped.get(key) or []
        if scores:
            avg_scores = np.stack(scores).mean(axis=0)
            predicted, confidence, probs = _predict_from_scores(avg_scores, temperature=temperature)
        else:
            predicted, confidence, probs = "unknown", 0.0, {}
        manual = truth[key]
        is_correct = predicted == manual
        correct += 1 if is_correct else 0
        if not is_correct:
            confusion[(manual, predicted)] += 1
        per_group.append(
            {
                "person_id": key[0],
                "split_group": key[1],
                "manual_upper_color": manual,
                "predicted_upper_color": predicted,
                "confidence": round(confidence, 6),
                "correct": is_correct,
                "sample_score_count": len(scores),
                "probs": probs,
            }
        )

    total = len(truth)
    return {
        "total": total,
        "correct": correct,
        "accuracy": round(correct / total, 4) if total else None,
        "confusion_top": [
            {"manual_color": manual, "predicted_color": predicted, "count": count}
            for (manual, predicted), count in confusion.most_common()
        ],
        "per_group": per_group,
    }


def _prob_group_metrics(
    items: list[dict[str, Any]],
    probs_by_sample: dict[str, np.ndarray],
) -> dict[str, Any]:
    grouped: dict[tuple[str, str], list[np.ndarray]] = defaultdict(list)
    truth: dict[tuple[str, str], str] = {}
    for item in items:
        key = (item["person_id"], item["split_group"])
        probs = probs_by_sample.get(item["sample_key"])
        if probs is not None:
            grouped[key].append(probs.astype(np.float32))
        truth[key] = item["upper_color"]

    correct = 0
    confusion: Counter[tuple[str, str]] = Counter()
    per_group = []
    for key in sorted(truth):
        sample_probs = grouped.get(key) or []
        if sample_probs:
            avg_probs = np.stack(sample_probs).mean(axis=0)
            predicted, confidence, probs = _predict_from_probs(avg_probs)
        else:
            predicted, confidence, probs = "unknown", 0.0, {}
        manual = truth[key]
        is_correct = predicted == manual
        correct += 1 if is_correct else 0
        if not is_correct:
            confusion[(manual, predicted)] += 1
        per_group.append(
            {
                "person_id": key[0],
                "split_group": key[1],
                "manual_upper_color": manual,
                "predicted_upper_color": predicted,
                "confidence": round(confidence, 6),
                "correct": is_correct,
                "sample_prob_count": len(sample_probs),
                "probs": probs,
            }
        )

    total = len(truth)
    return {
        "total": total,
        "correct": correct,
        "accuracy": round(correct / total, 4) if total else None,
        "confusion_top": [
            {"manual_color": manual, "predicted_color": predicted, "count": count}
            for (manual, predicted), count in confusion.most_common()
        ],
        "per_group": per_group,
    }


def _evaluate_predictions(items: list[dict[str, Any]], predictions: dict[str, str]) -> dict[str, Any]:
    event = _sample_metrics(items, predictions)
    group = _group_metrics(items, predictions)
    confusion: Counter[tuple[str, str]] = Counter()
    for item in items:
        predicted = predictions.get(item["sample_key"], "unknown")
        manual = item["upper_color"]
        if predicted != manual:
            confusion[(manual, predicted)] += 1
    return {
        "event_metrics": event,
        "group_metrics": group,
        "confusion_top": [
            {"manual_color": manual, "predicted_color": predicted, "count": count}
            for (manual, predicted), count in confusion.most_common(30)
        ],
    }


def _with_score_group_metrics(
    report: dict[str, Any],
    items: list[dict[str, Any]],
    scores_by_sample: dict[str, np.ndarray] | None,
    *,
    temperature: float,
) -> dict[str, Any]:
    if scores_by_sample:
        report["score_group_metrics"] = _score_group_metrics(
            items,
            scores_by_sample,
            temperature=temperature,
        )
    return report


def _evaluate_prob_predictions(
    items: list[dict[str, Any]],
    probs_by_sample: dict[str, np.ndarray],
) -> dict[str, Any]:
    predictions = {}
    details = []
    for item in items:
        sample_key = item["sample_key"]
        probs = probs_by_sample.get(sample_key)
        if probs is None:
            color, confidence, prob_map = "unknown", 0.0, {}
        else:
            color, confidence, prob_map = _predict_from_probs(probs)
        predictions[sample_key] = color
        details.append(
            {
                "sample_key": sample_key,
                "event_id": item["event_id"],
                "observation_id": item["observation_id"],
                "person_id": item["person_id"],
                "split_group": item["split_group"],
                "manual_upper_color": item["upper_color"],
                "predicted_upper_color": color,
                "confidence": round(confidence, 6),
                "correct": color == item["upper_color"],
                "probs": prob_map,
            }
        )
    return _evaluate_predictions(items, predictions) | {
        "prob_group_metrics": _prob_group_metrics(items, probs_by_sample),
        "details": details,
        "prediction_counts": dict(Counter(predictions.values()).most_common()),
    }


def _combine_prob_strategies(
    strategy_probs: dict[str, dict[str, np.ndarray]],
    spec: list[tuple[str, float]],
) -> dict[str, np.ndarray]:
    sample_keys = sorted({sample_key for name, _ in spec for sample_key in strategy_probs.get(name, {})})
    combined: dict[str, np.ndarray] = {}
    for sample_key in sample_keys:
        weighted = []
        weights = []
        for name, weight in spec:
            probs = strategy_probs.get(name, {}).get(sample_key)
            if probs is None:
                continue
            weighted.append(probs.astype(np.float32) * float(weight))
            weights.append(float(weight))
        if weighted:
            avg = np.stack(weighted).sum(axis=0) / max(1e-6, sum(weights))
            total = float(avg.sum())
            combined[sample_key] = (avg / total if total > 0 else avg).astype(np.float32)
    return combined


def _combine_score_strategies_as_probs(
    strategy_scores: dict[str, dict[str, np.ndarray]],
    spec: list[tuple[str, float]],
    *,
    temperature: float,
) -> dict[str, np.ndarray]:
    sample_keys = sorted({sample_key for name, _ in spec for sample_key in strategy_scores.get(name, {})})
    combined: dict[str, np.ndarray] = {}
    for sample_key in sample_keys:
        weighted = []
        weights = []
        for name, weight in spec:
            scores = strategy_scores.get(name, {}).get(sample_key)
            if scores is None:
                continue
            weighted.append(_probs_from_scores(scores, temperature=temperature) * float(weight))
            weights.append(float(weight))
        if weighted:
            avg = np.stack(weighted).sum(axis=0) / max(1e-6, sum(weights))
            total = float(avg.sum())
            combined[sample_key] = (avg / total if total > 0 else avg).astype(np.float32)
    return combined


def _parse_temperature_grid(value: str | None) -> list[float]:
    if not value:
        return []
    temperatures = []
    for raw in value.split(","):
        raw = raw.strip()
        if not raw:
            continue
        temp = float(raw)
        if temp <= 0:
            raise ValueError("temperature grid values must be positive")
        temperatures.append(temp)
    return sorted(set(temperatures))


def main() -> int:
    total_started_at = time.perf_counter()
    parser = argparse.ArgumentParser(description="Evaluate zero-shot CLIP upper-clothing color classification.")
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--labels", type=Path, default=DEFAULT_LABEL_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--backend", choices=["auto", "hf", "open_clip", "siglip"], default="auto")
    parser.add_argument("--open-clip-model-name", default=None)
    parser.add_argument("--open-clip-pretrained", default=None)
    parser.add_argument("--temperature", type=float, default=10.0)
    parser.add_argument("--temperature-grid", default="")
    parser.add_argument("--prompt-set", choices=sorted(_prompt_sets()), default=None)
    parser.add_argument(
        "--ensemble-prompt-set",
        choices=sorted(_prompt_ensembles()),
        default="ensemble_mixed",
    )
    parser.add_argument(
        "--crop-mode",
        choices=CROP_MODE_CHOICES,
        default="all",
    )
    parser.add_argument("--enable-schp", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    temperature_grid = _parse_temperature_grid(args.temperature_grid)

    if args.device == "cuda" and not torch.cuda.is_available():
        args.device = "cpu"
    load_started_at = time.perf_counter()
    runner = ClipRunner(
        args.model_dir,
        backend=args.backend,
        device=args.device,
        open_clip_model_name=args.open_clip_model_name,
        open_clip_pretrained=args.open_clip_pretrained,
    )
    model_load_seconds = time.perf_counter() - load_started_at

    db.init_db()
    schp_model = None
    schp_load_seconds = 0.0
    if args.enable_schp:
        from scripts.evaluate_schp_clothes import _load_schp  # noqa: WPS433

        schp_started_at = time.perf_counter()
        schp_model = _load_schp(args.device)
        schp_load_seconds = time.perf_counter() - schp_started_at
    all_items = _load_manual_items(args.labels)
    items = all_items[: args.limit] if args.limit else all_items
    prompt_sets = _prompt_sets()
    selected_sets = {args.prompt_set: prompt_sets[args.prompt_set]} if args.prompt_set else prompt_sets
    ensemble_sets = _prompt_ensembles()

    rois: dict[str, dict[str, np.ndarray]] = {}
    missing: Counter[str] = Counter()
    sample_sources: Counter[str] = Counter()
    crop_started_at = time.perf_counter()
    for item in items:
        sample, source = _sample_image(item)
        if sample is None:
            missing[source] += 1
            continue
        variants = _crop_variants(sample, schp_model=schp_model, device=args.device)
        if args.crop_mode != "all":
            variants = {args.crop_mode: variants[args.crop_mode]} if args.crop_mode in variants else {}
        if not variants:
            missing["roi_missing"] += 1
            continue
        rois[item["sample_key"]] = variants
        sample_sources[source] += 1
    crop_prepare_seconds = time.perf_counter() - crop_started_at

    reports: dict[str, Any] = {}
    for name, prompts in selected_sets.items():
        text_features = _text_features(
            runner=runner,
            prompts=prompts,
        )
        predictions: dict[str, str] = {}
        details = []
        for item in items:
            sample_key = item["sample_key"]
            variants = rois.get(sample_key)
            roi = variants.get("upper_center") if variants else None
            if roi is None:
                predictions[sample_key] = "unknown"
                continue
            color, confidence, probs = _predict(
                runner=runner,
                text_features=text_features,
                roi_bgr=roi,
                temperature=args.temperature,
            )
            predictions[sample_key] = color
            details.append(
                {
                    "sample_key": sample_key,
                    "event_id": item["event_id"],
                    "observation_id": item["observation_id"],
                    "person_id": item["person_id"],
                    "split_group": item["split_group"],
                    "manual_upper_color": item["upper_color"],
                    "predicted_upper_color": color,
                    "confidence": round(confidence, 6),
                    "correct": color == item["upper_color"],
                    "probs": probs,
                }
            )
        reports[name] = _evaluate_predictions(items, predictions) | {
            "details": details,
            "prediction_counts": dict(Counter(predictions.values()).most_common()),
        }

    image_feature_cache: dict[tuple[str, str], torch.Tensor] = {}
    all_strategy_probs: dict[str, dict[str, np.ndarray]] = {}
    all_strategy_scores: dict[str, dict[str, np.ndarray]] = {}
    for ensemble_name, prompt_by_color in ensemble_sets.items():
        if args.prompt_set:
            continue
        text_features = _ensemble_text_features(
            runner=runner,
            prompt_by_color=prompt_by_color,
        )
        strategy_predictions: dict[str, dict[str, str]] = defaultdict(dict)
        strategy_details: dict[str, list[dict[str, Any]]] = defaultdict(list)
        strategy_scores: dict[str, dict[str, np.ndarray]] = defaultdict(dict)
        strategy_probs: dict[str, dict[str, np.ndarray]] = defaultdict(dict)
        crop_names = [*BASE_CROP_NAMES, *SCHP_CROP_NAMES]
        if args.crop_mode != "all":
            crop_names = [args.crop_mode]
        for item in items:
            sample_key = item["sample_key"]
            variants = rois.get(sample_key)
            if not variants:
                for strategy in [f"{ensemble_name}_{crop}" for crop in crop_names] + [
                    f"{ensemble_name}_crop_avg",
                    f"{ensemble_name}_crop_avg_rule_fusion",
                    *[f"rule_{crop}" for crop in crop_names],
                ]:
                    strategy_predictions[strategy][sample_key] = "unknown"
                continue

            crop_scores = {}
            crop_probs = {}
            for crop_name in crop_names:
                roi = variants.get(crop_name)
                if roi is None:
                    continue
                cache_key = (sample_key, crop_name)
                image_feature = image_feature_cache.get(cache_key)
                if image_feature is None:
                    image_feature = _image_feature(
                        runner=runner,
                        roi_bgr=roi,
                    )
                    image_feature_cache[cache_key] = image_feature
                scores = runner.similarity_scores(image_feature, text_features).detach().cpu().numpy()
                probs_array = _probs_from_scores(scores, temperature=args.temperature)
                color, confidence, probs = _predict_from_probs(probs_array)
                crop_scores[crop_name] = scores
                crop_probs[crop_name] = probs_array
                strategy = f"{ensemble_name}_{crop_name}"
                strategy_predictions[strategy][sample_key] = color
                strategy_scores[strategy][sample_key] = scores
                strategy_probs[strategy][sample_key] = probs_array
                strategy_details[strategy].append(
                    {
                        "sample_key": sample_key,
                        "event_id": item["event_id"],
                        "observation_id": item["observation_id"],
                        "person_id": item["person_id"],
                        "split_group": item["split_group"],
                        "manual_upper_color": item["upper_color"],
                        "predicted_upper_color": color,
                        "confidence": round(confidence, 6),
                        "correct": color == item["upper_color"],
                        "crop_mode": crop_name,
                        "probs": probs,
                    }
                )
                if crop_name in {"schp_upper_masked", "schp_upper_tight_masked"}:
                    masked_color, masked_confidence, masked_diagnostics = _masked_rule_color(roi)
                    masked_strategy = f"masked_rule_{crop_name}"
                    strategy_predictions[masked_strategy][sample_key] = masked_color
                    strategy_details[masked_strategy].append(
                        {
                            "sample_key": sample_key,
                            "event_id": item["event_id"],
                            "observation_id": item["observation_id"],
                            "person_id": item["person_id"],
                            "split_group": item["split_group"],
                            "manual_upper_color": item["upper_color"],
                            "predicted_upper_color": masked_color,
                            "confidence": round(masked_confidence, 6),
                            "correct": masked_color == item["upper_color"],
                            "crop_mode": crop_name,
                            "diagnostics": masked_diagnostics,
                        }
                    )
                    guarded, guarded_confidence, guarded_reason = _guarded_color(
                        clip_color=color,
                        clip_confidence=confidence,
                        rule_color=masked_color,
                        rule_confidence=masked_confidence,
                    )
                    guarded_strategy = f"{ensemble_name}_{crop_name}_masked_guard"
                    strategy_predictions[guarded_strategy][sample_key] = guarded
                    strategy_details[guarded_strategy].append(
                        {
                            "sample_key": sample_key,
                            "event_id": item["event_id"],
                            "observation_id": item["observation_id"],
                            "person_id": item["person_id"],
                            "split_group": item["split_group"],
                            "manual_upper_color": item["upper_color"],
                            "predicted_upper_color": guarded,
                            "confidence": round(guarded_confidence, 6),
                            "correct": guarded == item["upper_color"],
                            "clip_upper_color": color,
                            "clip_confidence": round(confidence, 6),
                            "masked_rule_upper_color": masked_color,
                            "masked_rule_confidence": round(masked_confidence, 6),
                            "guard_reason": guarded_reason,
                            "crop_mode": crop_name,
                            "probs": probs,
                            "diagnostics": masked_diagnostics,
                        }
                    )
                rule_color, rule_confidence = _rule_color(roi)
                rule_strategy = f"rule_{crop_name}"
                strategy_predictions[rule_strategy][sample_key] = rule_color
                strategy_details[rule_strategy].append(
                    {
                        "sample_key": sample_key,
                        "event_id": item["event_id"],
                        "observation_id": item["observation_id"],
                        "person_id": item["person_id"],
                        "split_group": item["split_group"],
                        "manual_upper_color": item["upper_color"],
                        "predicted_upper_color": rule_color,
                        "confidence": round(rule_confidence, 6),
                        "correct": rule_color == item["upper_color"],
                        "crop_mode": crop_name,
                    }
                )
            if crop_scores:
                weights = {
                    "upper_center": 1.15,
                    "upper_wide": 1.05,
                    "torso": 1.0,
                    "body_no_head": 0.85,
                    "full_body": 0.55,
                    "schp_upper_masked": 1.35,
                    "schp_upper_tight_masked": 1.45,
                    "schp_upper_tight_filled": 1.35,
                    "schp_upper_tight_raw": 1.10,
                }
                score_sum = np.zeros(len(COLORS), dtype=np.float32)
                weight_sum = 0.0
                for crop_name, scores in crop_scores.items():
                    weight = weights.get(crop_name, 1.0)
                    score_sum += scores * weight
                    weight_sum += weight
                avg_scores = score_sum / max(1e-6, weight_sum)
                probs_array = _probs_from_scores(avg_scores, temperature=args.temperature)
                color, confidence, probs = _predict_from_probs(probs_array)
            else:
                probs_array = None
                color, confidence, probs = "unknown", 0.0, {}

            avg_strategy = f"{ensemble_name}_crop_avg"
            strategy_predictions[avg_strategy][sample_key] = color
            if crop_scores:
                strategy_scores[avg_strategy][sample_key] = avg_scores
                strategy_probs[avg_strategy][sample_key] = probs_array
            rule_roi = (
                variants.get("schp_upper_tight_raw")
                if "schp_upper_tight_raw" in variants
                else variants.get("torso")
            )
            if rule_roi is None:
                rule_roi = variants.get("upper_center")
            if rule_roi is None:
                rule_roi = next(iter(variants.values()))
            rule_color, rule_confidence = _rule_color(rule_roi)
            fused, fused_confidence, reason = _fused_color(
                clip_color=color,
                clip_confidence=confidence,
                rule_color=rule_color,
                rule_confidence=rule_confidence,
            )
            fused_strategy = f"{ensemble_name}_crop_avg_rule_fusion"
            strategy_predictions[fused_strategy][sample_key] = fused
            common_detail = {
                "sample_key": sample_key,
                "event_id": item["event_id"],
                "observation_id": item["observation_id"],
                "person_id": item["person_id"],
                "split_group": item["split_group"],
                "manual_upper_color": item["upper_color"],
            }
            strategy_details[avg_strategy].append(
                common_detail
                | {
                    "predicted_upper_color": color,
                    "confidence": round(confidence, 6),
                    "correct": color == item["upper_color"],
                    "crop_mode": "weighted_average",
                    "probs": probs,
                }
            )
            strategy_details[fused_strategy].append(
                common_detail
                | {
                    "predicted_upper_color": fused,
                    "confidence": round(fused_confidence, 6),
                    "correct": fused == item["upper_color"],
                    "clip_upper_color": color,
                    "clip_confidence": round(confidence, 6),
                    "rule_upper_color": rule_color,
                    "rule_confidence": round(rule_confidence, 6),
                    "fusion_reason": reason,
                    "probs": probs,
                }
            )

        for strategy, predictions in strategy_predictions.items():
            reports[strategy] = _with_score_group_metrics(
                _evaluate_predictions(items, predictions)
                | {
                    "details": strategy_details.get(strategy, []),
                    "prediction_counts": dict(Counter(predictions.values()).most_common()),
                },
                items,
                strategy_scores.get(strategy),
                temperature=args.temperature,
            )
        all_strategy_probs.update({strategy: dict(probs) for strategy, probs in strategy_probs.items()})
        all_strategy_scores.update({strategy: dict(scores) for strategy, scores in strategy_scores.items()})

    combo_specs = {
        "profile_realtime_schp_tight_v1": [
            ("ensemble_mixed_schp_upper_tight_masked", 0.55),
            ("ensemble_garment_schp_upper_tight_masked", 0.45),
        ],
        "profile_realtime_schp_tight_plus_torso_v1": [
            ("ensemble_mixed_schp_upper_tight_masked", 0.42),
            ("ensemble_garment_schp_upper_tight_masked", 0.34),
            ("ensemble_mixed_torso", 0.24),
        ],
        "profile_realtime_balanced_prompt_v2": [
            ("ensemble_garment_schp_upper_tight_masked", 0.50),
            ("ensemble_surveillance_torso", 0.50),
        ],
        "profile_realtime_balanced_prompt_4way_v2": [
            ("ensemble_garment_schp_upper_tight_masked", 0.25),
            ("ensemble_mixed_body_no_head", 0.25),
            ("ensemble_surveillance_crop_avg", 0.25),
            ("ensemble_surveillance_torso", 0.25),
        ],
        "profile_offline_allcrop_prompt_mix_v1": [
            ("ensemble_mixed_crop_avg", 0.48),
            ("ensemble_garment_crop_avg", 0.30),
            ("ensemble_surveillance_crop_avg", 0.22),
        ],
        "profile_offline_prior_best_combo_v1": [
            ("ensemble_surveillance_crop_avg", 0.50),
            ("ensemble_mixed_torso", 0.50),
        ],
    }
    for strategy, spec in combo_specs.items():
        if not all(name in all_strategy_probs for name, _ in spec):
            continue
        combined_probs = _combine_prob_strategies(all_strategy_probs, spec)
        reports[strategy] = _evaluate_prob_predictions(items, combined_probs) | {
            "profile_spec": [{"strategy": name, "weight": weight} for name, weight in spec],
        }
        for temp in temperature_grid:
            if temp == args.temperature:
                continue
            if not all(name in all_strategy_scores for name, _ in spec):
                continue
            temp_probs = _combine_score_strategies_as_probs(
                all_strategy_scores,
                spec,
                temperature=temp,
            )
            temp_key = f"{strategy}_temp_{str(temp).replace('.', '_')}"
            reports[temp_key] = _evaluate_prob_predictions(items, temp_probs) | {
                "profile_spec": [{"strategy": name, "weight": weight} for name, weight in spec],
                "profile_temperature": temp,
            }

    total_seconds = time.perf_counter() - total_started_at
    image_avg_ms = (
        runner.image_feature_seconds / max(1, runner.image_feature_calls) * 1000.0
        if runner.image_feature_calls
        else None
    )
    text_avg_ms = (
        runner.text_feature_seconds / max(1, runner.text_feature_calls) * 1000.0
        if runner.text_feature_calls
        else None
    )
    output = {
        "model_dir": str(args.model_dir),
        "backend": runner.backend,
        "open_clip_model_name": args.open_clip_model_name,
        "open_clip_pretrained": args.open_clip_pretrained,
        "device": args.device,
        "temperature": args.temperature,
        "temperature_grid": temperature_grid,
        "manual_event_count": len(items),
        "roi_count": len(rois),
        "missing_roi_counts": dict(missing.most_common()),
        "sample_source_counts": dict(sample_sources.most_common()),
        "schp_enabled": bool(args.enable_schp),
        "runtime": {
            "total_seconds": round(total_seconds, 4),
            "model_load_seconds": round(model_load_seconds, 4),
            "schp_load_seconds": round(schp_load_seconds, 4),
            "crop_prepare_seconds": round(crop_prepare_seconds, 4),
            "image_feature_calls": runner.image_feature_calls,
            "image_feature_seconds": round(runner.image_feature_seconds, 4),
            "image_feature_avg_ms": round(image_avg_ms, 4) if image_avg_ms is not None else None,
            "text_feature_calls": runner.text_feature_calls,
            "text_feature_seconds": round(runner.text_feature_seconds, 4),
            "text_feature_avg_ms": round(text_avg_ms, 4) if text_avg_ms is not None else None,
            "cached_image_features": len(image_feature_cache),
        },
        "colors": COLORS,
        "reports": reports,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {
        name: {
            "event_accuracy": report["event_metrics"]["accuracy"],
            "group_accuracy": report["group_metrics"]["accuracy"],
            "score_group_accuracy": (
                report.get("score_group_metrics", {}).get("accuracy")
                if report.get("score_group_metrics")
                else None
            ),
            "prob_group_accuracy": (
                report.get("prob_group_metrics", {}).get("accuracy")
                if report.get("prob_group_metrics")
                else None
            ),
            "event_correct": report["event_metrics"]["correct"],
            "event_total": report["event_metrics"]["total"],
            "group_correct": report["group_metrics"]["correct"],
            "group_total": report["group_metrics"]["total"],
        }
        for name, report in reports.items()
    }
    print(json.dumps({"summary": summary, "output": str(args.output)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
