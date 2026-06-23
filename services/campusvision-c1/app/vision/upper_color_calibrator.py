from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from app.core.config import settings


MODEL_VERSION = "upper_color_knn_calibrator_v1"
_MANUAL_EVAL_SOURCES = {
    "manual_eval_labels",
    "manual_upper_color_eval_labels",
    "manual_outfit_labels",
    "manual_outfit_review",
    "manual_person_outfit_grouping",
}


def _is_deployable_model(data: dict[str, Any]) -> bool:
    if data.get("eval_only") is True:
        return False
    source = str(data.get("training_source") or data.get("source") or "")
    if source in _MANUAL_EVAL_SOURCES or source.startswith("manual_"):
        return False
    return data.get("deployment_allowed") is True


def _hist(values: np.ndarray, bins: int, value_range: tuple[int, int]) -> np.ndarray:
    hist, _ = np.histogram(values.reshape(-1), bins=bins, range=value_range)
    hist = hist.astype(np.float32)
    return hist / max(1e-6, float(hist.sum()))


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
    profiles = (
        lab[:, :, 0].mean(axis=0),
        lab[:, :, 0].mean(axis=1),
        lab[:, :, 1].mean(axis=0),
        lab[:, :, 1].mean(axis=1),
        lab[:, :, 2].mean(axis=0),
        lab[:, :, 2].mean(axis=1),
    )
    return max(_stripe_profile_score(profile) for profile in profiles)


def extract_features(roi_bgr: np.ndarray) -> np.ndarray:
    roi = cv2.resize(roi_bgr, (48, 64), interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV).astype(np.float32)
    lab = cv2.cvtColor(roi, cv2.COLOR_BGR2LAB).astype(np.float32)
    bgr = roi.astype(np.float32)

    spread = bgr.max(axis=2) - bgr.min(axis=2)
    chroma = np.sqrt((lab[:, :, 1] - 128.0) ** 2 + (lab[:, :, 2] - 128.0) ** 2)
    h = hsv[:, :, 0]
    s = hsv[:, :, 1]
    v = hsv[:, :, 2]

    stats: list[float] = []
    for values in (
        bgr[:, :, 0],
        bgr[:, :, 1],
        bgr[:, :, 2],
        h,
        s,
        v,
        lab[:, :, 0],
        lab[:, :, 1],
        lab[:, :, 2],
        spread,
        chroma,
    ):
        stats.extend(
            [
                float(np.mean(values)),
                float(np.std(values)),
                float(np.median(values)),
                float(np.percentile(values, 10)),
                float(np.percentile(values, 90)),
            ]
        )

    stats.extend(
        [
            _striped_score(roi),
            float(np.mean(v < 70)),
            float(np.mean(v < 95)),
            float(np.mean(v > 170)),
            float(np.mean(v > 188)),
            float(np.mean(s < 45)),
            float(np.mean(s < 70)),
            float(np.mean(chroma < 25)),
            float(np.mean(spread < 35)),
        ]
    )

    return np.concatenate(
        [
            np.asarray(stats, dtype=np.float32),
            _hist(h, 18, (0, 180)),
            _hist(s, 10, (0, 256)),
            _hist(v, 10, (0, 256)),
            _hist(lab[:, :, 0], 10, (0, 256)),
            _hist(lab[:, :, 1], 10, (0, 256)),
            _hist(lab[:, :, 2], 10, (0, 256)),
        ]
    ).astype(np.float32)


def normalize_features(features: np.ndarray, model: dict[str, Any]) -> np.ndarray:
    mean = np.asarray(model["feature_mean"], dtype=np.float32)
    scale = np.asarray(model["feature_scale"], dtype=np.float32)
    scale = np.where(scale <= 1e-6, 1.0, scale)
    return (features.astype(np.float32) - mean) / scale


def load_model(path: Path | str | None = None) -> dict[str, Any] | None:
    model_path = Path(path) if path is not None else settings.upper_color_calibrator_path
    if not model_path.exists():
        return None
    data = json.loads(model_path.read_text(encoding="utf-8"))
    if data.get("model_version") != MODEL_VERSION:
        return None
    if not _is_deployable_model(data):
        return None
    vectors = np.asarray(data.get("feature_vectors") or [], dtype=np.float32)
    labels = list(data.get("labels") or [])
    if vectors.ndim != 2 or not labels or vectors.shape[0] != len(labels):
        return None
    data["_feature_vectors_np"] = vectors
    data["_labels_np"] = np.asarray(labels)
    return data


@lru_cache(maxsize=2)
def _cached_model(path: str) -> dict[str, Any] | None:
    return load_model(Path(path))


def get_default_model() -> dict[str, Any] | None:
    return _cached_model(str(settings.upper_color_calibrator_path))


def clear_model_cache() -> None:
    _cached_model.cache_clear()


def predict(
    roi_bgr: np.ndarray,
    *,
    model: dict[str, Any] | None = None,
    k: int | None = None,
) -> dict[str, Any] | None:
    model = model if model is not None else get_default_model()
    if model is None:
        return None
    vectors = model["_feature_vectors_np"]
    labels = model["_labels_np"]
    if vectors.size == 0:
        return None

    query = normalize_features(extract_features(roi_bgr), model)
    distances = np.linalg.norm(vectors - query, axis=1)
    neighbor_count = max(1, min(int(k or model.get("k") or settings.upper_color_calibrator_k), len(labels)))
    order = np.argsort(distances)[:neighbor_count]

    votes: dict[str, float] = {}
    nearest_distance = float(distances[order[0]])
    for index in order:
        label = str(labels[index])
        votes[label] = votes.get(label, 0.0) + 1.0 / (float(distances[index]) + 1e-6)

    ranked = sorted(votes.items(), key=lambda item: item[1], reverse=True)
    color, score = ranked[0]
    total = sum(votes.values())
    confidence = float(score / max(1e-6, total))
    if nearest_distance <= 1e-5:
        confidence = 1.0

    return {
        "color": color,
        "confidence": round(confidence, 4),
        "nearest_distance": round(nearest_distance, 6),
        "neighbors": [
            {
                "color": str(labels[index]),
                "distance": round(float(distances[index]), 6),
            }
            for index in order
        ],
        "model_version": model.get("model_version") or MODEL_VERSION,
    }
