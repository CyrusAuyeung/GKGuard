from __future__ import annotations

from dataclasses import dataclass
from math import hypot

import cv2
import numpy as np

from app.core.config import settings


@dataclass(frozen=True)
class RegionResult:
    color: str | None
    confidence: float | None
    visible: bool
    valid_pixel_ratio: float | None
    probabilities: dict[str, float] | None = None

    def as_prefix(self, prefix: str) -> dict:
        return {
            f"{prefix}_color": self.color,
            f"{prefix}_color_confidence": self.confidence,
            f"{prefix}_visible": self.visible,
            f"{prefix}_valid_pixel_ratio": self.valid_pixel_ratio,
            f"{prefix}_color_probs": self.probabilities,
        }


def bbox_area(box: dict | None) -> float:
    if not box:
        return 0.0
    return max(0.0, float(box.get("x2", 0) - box.get("x1", 0))) * max(
        0.0, float(box.get("y2", 0) - box.get("y1", 0))
    )


def clamp_bbox(box: dict, width: int, height: int) -> dict:
    x1 = max(0, min(width - 1, int(round(float(box["x1"])))))
    y1 = max(0, min(height - 1, int(round(float(box["y1"])))))
    x2 = max(x1 + 1, min(width, int(round(float(box["x2"])))))
    y2 = max(y1 + 1, min(height, int(round(float(box["y2"])))))
    out = dict(box)
    out.update({"x1": x1, "y1": y1, "x2": x2, "y2": y2, "width": x2 - x1, "height": y2 - y1})
    return out


def estimate_body_bbox_from_face(face_box: dict, image_width: int, image_height: int) -> dict:
    face_w = max(1.0, float(face_box.get("x2", 0) - face_box.get("x1", 0)))
    face_h = max(1.0, float(face_box.get("y2", 0) - face_box.get("y1", 0)))
    face_cx = (float(face_box["x1"]) + float(face_box["x2"])) / 2.0

    body_w = max(settings.min_person_box_width, face_w * 3.0)
    body_h = max(settings.min_person_box_height, face_h * 6.8)
    raw_x1 = face_cx - body_w / 2.0
    raw_y1 = float(face_box["y1"]) - face_h * 0.35
    raw_x2 = raw_x1 + body_w
    raw_y2 = raw_y1 + body_h

    box = clamp_bbox(
        {
            "x1": raw_x1,
            "y1": raw_y1,
            "x2": raw_x2,
            "y2": raw_y2,
            "score": min(0.34, float(face_box.get("score") or 0.0) * 0.35),
            "class_id": 0,
            "class_name": "person",
            "detector": "face_estimated_body",
            "estimated_from_face": True,
            "estimated_bottom_clipped": raw_y2 >= image_height - 1,
        },
        image_width,
        image_height,
    )
    return box


def _edge_truncation(box: dict, width: int, height: int) -> float:
    touches = 0
    touches += 1 if float(box["x1"]) <= 1 else 0
    touches += 1 if float(box["y1"]) <= 1 else 0
    touches += 1 if float(box["x2"]) >= width - 1 else 0
    touches += 1 if float(box["y2"]) >= height - 1 else 0
    return touches / 4.0


def _is_bottom_truncated(box: dict, height: int) -> bool:
    return float(box["y2"]) >= height - 2


def _roi_from_ratio(image_bgr: np.ndarray, body_box: dict, start_ratio: float, end_ratio: float) -> np.ndarray | None:
    height, width = image_bgr.shape[:2]
    box = clamp_bbox(body_box, width, height)
    y1 = int(round(box["y1"] + box["height"] * start_ratio))
    y2 = int(round(box["y1"] + box["height"] * end_ratio))
    x1 = int(box["x1"])
    x2 = int(box["x2"])
    y1 = max(0, min(height - 1, y1))
    y2 = max(y1 + 1, min(height, y2))
    if (x2 - x1) * (y2 - y1) < settings.min_clothing_roi_area:
        return None
    return image_bgr[y1:y2, x1:x2]


def _center_roi(roi_bgr: np.ndarray) -> np.ndarray:
    keep = max(0.2, min(1.0, float(settings.clothing_roi_center_width_ratio)))
    if keep >= 0.999:
        return roi_bgr

    width = roi_bgr.shape[1]
    center = width / 2.0
    half = width * keep / 2.0
    x1 = max(0, int(round(center - half)))
    x2 = min(width, int(round(center + half)))
    if x2 <= x1:
        return roi_bgr
    return roi_bgr[:, x1:x2]


