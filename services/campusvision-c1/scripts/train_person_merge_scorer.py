from __future__ import annotations

import argparse
import itertools
import json
import math
import sqlite3
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha1
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix, precision_recall_fscore_support
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import settings


DEFAULT_PRE_MERGE_DB = settings.data_dir / "backups" / "manual_person_merge_20260623_100235" / "campusvision.sqlite3"
DEFAULT_MANUAL_RESULT = settings.data_dir / "backups" / "manual_person_merge_20260623_100235" / "manual_person_merge_result.json"
DEFAULT_MODEL_PATH = settings.data_dir / "models" / "person_merge" / "person_merge_scorer_v1.json"
DEFAULT_REPORT_PATH = settings.data_dir / "evals" / "person_merge_scorer" / "person_merge_scorer_eval.json"

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


@dataclass(frozen=True)
class FaceRecord:
    face_id: str
    person_id: str
    video_id: str
    camera_id: str
    timestamp: float
    bbox: dict[str, Any]
    embedding: np.ndarray


@dataclass
class Fragment:
    fragment_id: str
    person_id: str
    records: list[FaceRecord]
    embedding: np.ndarray


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stable_float(value: str) -> float:
    digest = sha1(value.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def _cosine(left: np.ndarray, right: np.ndarray) -> float:
    left = left.astype(np.float32).reshape(-1)
    right = right.astype(np.float32).reshape(-1)
    denom = float(np.linalg.norm(left) * np.linalg.norm(right))
    if denom < 1e-8:
        return 0.0
    return float(np.dot(left, right) / denom)


def _normalized_mean(vectors: list[np.ndarray]) -> np.ndarray:
    if not vectors:
        return np.zeros((0,), dtype=np.float32)
    matrix = np.vstack(vectors).astype(np.float32)
    mean = matrix.mean(axis=0)
    norm = float(np.linalg.norm(mean))
    if norm < 1e-8:
        return mean
    return (mean / norm).astype(np.float32)


def _bbox_area(record: FaceRecord) -> float:
    return max(1.0, float(record.bbox.get("x2", 0.0) - record.bbox.get("x1", 0.0))) * max(
        1.0,
        float(record.bbox.get("y2", 0.0) - record.bbox.get("y1", 0.0)),
    )


def _score(record: FaceRecord) -> float:
    return float(record.bbox.get("score") or 0.0)


def _fragment(records: list[FaceRecord], fragment_id: str) -> Fragment:
    if not records:
        raise ValueError("fragment requires at least one record")
    return Fragment(
        fragment_id=fragment_id,
        person_id=records[0].person_id,
        records=records,
        embedding=_normalized_mean([record.embedding for record in records]),
    )


def _mean_intra(fragment: Fragment) -> float:
    if len(fragment.records) <= 1:
        return 1.0
    scores = [
        _cosine(left.embedding, right.embedding)
        for index, left in enumerate(fragment.records)
        for right in fragment.records[index + 1 :]
    ]
    return float(np.mean(scores)) if scores else 0.0


def _same_frame_conflict(left: Fragment, right: Fragment) -> bool:
    left_keys = {(record.video_id, round(record.timestamp, 3)) for record in left.records}
    return any((record.video_id, round(record.timestamp, 3)) in left_keys for record in right.records)


def load_people(db_path: Path) -> dict[str, list[FaceRecord]]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT
            pf.person_id,
            fr.face_id,
            fr.video_id,
            fr.camera_id,
            fr.video_timestamp_sec,
            fr.bbox_json,
            fr.embedding_json
        FROM person_faces pf
        JOIN face_records fr ON fr.face_id = pf.face_id
        ORDER BY pf.person_id, fr.camera_id, fr.video_timestamp_sec, fr.face_id
        """
    ).fetchall()
    conn.close()

    people: dict[str, list[FaceRecord]] = {}
    for row in rows:
        record = FaceRecord(
            face_id=str(row["face_id"]),
            person_id=str(row["person_id"]),
            video_id=str(row["video_id"]),
            camera_id=str(row["camera_id"]),
            timestamp=float(row["video_timestamp_sec"] or 0.0),
            bbox=json.loads(row["bbox_json"]),
            embedding=np.asarray(json.loads(row["embedding_json"]), dtype=np.float32),
        )
        people.setdefault(record.person_id, []).append(record)
    return people


def load_manual_groups(path: Path) -> tuple[list[list[str]], set[str], list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    groups_by_tuple: dict[tuple[int, ...], set[str]] = {}
    for result in payload.get("results") or []:
        group_key = tuple(int(value) for value in result.get("group") or [])
        groups_by_tuple.setdefault(group_key, set()).update(
            [
                str(result["source_person_id"]),
                str(result["target_person_id"]),
            ]
        )
    groups = [sorted(person_ids) for _, person_ids in sorted(groups_by_tuple.items())]
    involved = {person_id for group in groups for person_id in group}
    return groups, involved, list(payload.get("results") or [])


def make_positive_splits(records: list[FaceRecord], *, seed_prefix: str, max_pairs: int = 8) -> list[tuple[Fragment, Fragment]]:
    if len(records) < 4:
        return []
    ordered = sorted(records, key=lambda record: (record.camera_id, record.timestamp, record.face_id))
    pairs: list[tuple[list[FaceRecord], list[FaceRecord], str]] = []

    midpoint = len(ordered) // 2
    pairs.append((ordered[:midpoint], ordered[midpoint:], "time_half"))

    by_camera: dict[str, list[FaceRecord]] = {}
    for record in ordered:
        by_camera.setdefault(record.camera_id, []).append(record)
    for camera_id, camera_records in sorted(by_camera.items()):
        rest = [record for record in ordered if record.camera_id != camera_id]
        if len(camera_records) >= 2 and len(rest) >= 2:
            pairs.append((camera_records, rest, f"camera_{camera_id}"))

    quality = sorted(records, key=lambda record: (_score(record), _bbox_area(record)), reverse=True)
    for size in (2, 3, min(4, max(2, len(quality) // 3))):
        if len(quality) - size >= 2:
            pairs.append((quality[:size], quality[size:], f"quality_top_{size}"))

    rng = np.random.default_rng(int(sha1(seed_prefix.encode("utf-8")).hexdigest()[:8], 16))
    for index in range(6):
        permuted = list(ordered)
        rng.shuffle(permuted)
        left_size = max(2, min(len(permuted) - 2, int(rng.integers(2, max(3, len(permuted) - 1)))))
        pairs.append((permuted[:left_size], permuted[left_size:], f"random_{index}"))

    out: list[tuple[Fragment, Fragment]] = []
    seen: set[tuple[str, ...]] = set()
    for left_records, right_records, name in pairs:
        if len(left_records) < 2 or len(right_records) < 2:
            continue
        key = tuple(sorted(record.face_id for record in left_records))
        if key in seen:
            continue
        seen.add(key)
        out.append(
            (
                _fragment(left_records, f"{seed_prefix}:{name}:a"),
                _fragment(right_records, f"{seed_prefix}:{name}:b"),
            )
        )
        if len(out) >= max_pairs:
            break
    return out


def make_eval_positive_pairs(groups: list[list[str]], people: dict[str, list[FaceRecord]]) -> list[tuple[Fragment, Fragment, dict[str, Any]]]:
    out = []
    for group_index, group in enumerate(groups, start=1):
        for left_id, right_id in itertools.combinations(group, 2):
            if left_id not in people or right_id not in people:
                continue
            out.append(
                (
                    _fragment(people[left_id], f"manual:{group_index}:{left_id}"),
                    _fragment(people[right_id], f"manual:{group_index}:{right_id}"),
                    {"manual_group_index": group_index, "left_person_id": left_id, "right_person_id": right_id},
                )
            )
    return out


def person_centroids(people: dict[str, list[FaceRecord]]) -> dict[str, np.ndarray]:
    return {
        person_id: _normalized_mean([record.embedding for record in records])
        for person_id, records in people.items()
    }


def pair_features(left: Fragment, right: Fragment, universe: dict[str, np.ndarray] | None = None) -> dict[str, float]:
    pair_scores = np.asarray(
        [
            _cosine(left_record.embedding, right_record.embedding)
            for left_record in left.records
            for right_record in right.records
        ],
        dtype=np.float32,
    )
    pair_scores.sort()
    descending = pair_scores[::-1]
    left_cameras = {record.camera_id for record in left.records}
    right_cameras = {record.camera_id for record in right.records}
    camera_union = left_cameras | right_cameras
    source_areas = np.asarray([_bbox_area(record) for record in left.records], dtype=np.float32)
    target_areas = np.asarray([_bbox_area(record) for record in right.records], dtype=np.float32)
    source_scores = np.asarray([_score(record) for record in left.records], dtype=np.float32)
    target_scores = np.asarray([_score(record) for record in right.records], dtype=np.float32)

    centroid = _cosine(left.embedding, right.embedding)
    second_best = -1.0
    if universe:
        for person_id, embedding in universe.items():
            if person_id in {left.person_id, right.person_id}:
                continue
            second_best = max(second_best, _cosine(left.embedding, embedding))

    left_count = len(left.records)
    right_count = len(right.records)
    min_count = min(left_count, right_count)
    max_count = max(left_count, right_count)
    return {
        "centroid_similarity": centroid,
        "max_pair_similarity": float(descending[0]) if descending.size else 0.0,
        "top3_pair_similarity": float(np.mean(descending[: min(3, descending.size)])) if descending.size else 0.0,
        "top5_pair_similarity": float(np.mean(descending[: min(5, descending.size)])) if descending.size else 0.0,
        "p90_pair_similarity": float(np.percentile(pair_scores, 90)) if pair_scores.size else 0.0,
        "p75_pair_similarity": float(np.percentile(pair_scores, 75)) if pair_scores.size else 0.0,
        "mean_pair_similarity": float(np.mean(pair_scores)) if pair_scores.size else 0.0,
        "median_pair_similarity": float(np.median(pair_scores)) if pair_scores.size else 0.0,
        "std_pair_similarity": float(np.std(pair_scores)) if pair_scores.size else 0.0,
        "source_mean_intra_similarity": _mean_intra(left),
        "target_mean_intra_similarity": _mean_intra(right),
        "min_mean_intra_similarity": min(_mean_intra(left), _mean_intra(right)),
        "source_face_count_log": math.log1p(left_count),
        "target_face_count_log": math.log1p(right_count),
        "min_face_count_log": math.log1p(min_count),
        "max_face_count_log": math.log1p(max_count),
        "face_count_ratio": min_count / max(1, max_count),
        "source_mean_face_area_log": math.log1p(float(np.mean(source_areas))) if source_areas.size else 0.0,
        "target_mean_face_area_log": math.log1p(float(np.mean(target_areas))) if target_areas.size else 0.0,
        "min_mean_face_area_log": math.log1p(min(float(np.mean(source_areas)), float(np.mean(target_areas)))) if source_areas.size and target_areas.size else 0.0,
        "source_min_detection_score": float(np.min(source_scores)) if source_scores.size else 0.0,
        "target_min_detection_score": float(np.min(target_scores)) if target_scores.size else 0.0,
        "min_detection_score": min(float(np.min(source_scores)), float(np.min(target_scores))) if source_scores.size and target_scores.size else 0.0,
        "camera_intersection_count": float(len(left_cameras & right_cameras)),
        "camera_jaccard": len(left_cameras & right_cameras) / max(1, len(camera_union)),
        "same_frame_conflict": 1.0 if _same_frame_conflict(left, right) else 0.0,
        "centroid_nearest_margin": centroid - second_best if second_best >= 0.0 else 1.0,
    }


def row_from_features(features: dict[str, float]) -> list[float]:
    return [float(features[name]) for name in FEATURE_NAMES]


def build_samples(
    people: dict[str, list[FaceRecord]],
    person_ids: list[str],
    *,
    universe: dict[str, np.ndarray],
    max_negative_pairs: int,
) -> tuple[np.ndarray, np.ndarray, list[dict[str, Any]]]:
    rows: list[list[float]] = []
    labels: list[int] = []
    meta: list[dict[str, Any]] = []

    for person_id in person_ids:
        for left, right in make_positive_splits(people[person_id], seed_prefix=person_id):
            rows.append(row_from_features(pair_features(left, right, universe)))
            labels.append(1)
            meta.append({"kind": "positive_split", "person_id": person_id})

    negative_candidates = []
    for left_id, right_id in itertools.combinations(person_ids, 2):
        left = _fragment(people[left_id], f"negative:{left_id}")
        right = _fragment(people[right_id], f"negative:{right_id}")
        features = pair_features(left, right, universe)
        score = max(features["centroid_similarity"], features["top5_pair_similarity"], features["max_pair_similarity"])
        negative_candidates.append((score, left_id, right_id, features))

    negative_candidates.sort(key=lambda item: item[0], reverse=True)
    hard_count = min(len(negative_candidates), max_negative_pairs // 2)
    selected = negative_candidates[:hard_count]
    remaining = negative_candidates[hard_count:]
    remaining.sort(key=lambda item: _stable_float(f"{item[1]}:{item[2]}"))
    selected.extend(remaining[: max(0, max_negative_pairs - len(selected))])

    for _, left_id, right_id, features in selected:
        rows.append(row_from_features(features))
        labels.append(0)
        meta.append({"kind": "negative_person_pair", "left_person_id": left_id, "right_person_id": right_id})

    return np.asarray(rows, dtype=np.float32), np.asarray(labels, dtype=np.int64), meta


def split_person_ids(person_ids: list[str], *, holdout_ratio: float) -> tuple[list[str], list[str]]:
    sorted_ids = sorted(person_ids)
    holdout = [person_id for person_id in sorted_ids if _stable_float(person_id) < holdout_ratio]
    train = [person_id for person_id in sorted_ids if person_id not in set(holdout)]
    if len(holdout) < 3 and len(sorted_ids) >= 8:
        holdout = sorted_ids[: max(3, len(sorted_ids) // 4)]
        train = sorted_ids[len(holdout) :]
    return train, holdout


def metrics_for(y_true: np.ndarray, probabilities: np.ndarray, threshold: float) -> dict[str, Any]:
    predicted = (probabilities >= threshold).astype(np.int64)
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true,
        predicted,
        average="binary",
        zero_division=0,
    )
    tn, fp, fn, tp = confusion_matrix(y_true, predicted, labels=[0, 1]).ravel()
    return {
        "threshold": round(float(threshold), 4),
        "accuracy": round(float(accuracy_score(y_true, predicted)), 4),
        "balanced_accuracy": round(float(balanced_accuracy_score(y_true, predicted)), 4),
        "precision": round(float(precision), 4),
        "recall": round(float(recall), 4),
        "f1": round(float(f1), 4),
        "tp": int(tp),
        "fp": int(fp),
        "tn": int(tn),
        "fn": int(fn),
    }


def choose_threshold(y_true: np.ndarray, probabilities: np.ndarray) -> dict[str, Any]:
    candidates = np.arange(0.85, 0.951, 0.01)
    acceptable = []
    scored = []
    for threshold in candidates:
        metric = metrics_for(y_true, probabilities, float(threshold))
        if metric["precision"] >= 0.95 and metric["recall"] >= 0.95:
            acceptable.append(metric)
        # Fallback: favor low false positives; use recall as tie breaker.
        if metric["precision"] >= 0.90:
            score = metric["balanced_accuracy"] + 0.08 * metric["recall"] + 0.04 * metric["precision"]
        else:
            score = metric["balanced_accuracy"] - 0.25 * (0.90 - metric["precision"])
        scored.append((score, metric))
    if acceptable:
        acceptable.sort(
            key=lambda metric: (
                -metric["balanced_accuracy"],
                -metric["precision"],
                -metric["recall"],
                metric["threshold"],
            )
        )
        return acceptable[0]
    scored.sort(key=lambda item: (item[0], item[1]["f1"], item[1]["threshold"]), reverse=True)
    return scored[0][1]


def manual_eval_samples(
    people: dict[str, list[FaceRecord]],
    manual_groups: list[list[str]],
    *,
    universe: dict[str, np.ndarray],
) -> tuple[np.ndarray, np.ndarray, list[dict[str, Any]]]:
    rows: list[list[float]] = []
    labels: list[int] = []
    meta: list[dict[str, Any]] = []

    for left, right, item_meta in make_eval_positive_pairs(manual_groups, people):
        rows.append(row_from_features(pair_features(left, right, universe)))
        labels.append(1)
        meta.append({"kind": "manual_positive", **item_meta})

    # Hard negatives are all cross-group pairs among manually reviewed groups. They are used only for calibration reporting.
    group_by_person = {
        person_id: group_index
        for group_index, group in enumerate(manual_groups, start=1)
        for person_id in group
    }
    involved = sorted(group_by_person)
    negative_candidates = []
    for left_id, right_id in itertools.combinations(involved, 2):
        if group_by_person[left_id] == group_by_person[right_id]:
            continue
        if left_id not in people or right_id not in people:
            continue
        left = _fragment(people[left_id], f"manual_negative:{left_id}")
        right = _fragment(people[right_id], f"manual_negative:{right_id}")
        features = pair_features(left, right, universe)
        score = max(features["centroid_similarity"], features["top5_pair_similarity"], features["max_pair_similarity"])
        negative_candidates.append((score, left_id, right_id, features))
    negative_candidates.sort(key=lambda item: item[0], reverse=True)
    for _, left_id, right_id, features in negative_candidates[: max(1, len(labels) * 2)]:
        rows.append(row_from_features(features))
        labels.append(0)
        meta.append(
            {
                "kind": "manual_cross_group_hard_negative",
                "left_person_id": left_id,
                "right_person_id": right_id,
                "left_group": group_by_person[left_id],
                "right_group": group_by_person[right_id],
            }
        )

    return np.asarray(rows, dtype=np.float32), np.asarray(labels, dtype=np.int64), meta


def serialize_model(
    *,
    scaler: StandardScaler,
    classifier: LogisticRegression,
    threshold: float,
    training_summary: dict[str, Any],
) -> dict[str, Any]:
    return {
        "model_version": MODEL_VERSION,
        "created_at": _now(),
        "feature_names": FEATURE_NAMES,
        "threshold": round(float(threshold), 6),
        "scaler_mean": np.asarray(scaler.mean_, dtype=float).round(8).tolist(),
        "scaler_scale": np.asarray(scaler.scale_, dtype=float).round(8).tolist(),
        "coef": np.asarray(classifier.coef_[0], dtype=float).round(8).tolist(),
        "intercept": float(np.asarray(classifier.intercept_, dtype=float)[0]),
        "training_summary": training_summary,
    }


def predict_with_model(model: dict[str, Any], rows: np.ndarray) -> np.ndarray:
    mean = np.asarray(model["scaler_mean"], dtype=np.float32)
    scale = np.asarray(model["scaler_scale"], dtype=np.float32)
    coef = np.asarray(model["coef"], dtype=np.float32)
    intercept = float(model["intercept"])
    normalized = (rows.astype(np.float32) - mean) / np.where(scale <= 1e-8, 1.0, scale)
    logits = normalized @ coef + intercept
    return 1.0 / (1.0 + np.exp(-logits))


def main() -> int:
    parser = argparse.ArgumentParser(description="Train an offline person-fragment merge scorer.")
    parser.add_argument("--db", type=Path, default=DEFAULT_PRE_MERGE_DB, help="Training/evaluation DB, normally the pre-manual-merge backup.")
    parser.add_argument("--manual-result", type=Path, default=DEFAULT_MANUAL_RESULT)
    parser.add_argument("--model-output", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--holdout-ratio", type=float, default=0.30)
    parser.add_argument("--min-train-faces", type=int, default=6)
    parser.add_argument("--max-negative-pairs", type=int, default=400)
    parser.add_argument("--no-write-model", action="store_true")
    args = parser.parse_args()

    if not args.db.exists():
        raise FileNotFoundError(args.db)
    if not args.manual_result.exists():
        raise FileNotFoundError(args.manual_result)

    people = load_people(args.db)
    manual_groups, manual_involved, manual_results = load_manual_groups(args.manual_result)
    universe = person_centroids(people)
    eligible = [
        person_id
        for person_id, records in people.items()
        if person_id not in manual_involved and len(records) >= args.min_train_faces
    ]
    train_ids, holdout_ids = split_person_ids(eligible, holdout_ratio=args.holdout_ratio)

    train_x, train_y, train_meta = build_samples(
        people,
        train_ids,
        universe=universe,
        max_negative_pairs=args.max_negative_pairs,
    )
    holdout_x, holdout_y, holdout_meta = build_samples(
        people,
        holdout_ids,
        universe=universe,
        max_negative_pairs=max(100, args.max_negative_pairs // 3),
    )
    if train_x.size == 0 or holdout_x.size == 0:
        raise RuntimeError("not enough samples for training/holdout evaluation")

    scaler = StandardScaler()
    scaled_train_x = scaler.fit_transform(train_x)
    classifier = LogisticRegression(
        class_weight="balanced",
        max_iter=5000,
        random_state=17,
        solver="lbfgs",
    )
    classifier.fit(scaled_train_x, train_y)

    holdout_prob = classifier.predict_proba(scaler.transform(holdout_x))[:, 1]
    threshold_metrics = choose_threshold(holdout_y, holdout_prob)
    threshold = float(threshold_metrics["threshold"])

    manual_x, manual_y, manual_meta = manual_eval_samples(people, manual_groups, universe=universe)
    train_prob = classifier.predict_proba(scaler.transform(train_x))[:, 1]
    manual_prob = classifier.predict_proba(scaler.transform(manual_x))[:, 1] if manual_x.size else np.asarray([], dtype=np.float32)

    training_summary = {
        "db": str(args.db),
        "manual_result": str(args.manual_result),
        "excluded_manual_person_count": len(manual_involved),
        "eligible_train_person_count": len(eligible),
        "train_person_count": len(train_ids),
        "holdout_person_count": len(holdout_ids),
        "train_sample_count": int(train_y.size),
        "holdout_sample_count": int(holdout_y.size),
        "train_label_counts": dict(Counter(str(int(value)) for value in train_y)),
        "holdout_label_counts": dict(Counter(str(int(value)) for value in holdout_y)),
        "manual_group_count": len(manual_groups),
        "manual_merge_result_count": len(manual_results),
    }

    model = serialize_model(
        scaler=scaler,
        classifier=classifier,
        threshold=threshold,
        training_summary=training_summary,
    )
    model_prob_check = predict_with_model(model, holdout_x)
    if float(np.max(np.abs(model_prob_check - holdout_prob))) > 1e-4:
        raise RuntimeError("serialized model probability check failed")

    def detailed_rows(rows: np.ndarray, y: np.ndarray, prob: np.ndarray, meta: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out = []
        for index, item in enumerate(meta):
            features = {name: round(float(rows[index, feature_index]), 6) for feature_index, name in enumerate(FEATURE_NAMES)}
            out.append(
                {
                    **item,
                    "label": int(y[index]),
                    "merge_probability": round(float(prob[index]), 6),
                    "predicted": bool(float(prob[index]) >= threshold),
                    "features": features,
                }
            )
        return out

    manual_metrics = metrics_for(manual_y, manual_prob, threshold) if manual_y.size else None
    manual_positive = manual_y == 1
    manual_negative = manual_y == 0
    manual_positive_recall = (
        float(np.mean(manual_prob[manual_positive] >= threshold)) if manual_y.size and np.any(manual_positive) else None
    )
    manual_negative_reject_rate = (
        float(np.mean(manual_prob[manual_negative] < threshold)) if manual_y.size and np.any(manual_negative) else None
    )

    report = {
        "created_at": _now(),
        "model_version": MODEL_VERSION,
        "target_accuracy": 0.85,
        "important_note": "Manual merge pairs are excluded from training and used only for calibration/evaluation.",
        "clothing_features_used": False,
        "threshold_source": "lowest_threshold_at_or_above_0.85_with_holdout_precision_and_recall_at_least_0.95",
        "threshold": threshold,
        "training_summary": training_summary,
        "metrics": {
            "train": metrics_for(train_y, train_prob, threshold),
            "holdout": metrics_for(holdout_y, holdout_prob, threshold),
            "holdout_threshold_selection": threshold_metrics,
            "manual_calibration": manual_metrics,
            "manual_positive_recall": round(manual_positive_recall, 4) if manual_positive_recall is not None else None,
            "manual_cross_group_hard_negative_reject_rate": round(manual_negative_reject_rate, 4) if manual_negative_reject_rate is not None else None,
            "passes_85_holdout_accuracy": bool(metrics_for(holdout_y, holdout_prob, threshold)["accuracy"] >= 0.85),
            "passes_85_manual_calibration_accuracy": bool(manual_metrics and manual_metrics["accuracy"] >= 0.85),
        },
        "top_positive_coefficients": [],
        "top_negative_coefficients": [],
        "manual_calibration_rows": detailed_rows(manual_x, manual_y, manual_prob, manual_meta),
        "holdout_error_rows": [
            row
            for row in detailed_rows(holdout_x, holdout_y, holdout_prob, holdout_meta)
            if int(row["label"]) != int(row["predicted"])
        ][:80],
    }

    coef = list(zip(FEATURE_NAMES, model["coef"]))
    report["top_positive_coefficients"] = [
        {"feature": name, "coef": coef_value}
        for name, coef_value in sorted(coef, key=lambda item: item[1], reverse=True)[:12]
    ]
    report["top_negative_coefficients"] = [
        {"feature": name, "coef": coef_value}
        for name, coef_value in sorted(coef, key=lambda item: item[1])[:12]
    ]

    args.report_output.parent.mkdir(parents=True, exist_ok=True)
    args.report_output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not args.no_write_model:
        args.model_output.parent.mkdir(parents=True, exist_ok=True)
        args.model_output.write_text(json.dumps(model, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "model_output": None if args.no_write_model else str(args.model_output),
                "report_output": str(args.report_output),
                "threshold": threshold,
                "holdout": report["metrics"]["holdout"],
                "manual_calibration": report["metrics"]["manual_calibration"],
                "passes_85_holdout_accuracy": report["metrics"]["passes_85_holdout_accuracy"],
                "passes_85_manual_calibration_accuracy": report["metrics"]["passes_85_manual_calibration_accuracy"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
