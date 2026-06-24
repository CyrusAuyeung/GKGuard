from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from app.core.config import settings
from app.vision.vector_math import cosine_similarity


MODEL_VERSION = "person_merge_logreg_v1"

FEATURE_NAMES = [
    "centroid_similarity",
    "max_pair_similarity",
    "top3_pair_similarity",
    "top5_pair_similarity",
    "p90_pair_similarity",
    "p75_pair_similarity",
    "mean_pair_similarity",
    "median_pair_similarity",
    "std_pair_similarity",
    "source_mean_intra_similarity",
    "target_mean_intra_similarity",
    "min_mean_intra_similarity",
    "source_face_count_log",
    "target_face_count_log",
    "min_face_count_log",
    "max_face_count_log",
    "face_count_ratio",
    "source_mean_face_area_log",
    "target_mean_face_area_log",
    "min_mean_face_area_log",
    "source_min_detection_score",
    "target_min_detection_score",
    "min_detection_score",
    "camera_intersection_count",
    "camera_jaccard",
    "same_frame_conflict",
    "centroid_nearest_margin",
]


def _normalized_mean(vectors: list[list[float]]) -> list[float]:
    if not vectors:
        return []
    matrix = np.asarray(vectors, dtype="float32")
    mean = matrix.mean(axis=0)
    norm = float(np.linalg.norm(mean))
    if norm < 1e-8:
        return mean.astype(float).tolist()
    return (mean / norm).astype(float).tolist()


def _bbox_area(record: dict[str, Any]) -> float:
    bbox = record.get("bbox") or {}
    return max(1.0, float(bbox.get("x2", 0.0) - bbox.get("x1", 0.0))) * max(
        1.0,
        float(bbox.get("y2", 0.0) - bbox.get("y1", 0.0)),
    )


def _detection_score(record: dict[str, Any]) -> float:
    return float((record.get("bbox") or {}).get("score") or 0.0)


def _frame_key(record: dict[str, Any]) -> tuple[str, float]:
    return (str(record.get("video_id") or ""), round(float(record.get("video_timestamp_sec") or 0.0), 3))


def _same_frame_conflict(left_records: list[dict[str, Any]], right_records: list[dict[str, Any]]) -> bool:
    left_keys = {_frame_key(record) for record in left_records}
    return any(_frame_key(record) in left_keys for record in right_records)


def _mean_intra_similarity(records: list[dict[str, Any]]) -> float:
    if len(records) <= 1:
        return 1.0
    scores = [
        cosine_similarity(left["embedding"], right["embedding"])
        for index, left in enumerate(records)
        for right in records[index + 1 :]
    ]
    return float(np.mean(scores)) if scores else 0.0


def _pair_scores(left_records: list[dict[str, Any]], right_records: list[dict[str, Any]]) -> np.ndarray:
    scores = [
        cosine_similarity(left["embedding"], right["embedding"])
        for left in left_records
        for right in right_records
    ]
    return np.asarray(scores, dtype="float32")