def classify_body_visibility(image_bgr: np.ndarray, body_box: dict | None, face_box: dict | None = None) -> str:
    if body_box is None:
        return "face_only" if face_box is not None else "unknown_body"

    height, width = image_bgr.shape[:2]
    box = clamp_bbox(body_box, width, height)
    if box["width"] < settings.min_person_box_width or box["height"] < settings.min_person_box_height:
        return "unknown_body"

    truncation = _edge_truncation(box, width, height)
    upper_roi = _roi_from_ratio(image_bgr, box, settings.upper_roi_start_ratio, settings.upper_roi_end_ratio)
    lower_roi = _roi_from_ratio(image_bgr, box, settings.lower_roi_start_ratio, settings.lower_roi_end_ratio)

    if upper_roi is None:
        return "partial_body"

    if body_box.get("estimated_from_face"):
        return "upper_body"

    if face_box:
        face_h = max(1.0, float(face_box.get("y2", 0) - face_box.get("y1", 0)))
        body_to_face_ratio = float(box["height"]) / face_h
        if body_to_face_ratio < 3.2:
            return "upper_body"

    if _is_bottom_truncated(box, height):
        return "upper_body"

    if float(body_box.get("score") or 0.0) < settings.lower_body_min_detection_confidence:
        return "upper_body"

    if lower_roi is not None and truncation <= settings.max_bbox_edge_truncation_ratio:
        return "full_body"
    return "upper_body"


def _color_from_hue(hue: float, value: float) -> str:
    if value < 135 and (8 <= hue <= 24 or 25 <= hue <= 34):
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
    return "other"


def _smooth_profile(profile: np.ndarray) -> np.ndarray:
    values = profile.astype(np.float32).reshape(-1)
    if values.size < 5:
        return values
    window = max(3, min(9, values.size // 10))
    if window % 2 == 0:
        window += 1
    kernel = np.ones(window, dtype=np.float32) / float(window)
    return np.convolve(values, kernel, mode="same")


def _stripe_profile_score(profile: np.ndarray) -> float:
    values = _smooth_profile(profile)
    if values.size < 18:
        return 0.0

    p10, p90 = np.percentile(values, [10, 90])
    amplitude = float(p90 - p10)
    if amplitude < 18.0:
        return 0.0

    midpoint = float(np.median(values))
    signs = values > midpoint
    transition_count = int(np.count_nonzero(signs[1:] != signs[:-1]))
    if transition_count < 4:
        return 0.0

    change_indexes = np.where(signs[1:] != signs[:-1])[0] + 1
    run_edges = np.concatenate(([0], change_indexes, [values.size]))
    run_lengths = np.diff(run_edges)
    max_run_ratio = float(run_lengths.max() / max(1, values.size))
    median_run = float(np.median(run_lengths))
    transition_density = float(transition_count / max(1, values.size - 1))

    # One large split is not a stripe pattern; one-pixel flicker is usually noise.
    if max_run_ratio > 0.55 or median_run < 2.0 or transition_density > 0.55:
        return 0.0

    amplitude_score = min(1.0, amplitude / 80.0)
    transition_score = min(1.0, transition_count / 8.0)
    run_balance_score = max(0.0, 1.0 - max(0.0, max_run_ratio - 0.35) / 0.20)
    return float(amplitude_score * transition_score * run_balance_score)


def _striped_score(roi_bgr: np.ndarray) -> float:
    if roi_bgr.shape[0] < 18 or roi_bgr.shape[1] < 18:
        return 0.0

    lab = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    lab_l = lab[:, :, 0]
    lab_a = lab[:, :, 1]
    lab_b = lab[:, :, 2]
    profiles = (
        lab_l.mean(axis=0),
        lab_l.mean(axis=1),
        lab_a.mean(axis=0),
        lab_a.mean(axis=1),
        lab_b.mean(axis=0),
        lab_b.mean(axis=1),
    )
    return max(_stripe_profile_score(profile) for profile in profiles)


def classify_clothing_color(roi_bgr: np.ndarray | None, *, part: str | None = None) -> RegionResult:
    if roi_bgr is None or roi_bgr.size == 0:
        return RegionResult("unknown", None, False, None)

    roi_bgr = _center_roi(roi_bgr)

    area = int(roi_bgr.shape[0] * roi_bgr.shape[1])
    if area < settings.min_clothing_roi_area:
        return RegionResult("unknown", None, False, 0.0)

    if part == "upper" and settings.enable_upper_color_calibrator:
        try:
            from app.vision import upper_color_calibrator

            calibrated = upper_color_calibrator.predict(roi_bgr)
        except Exception:
            calibrated = None
        if calibrated and calibrated.get("color") in settings.clothing_color_labels:
            confidence = float(calibrated.get("confidence") or 0.0)
            if confidence >= settings.upper_color_calibrator_min_confidence:
                return RegionResult(
                    str(calibrated["color"]),
                    round(confidence, 4),
                    str(calibrated["color"]) != "unknown",
                    1.0,
                )

    hsv = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2HSV)
    h = hsv[:, :, 0].astype(np.float32)
    s = hsv[:, :, 1].astype(np.float32)
    v = hsv[:, :, 2].astype(np.float32)
    bgr = roi_bgr.astype(np.float32)
    channel_spread = bgr.max(axis=2) - bgr.min(axis=2)

    valid = np.ones(v.shape, dtype=bool)
    valid_ratio = float(valid.sum() / max(1, valid.size))
    if valid_ratio < settings.min_valid_pixel_ratio:
        return RegionResult("unknown", 0.0, False, round(valid_ratio, 4))

    valid_h = h[valid]
    valid_s = s[valid]
    valid_v = v[valid]
    valid_spread = channel_spread[valid]
    lab = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2LAB)
    lab_a = lab[:, :, 1].astype(np.float32)
    lab_b = lab[:, :, 2].astype(np.float32)
    lab_l = lab[:, :, 0].astype(np.float32)
    lab_chroma = np.sqrt((lab_a - 128.0) ** 2 + (lab_b - 128.0) ** 2)
    valid_l = lab_l[valid]
    valid_chroma = lab_chroma[valid]
    median_s = float(np.median(valid_s))
    median_v = float(np.median(valid_v))
    median_l = float(np.median(valid_l))
    median_chroma = float(np.median(valid_chroma))
    median_spread = float(np.median(valid_spread))
    low_chroma_ratio = float((valid_chroma <= 25).sum() / max(1, valid_chroma.size))
    bright_170_ratio = float((valid_v >= 170).sum() / max(1, valid_v.size))
    bright_188_ratio = float((valid_v >= 188).sum() / max(1, valid_v.size))
    dark_90_ratio = float((valid_v < 90).sum() / max(1, valid_v.size))

    striped_score = _striped_score(roi_bgr)
    if striped_score >= 0.27:
        return RegionResult(
            "striped",
            round(min(0.98, striped_score * valid_ratio), 4),
            True,
            round(valid_ratio, 4),
        )

    dark_mask = valid_v < 70
    if median_v < 70 and float(dark_mask.sum() / max(1, valid_v.size)) >= 0.45:
        dark_ratio = float(dark_mask.sum() / max(1, valid_v.size))
        return RegionResult("black", round(min(1.0, dark_ratio * valid_ratio), 4), True, round(valid_ratio, 4))

    if part == "upper":
        blue_cast_white = (
            bright_170_ratio >= 0.45
            and median_l >= 135
            and (low_chroma_ratio >= 0.45 or median_s <= 90)
        ) or (
            bright_188_ratio >= 0.35
            and median_l >= 148
            and median_s <= 110
            and low_chroma_ratio >= 0.32
        )
        if blue_cast_white:
            confidence = min(0.95, max(bright_170_ratio, bright_188_ratio, low_chroma_ratio))
            return RegionResult("white", round(confidence * valid_ratio, 4), True, round(valid_ratio, 4))

    white_mask = (valid_v >= 188) & ((valid_s <= 72) | (valid_spread <= 42))
    white_ratio = float(white_mask.sum() / max(1, valid_v.size))
    if median_v >= 185 and white_ratio >= 0.45:
        return RegionResult("white", round(min(1.0, white_ratio * valid_ratio), 4), True, round(valid_ratio, 4))

    gray_mask = (valid_v >= 70) & (valid_v < 188) & ((valid_s <= 55) | (valid_spread <= 34))
    gray_ratio = float(gray_mask.sum() / max(1, valid_v.size))
    if gray_ratio >= 0.55 or (median_s <= 50 and median_spread <= 36):
        return RegionResult("gray", round(min(1.0, max(gray_ratio, 0.55) * valid_ratio), 4), True, round(valid_ratio, 4))

    if median_s < 38 or median_spread < 28:
        if median_v > 205:
            bright_ratio = float((valid_v > 190).sum() / max(1, valid_v.size))
            return RegionResult("white", round(min(1.0, bright_ratio * valid_ratio), 4), True, round(valid_ratio, 4))
        gray_ratio = float((valid_s < 55).sum() / max(1, valid_s.size))
        return RegionResult("gray", round(min(1.0, gray_ratio * valid_ratio), 4), True, round(valid_ratio, 4))

    colorful = valid & (s >= 58) & (v >= 45) & (channel_spread >= 28)
    if colorful.sum() / max(1, valid.size) < 0.18:
        return RegionResult("unknown", 0.2, False, round(valid_ratio, 4))

    colorful_h = h[colorful]
    colorful_v = v[colorful]
    labels = [_color_from_hue(float(hue), float(value)) for hue, value in zip(colorful_h, colorful_v)]
    counts: dict[str, int] = {}
    for label in labels:
        counts[label] = counts.get(label, 0) + 1

    label, count = max(counts.items(), key=lambda item: item[1])
    confidence = (count / max(1, len(labels))) * valid_ratio
    if label not in settings.clothing_color_labels:
        label = "other"
    if confidence < settings.min_clothing_color_confidence:
        return RegionResult("unknown", round(float(confidence), 4), False, round(valid_ratio, 4))
    if part == "upper" and label == "blue":
        if dark_90_ratio >= 0.80 and median_l <= 62 and low_chroma_ratio >= 0.72:
            return RegionResult("black", round(0.62 * valid_ratio, 4), True, round(valid_ratio, 4))
        suspect_blue_cast = (
            low_chroma_ratio >= 0.55
            and median_chroma <= 24
        ) or (
            median_s <= 82
            and median_spread <= 42
        )
        if suspect_blue_cast:
            if bright_170_ratio >= 0.32 and median_l >= 120:
                return RegionResult("white", round(0.57 * valid_ratio, 4), True, round(valid_ratio, 4))
            confidence = min(float(confidence), 0.42)
    return RegionResult(label, round(float(confidence), 4), True, round(valid_ratio, 4))