def build_pair_features(
    source_records: list[dict[str, Any]],
    target_records: list[dict[str, Any]],
    *,
    other_person_embeddings: list[list[float]] | None = None,
) -> dict[str, float]:
    source_embedding = _normalized_mean([record["embedding"] for record in source_records])
    target_embedding = _normalized_mean([record["embedding"] for record in target_records])
    pair_scores = _pair_scores(source_records, target_records)
    pair_scores.sort()
    descending = pair_scores[::-1]

    source_cameras = {str(record.get("camera_id") or "") for record in source_records}
    target_cameras = {str(record.get("camera_id") or "") for record in target_records}
    camera_union = source_cameras | target_cameras
    source_areas = np.asarray([_bbox_area(record) for record in source_records], dtype="float32")
    target_areas = np.asarray([_bbox_area(record) for record in target_records], dtype="float32")
    source_scores = np.asarray([_detection_score(record) for record in source_records], dtype="float32")
    target_scores = np.asarray([_detection_score(record) for record in target_records], dtype="float32")

    centroid = cosine_similarity(source_embedding, target_embedding)
    second_best = -1.0
    for embedding in other_person_embeddings or []:
        second_best = max(second_best, cosine_similarity(source_embedding, embedding))

    source_count = len(source_records)
    target_count = len(target_records)
    min_count = min(source_count, target_count)
    max_count = max(source_count, target_count)
    source_mean_intra = _mean_intra_similarity(source_records)
    target_mean_intra = _mean_intra_similarity(target_records)
    source_mean_area = float(np.mean(source_areas)) if source_areas.size else 0.0
    target_mean_area = float(np.mean(target_areas)) if target_areas.size else 0.0

    return {
        "centroid_similarity": float(centroid),
        "max_pair_similarity": float(descending[0]) if descending.size else 0.0,
        "top3_pair_similarity": float(np.mean(descending[: min(3, descending.size)])) if descending.size else 0.0,
        "top5_pair_similarity": float(np.mean(descending[: min(5, descending.size)])) if descending.size else 0.0,
        "p90_pair_similarity": float(np.percentile(pair_scores, 90)) if pair_scores.size else 0.0,
        "p75_pair_similarity": float(np.percentile(pair_scores, 75)) if pair_scores.size else 0.0,
        "mean_pair_similarity": float(np.mean(pair_scores)) if pair_scores.size else 0.0,
        "median_pair_similarity": float(np.median(pair_scores)) if pair_scores.size else 0.0,
        "std_pair_similarity": float(np.std(pair_scores)) if pair_scores.size else 0.0,
        "source_mean_intra_similarity": source_mean_intra,
        "target_mean_intra_similarity": target_mean_intra,
        "min_mean_intra_similarity": min(source_mean_intra, target_mean_intra),
        "source_face_count_log": math.log1p(source_count),
        "target_face_count_log": math.log1p(target_count),
        "min_face_count_log": math.log1p(min_count),
        "max_face_count_log": math.log1p(max_count),
        "face_count_ratio": min_count / max(1, max_count),
        "source_mean_face_area_log": math.log1p(source_mean_area),
        "target_mean_face_area_log": math.log1p(target_mean_area),
        "min_mean_face_area_log": math.log1p(min(source_mean_area, target_mean_area)),
        "source_min_detection_score": float(np.min(source_scores)) if source_scores.size else 0.0,
        "target_min_detection_score": float(np.min(target_scores)) if target_scores.size else 0.0,
        "min_detection_score": min(float(np.min(source_scores)), float(np.min(target_scores)))
        if source_scores.size and target_scores.size
        else 0.0,
        "camera_intersection_count": float(len(source_cameras & target_cameras)),
        "camera_jaccard": len(source_cameras & target_cameras) / max(1, len(camera_union)),
        "same_frame_conflict": 1.0 if _same_frame_conflict(source_records, target_records) else 0.0,
        "centroid_nearest_margin": centroid - second_best if second_best >= 0.0 else 1.0,
    }


@lru_cache(maxsize=4)
def load_model(path: str | Path | None = None) -> dict[str, Any]:
    model_path = Path(path) if path is not None else settings.person_merge_scorer_model_path
    data = json.loads(model_path.read_text(encoding="utf-8"))
    if data.get("model_version") != MODEL_VERSION:
        raise ValueError(f"unsupported person merge scorer model: {data.get('model_version')}")
    if data.get("feature_names") != FEATURE_NAMES:
        raise ValueError("person merge scorer feature names do not match runtime features")
    return data


def predict_probability(model: dict[str, Any], features: dict[str, float]) -> float:
    row = np.asarray([float(features[name]) for name in FEATURE_NAMES], dtype="float32")
    mean = np.asarray(model["scaler_mean"], dtype="float32")
    scale = np.asarray(model["scaler_scale"], dtype="float32")
    coef = np.asarray(model["coef"], dtype="float32")
    intercept = float(model["intercept"])
    normalized = (row - mean) / np.where(scale <= 1e-8, 1.0, scale)
    logit = float(normalized @ coef + intercept)
    logit = max(-60.0, min(60.0, logit))
    return float(1.0 / (1.0 + math.exp(-logit)))