def _should_extract_lower_clothing(body_box: dict, body_visibility: str) -> bool:
    if body_visibility == "full_body":
        return True
    # Most current C1 surveillance samples use face-estimated body boxes because
    # full-body detection is weak on small hallway figures. The estimate is good
    # enough to sample the trouser region, but keep non-estimated upper bodies
    # protected so true upper-body-only crops do not invent lower clothing.
    return body_visibility == "upper_body" and bool(body_box.get("estimated_from_face"))


def _classify_upper_color_with_backend(image_bgr: np.ndarray, body_box: dict) -> RegionResult | None:
    return _classify_upper_colors_with_backend(image_bgr, [body_box])[0]


def _upper_prediction_to_region_result(prediction: dict[str, object]) -> RegionResult:
    color = prediction.get("color") or "unknown"
    if color not in settings.clothing_color_labels:
        color = "unknown"
    confidence = prediction.get("confidence")
    valid_ratio = prediction.get("valid_pixel_ratio")
    diagnostics = prediction.get("diagnostics") if isinstance(prediction.get("diagnostics"), dict) else {}
    raw_probs = diagnostics.get("probs") if isinstance(diagnostics, dict) else None
    probabilities = None
    if isinstance(raw_probs, dict):
        probabilities = {
            str(label): round(float(probability), 6)
            for label, probability in raw_probs.items()
            if str(label) in settings.clothing_color_labels
        }
    visible = bool(prediction.get("visible")) and color != "unknown"
    return RegionResult(
        str(color),
        round(float(confidence), 4) if confidence is not None else None,
        visible,
        round(float(valid_ratio), 4) if valid_ratio is not None else None,
        probabilities,
    )


def _classify_upper_colors_with_backend(
    image_bgr: np.ndarray,
    body_boxes: list[dict],
) -> list[RegionResult | None]:
    if settings.upper_color_backend != "clip_schp":
        return [None for _ in body_boxes]
    try:
        from app.vision import upper_color_clip

        predictions = upper_color_clip.predict_upper_colors(image_bgr, body_boxes)
    except Exception:
        return [None for _ in body_boxes]

    results: list[RegionResult | None] = []
    for body_box, prediction in zip(body_boxes, predictions):
        if not prediction:
            results.append(None)
            continue
        clip_result = _upper_prediction_to_region_result(prediction)
        results.append(_apply_upper_neutral_guard(image_bgr, body_box, clip_result))
    if len(results) < len(body_boxes):
        results.extend([None for _ in range(len(body_boxes) - len(results))])
    return results


def _upper_prob_colors() -> list[str]:
    return [
        color
        for color in settings.clothing_color_labels
        if color not in {"unknown", "other"}
    ]


def _normalized_upper_probs(probabilities: dict[str, float] | None, fallback_color: str | None) -> dict[str, float]:
    colors = _upper_prob_colors()
    out: dict[str, float] = {}
    if probabilities:
        for color in colors:
            try:
                out[color] = max(0.0, float(probabilities.get(color) or 0.0))
            except (TypeError, ValueError):
                out[color] = 0.0
    total = sum(out.values())
    if total <= 0.0:
        out = {color: 0.0 for color in colors}
        if fallback_color in out:
            out[str(fallback_color)] = 1.0
        else:
            out["gray"] = 1.0
        return out
    return {color: value / total for color, value in out.items()}


def _blend_upper_rule_result(
    clip_result: RegionResult,
    rule_result: RegionResult,
    *,
    rule_weight: float,
) -> RegionResult:
    colors = _upper_prob_colors()
    rule_color = rule_result.color if rule_result.color in colors else None
    if not rule_color:
        return clip_result

    clipped_weight = max(0.0, min(0.90, float(rule_weight)))
    clip_probs = _normalized_upper_probs(clip_result.probabilities, clip_result.color)
    blended = {}
    for color in colors:
        rule_probability = 1.0 if color == rule_color else 0.0
        blended[color] = (1.0 - clipped_weight) * clip_probs.get(color, 0.0) + clipped_weight * rule_probability
    total = sum(blended.values())
    if total > 0.0:
        blended = {color: value / total for color, value in blended.items()}

    color = max(blended.items(), key=lambda item: item[1])[0]
    max_probability = float(blended[color])
    clip_confidence = float(clip_result.confidence or 0.0)
    rule_confidence = float(rule_result.confidence or 0.0)
    confidence = max(
        clip_confidence,
        min(max_probability, rule_confidence * clipped_weight + clip_confidence * (1.0 - clipped_weight)),
    )
    return RegionResult(
        color,
        round(float(confidence), 4),
        color != "unknown",
        clip_result.valid_pixel_ratio if clip_result.valid_pixel_ratio is not None else rule_result.valid_pixel_ratio,
        {color_name: round(float(blended.get(color_name, 0.0)), 6) for color_name in colors},
    )


def _upper_rule_blend_weight(rule_result: RegionResult, clip_result: RegionResult) -> float:
    rule_color = rule_result.color or "unknown"
    rule_confidence = float(rule_result.confidence or 0.0)
    clip_color = clip_result.color or "unknown"
    clip_confidence = float(clip_result.confidence or 0.0)

    if rule_color in {"black", "white", "gray"}:
        if clip_color == "blue" and rule_confidence >= 0.55:
            return 0.68
        if clip_color == "unknown" and rule_confidence >= 0.50:
            return 0.62
        if clip_confidence < 0.18 and rule_confidence >= 0.58:
            return 0.58
    if rule_color == "striped":
        if clip_color in {"blue", "unknown"} and rule_confidence >= 0.32 and clip_confidence < 0.18:
            return 0.58
        if rule_confidence >= 0.50 and clip_confidence < 0.20:
            return 0.62
    return 0.0


def _apply_upper_neutral_guard(image_bgr: np.ndarray, body_box: dict, clip_result: RegionResult) -> RegionResult:
    upper_roi = _roi_from_ratio(
        image_bgr,
        body_box,
        settings.upper_roi_start_ratio,
        settings.upper_roi_end_ratio,
    )
    rule_result = classify_clothing_color(upper_roi, part="upper")
    if not rule_result.visible or rule_result.color not in {"black", "white", "gray", "striped"}:
        return clip_result

    rule_confidence = float(rule_result.confidence or 0.0)
    clip_confidence = float(clip_result.confidence or 0.0)
    clip_color = clip_result.color or "unknown"
    if clip_result.visible and clip_color not in {"blue", "unknown"} and clip_confidence >= 0.35:
        return clip_result

    neutral_color = rule_result.color in {"black", "white", "gray"}
    high_confidence_neutral = neutral_color and rule_confidence >= 0.58
    strong_blue_cast_evidence = clip_color == "blue" and neutral_color and rule_confidence >= 0.55
    low_confidence_clip = clip_confidence < 0.22

    if high_confidence_neutral and (low_confidence_clip or strong_blue_cast_evidence):
        return _blend_upper_rule_result(clip_result, rule_result, rule_weight=0.78)
    if rule_result.color == "striped" and rule_confidence >= 0.50 and clip_confidence < 0.20:
        return _blend_upper_rule_result(clip_result, rule_result, rule_weight=0.74)
    blend_weight = _upper_rule_blend_weight(rule_result, clip_result)
    if blend_weight > 0.0:
        return _blend_upper_rule_result(clip_result, rule_result, rule_weight=blend_weight)
    if not clip_result.visible and rule_confidence >= 0.45:
        return rule_result
    return clip_result


def analyze_clothing(
    image_bgr: np.ndarray,
    body_box: dict | None,
    body_visibility: str,
    *,
    upper_prediction: RegionResult | None = None,
) -> dict:
    if body_box is None or body_visibility in {"face_only", "unknown_body", "partial_body"}:
        return RegionResult("unknown", None, False, None).as_prefix("upper") | RegionResult(
            "unknown", None, False, None
        ).as_prefix("lower")

    upper = RegionResult("unknown", None, False, None)
    lower = RegionResult("unknown", None, False, None)

    if settings.enable_clothing_detection and settings.enable_upper_clothing_detection:
        upper = upper_prediction or _classify_upper_color_with_backend(image_bgr, body_box) or upper
        if upper.color == "unknown" and upper.confidence is None:
            upper_roi = _roi_from_ratio(
                image_bgr,
                body_box,
                settings.upper_roi_start_ratio,
                settings.upper_roi_end_ratio,
            )
            upper = classify_clothing_color(upper_roi, part="upper")

    if (
        settings.enable_clothing_detection
        and settings.enable_lower_clothing_detection
        and _should_extract_lower_clothing(body_box, body_visibility)
    ):
        lower_roi = _roi_from_ratio(
            image_bgr,
            body_box,
            settings.lower_roi_start_ratio,
            settings.lower_roi_end_ratio,
        )
        lower = classify_clothing_color(lower_roi, part="lower")

    return upper.as_prefix("upper") | lower.as_prefix("lower")


def match_faces_to_bodies(faces: list[dict], bodies: list[dict]) -> dict:
    candidates = []
    for face_index, face in enumerate(faces):
        face_cx = (float(face["x1"]) + float(face["x2"])) / 2.0
        face_cy = (float(face["y1"]) + float(face["y2"])) / 2.0
        face_h = max(1.0, float(face["y2"]) - float(face["y1"]))
        for body_index, body in enumerate(bodies):
            body_w = max(1.0, float(body["x2"]) - float(body["x1"]))
            body_h = max(1.0, float(body["y2"]) - float(body["y1"]))
            inside = (
                float(body["x1"]) <= face_cx <= float(body["x2"])
                and float(body["y1"]) <= face_cy <= float(body["y2"])
            )
            if not inside:
                continue
            upper_position = 1.0 - min(1.0, max(0.0, (face_cy - float(body["y1"])) / body_h) / 0.55)
            size_ratio = face_h / body_h
            if size_ratio < 0.04 or size_ratio > 0.45:
                continue
            body_top_cx = (float(body["x1"]) + float(body["x2"])) / 2.0
            body_top_cy = float(body["y1"]) + body_h * 0.25
            normalized_distance = hypot((face_cx - body_top_cx) / body_w, (face_cy - body_top_cy) / body_h)
            if normalized_distance > settings.face_body_max_normalized_distance:
                continue
            distance_score = 1.0 - normalized_distance / max(0.01, settings.face_body_max_normalized_distance)
            score = (
                0.35 * upper_position
                + 0.30 * distance_score
                + 0.20 * min(1.0, float(body.get("score") or 0.0))
                + 0.15 * min(1.0, float(face.get("score") or 0.0))
            )
            if score >= settings.face_body_match_threshold:
                candidates.append((score, face_index, body_index))

    matched_faces: set[int] = set()
    matched_bodies: set[int] = set()
    pairs = []
    for score, face_index, body_index in sorted(candidates, reverse=True):
        if face_index in matched_faces or body_index in matched_bodies:
            continue
        matched_faces.add(face_index)
        matched_bodies.add(body_index)
        pairs.append(
            {
                "face_index": face_index,
                "body_index": body_index,
                "score": round(float(score), 6),
                "reason": "face_center_in_body_upper_region",
            }
        )

    return {
        "pairs": pairs,
        "unmatched_face_indices": [index for index in range(len(faces)) if index not in matched_faces],
        "unmatched_body_indices": [index for index in range(len(bodies)) if index not in matched_bodies],
    }
