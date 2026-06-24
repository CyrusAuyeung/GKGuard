from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

import sys

sys.path.insert(0, str(ROOT))

from app.core.config import settings  # noqa: E402
from app.vision.upper_color_postprocess import choose_upper_color_from_probs  # noqa: E402


DEFAULT_BASELINE_DB = (
    settings.data_dir
    / "evals"
    / "database_snapshots"
    / "campusvision_eval_baseline_20260623_pre_full_api_rerun.sqlite3"
)
DEFAULT_OUTPUT = settings.data_dir / "evals" / "target_metrics" / "c1_target_metrics.json"
DEFAULT_MANUAL_PERSON_MERGE_DIR = settings.data_dir / "backups" / "manual_person_merge_20260623_100235"
DEFAULT_MANUAL_PERSON_MERGE_RESULT = DEFAULT_MANUAL_PERSON_MERGE_DIR / "manual_person_merge_result.json"
DEFAULT_MANUAL_PERSON_MERGE_REFERENCE_DB = DEFAULT_MANUAL_PERSON_MERGE_DIR / "campusvision.sqlite3"

TARGETS = {
    "person_aggregation_pairwise_precision": 0.95,
    "person_aggregation_pairwise_f1": 0.85,
    "outfit_grouping_pairwise_f1": 0.90,
    "outfit_grouping_purity": 0.98,
    "upper_color_outfit_accuracy": 0.80,
    "api_processing_realtime_factor": 1.0,
    "api_processing_ideal_max_sec": 15.0,
}


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _one(conn: sqlite3.Connection, sql: str) -> Any:
    return conn.execute(sql).fetchone()[0]


def _table_count(conn: sqlite3.Connection, table: str) -> int:
    return int(_one(conn, f"SELECT COUNT(*) FROM {table}"))


def _db_counts(db_path: Path) -> dict[str, Any]:
    with _connect(db_path) as conn:
        counts = {
            "cameras": _table_count(conn, "cameras"),
            "videos": _table_count(conn, "videos"),
            "indexed_videos": int(_one(conn, "SELECT COUNT(*) FROM videos WHERE status = 'indexed'")),
            "face_records": _table_count(conn, "face_records"),
            "person_observations": _table_count(conn, "person_observations"),
            "events": _table_count(conn, "events"),
            "identified_events": int(_one(conn, "SELECT COUNT(*) FROM events WHERE person_id IS NOT NULL")),
            "persons": _table_count(conn, "persons"),
            "person_faces": _table_count(conn, "person_faces"),
            "appearance_sessions": _table_count(conn, "appearance_sessions"),
        }
        counts["identified_event_rate"] = (
            round(counts["identified_events"] / counts["events"], 6) if counts["events"] else None
        )
        counts["person_face_coverage"] = (
            round(counts["person_faces"] / counts["face_records"], 6) if counts["face_records"] else None
        )
        counts["upper_unknown_events"] = int(
            _one(
                conn,
                """
                SELECT COUNT(*)
                FROM events
                WHERE COALESCE(normalized_upper_color, upper_color, 'unknown') = 'unknown'
                """,
            )
        )
        counts["upper_unknown_event_rate"] = (
            round(counts["upper_unknown_events"] / counts["events"], 6) if counts["events"] else None
        )
        counts["upper_unknown_observations"] = int(
            _one(
                conn,
                """
                SELECT COUNT(*)
                FROM person_observations
                WHERE COALESCE(upper_color, 'unknown') = 'unknown'
                """,
            )
        )
        counts["upper_unknown_observation_rate"] = (
            round(counts["upper_unknown_observations"] / counts["person_observations"], 6)
            if counts["person_observations"]
            else None
        )
    return counts


def _person_fragmentation(db_path: Path) -> dict[str, Any]:
    with _connect(db_path) as conn:
        rows = [dict(row) for row in conn.execute("SELECT face_count FROM persons").fetchall()]
    face_counts = [int(row["face_count"] or 0) for row in rows]
    return {
        "persons": len(face_counts),
        "total_person_faces": sum(face_counts),
        "min_faces": min(face_counts) if face_counts else None,
        "max_faces": max(face_counts) if face_counts else None,
        "avg_faces": round(mean(face_counts), 6) if face_counts else None,
        "small_persons_le3": sum(1 for count in face_counts if count <= 3),
        "small_person_rate_le3": round(sum(1 for count in face_counts if count <= 3) / len(face_counts), 6)
        if face_counts
        else None,
        "stable_persons_ge10": sum(1 for count in face_counts if count >= 10),
        "stable_person_rate_ge10": round(sum(1 for count in face_counts if count >= 10) / len(face_counts), 6)
        if face_counts
        else None,
        "histogram": {str(count): face_counts.count(count) for count in sorted(set(face_counts))},
    }


def _bbox_iou(left: dict[str, Any], right: dict[str, Any]) -> float:
    left_x1, left_y1, left_x2, left_y2 = (float(left[key]) for key in ("x1", "y1", "x2", "y2"))
    right_x1, right_y1, right_x2, right_y2 = (float(right[key]) for key in ("x1", "y1", "x2", "y2"))
    inter_w = max(0.0, min(left_x2, right_x2) - max(left_x1, right_x1))
    inter_h = max(0.0, min(left_y2, right_y2) - max(left_y1, right_y1))
    inter = inter_w * inter_h
    left_area = max(0.0, left_x2 - left_x1) * max(0.0, left_y2 - left_y1)
    right_area = max(0.0, right_x2 - right_x1) * max(0.0, right_y2 - right_y1)
    return inter / max(1e-9, left_area + right_area - inter)


def _manual_merge_groups(data: dict[str, Any]) -> tuple[list[list[str]], dict[str, int]]:
    number_to_person_id: dict[int, str] = {}
    for item in data.get("merge_plan") or []:
        if not isinstance(item, dict):
            continue
        for number_key, person_key in (
            ("source_number", "source_person_id"),
            ("target_number", "target_person_id"),
        ):
            number = item.get(number_key)
            person_id = item.get(person_key)
            if number is None or not person_id:
                continue
            number_to_person_id[int(number)] = str(person_id)

    groups: list[list[str]] = []
    for raw_group in data.get("groups") or []:
        if not isinstance(raw_group, list):
            continue
        group = [number_to_person_id[int(number)] for number in raw_group if int(number) in number_to_person_id]
        if len(group) >= 2:
            groups.append(group)
    person_number = {person_id: number for number, person_id in number_to_person_id.items()}
    return groups, person_number


def _manual_person_merge_current_db_report(
    current_db: Path,
    *,
    reference_db: Path = DEFAULT_MANUAL_PERSON_MERGE_REFERENCE_DB,
    manual_result_path: Path = DEFAULT_MANUAL_PERSON_MERGE_RESULT,
    timestamp_tolerance_sec: float = 0.05,
    min_iou: float = 0.50,
) -> dict[str, Any]:
    data = _read_json(manual_result_path)
    if not data:
        return {
            "status": "not_available",
            "source": str(manual_result_path),
            "reference_db": str(reference_db),
            "current_db": str(current_db),
            "note": "manual person merge result is missing or unreadable",
        }
    if not reference_db.exists() or not current_db.exists():
        return {
            "status": "not_available",
            "source": str(manual_result_path),
            "reference_db": str(reference_db),
            "current_db": str(current_db),
            "note": "reference or current database is missing",
        }

    groups, person_number = _manual_merge_groups(data)
    if not groups:
        return {
            "status": "not_available",
            "source": str(manual_result_path),
            "reference_db": str(reference_db),
            "current_db": str(current_db),
            "note": "manual person merge groups are missing",
        }

    current_by_camera: dict[str, list[dict[str, Any]]] = {}
    with _connect(current_db) as current_conn:
        rows = current_conn.execute(
            """
            SELECT fr.face_id, fr.camera_id, fr.video_timestamp_sec, fr.bbox_json, pf.person_id
            FROM face_records fr
            JOIN person_faces pf ON pf.face_id = fr.face_id
            """
        ).fetchall()
        for row in rows:
            try:
                bbox = json.loads(row["bbox_json"])
            except Exception:
                continue
            current_by_camera.setdefault(str(row["camera_id"]), []).append(
                {
                    "face_id": row["face_id"],
                    "person_id": row["person_id"],
                    "timestamp": float(row["video_timestamp_sec"] or 0.0),
                    "bbox": bbox,
                }
            )

    old_person_ids = sorted({person_id for group in groups for person_id in group})
    old_to_current: dict[str, str | None] = {}
    old_person_reports: list[dict[str, Any]] = []
    total_reference_faces = 0
    total_matched_faces = 0
    total_unmatched_faces = 0
    with _connect(reference_db) as reference_conn:
        for old_person_id in old_person_ids:
            rows = reference_conn.execute(
                """
                SELECT fr.face_id, fr.camera_id, fr.video_timestamp_sec, fr.bbox_json
                FROM face_records fr
                JOIN person_faces pf ON pf.face_id = fr.face_id
                WHERE pf.person_id = ?
                ORDER BY fr.camera_id, fr.video_timestamp_sec, fr.face_id
                """,
                (old_person_id,),
            ).fetchall()
            current_counts: Counter[str] = Counter()
            matched_ious: list[float] = []
            unmatched = 0
            for row in rows:
                total_reference_faces += 1
                try:
                    old_bbox = json.loads(row["bbox_json"])
                except Exception:
                    unmatched += 1
                    total_unmatched_faces += 1
                    continue

                old_timestamp = float(row["video_timestamp_sec"] or 0.0)
                candidates = [
                    candidate
                    for candidate in current_by_camera.get(str(row["camera_id"]), [])
                    if abs(candidate["timestamp"] - old_timestamp) <= timestamp_tolerance_sec
                ]
                best_candidate = None
                best_iou = -1.0
                for candidate in candidates:
                    candidate_iou = _bbox_iou(old_bbox, candidate["bbox"])
                    if candidate_iou > best_iou:
                        best_iou = candidate_iou
                        best_candidate = candidate
                if best_candidate is None or best_iou < min_iou:
                    unmatched += 1
                    total_unmatched_faces += 1
                    continue

                current_counts[str(best_candidate["person_id"])] += 1
                matched_ious.append(best_iou)
                total_matched_faces += 1

            dominant = current_counts.most_common(1)[0] if current_counts else (None, 0)
            old_to_current[old_person_id] = dominant[0]
            old_person_reports.append(
                {
                    "manual_number": person_number.get(old_person_id),
                    "reference_person_id": old_person_id,
                    "reference_face_count": len(rows),
                    "matched_face_count": sum(current_counts.values()),
                    "unmatched_face_count": unmatched,
                    "dominant_current_person_id": dominant[0],
                    "dominant_current_face_count": dominant[1],
                    "current_person_counts": dict(current_counts.most_common()),
                    "mean_match_iou": round(mean(matched_ious), 6) if matched_ious else None,
                }
            )

    tp = fp = tn = fn = 0
    false_positive_pairs = []
    false_negative_pairs = []
    positive_pairs = 0
    negative_pairs = 0
    for left_group_index, left_group in enumerate(groups):
        for left_index, left_person_id in enumerate(left_group):
            for right_person_id in left_group[left_index + 1 :]:
                positive_pairs += 1
                left_current = old_to_current.get(left_person_id)
                right_current = old_to_current.get(right_person_id)
                predicted_same = bool(left_current and right_current and left_current == right_current)
                if predicted_same:
                    tp += 1
                else:
                    fn += 1
                    false_negative_pairs.append(
                        {
                            "left_manual_number": person_number.get(left_person_id),
                            "right_manual_number": person_number.get(right_person_id),
                            "left_reference_person_id": left_person_id,
                            "right_reference_person_id": right_person_id,
                            "left_current_person_id": left_current,
                            "right_current_person_id": right_current,
                        }
                    )

        for right_group in groups[left_group_index + 1 :]:
            for left_person_id in left_group:
                for right_person_id in right_group:
                    negative_pairs += 1
                    left_current = old_to_current.get(left_person_id)
                    right_current = old_to_current.get(right_person_id)
                    predicted_same = bool(left_current and right_current and left_current == right_current)
                    if predicted_same:
                        fp += 1
                        false_positive_pairs.append(
                            {
                                "left_manual_number": person_number.get(left_person_id),
                                "right_manual_number": person_number.get(right_person_id),
                                "left_reference_person_id": left_person_id,
                                "right_reference_person_id": right_person_id,
                                "current_person_id": left_current,
                            }
                        )
                    else:
                        tn += 1

    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = (
        2.0 * precision * recall / (precision + recall)
        if precision is not None and recall is not None and (precision + recall) > 0.0
        else None
    )
    return {
        "status": "evaluated",
        "source": str(manual_result_path),
        "reference_db": str(reference_db),
        "current_db": str(current_db),
        "projection_method": "camera_timestamp_bbox_iou",
        "timestamp_tolerance_sec": timestamp_tolerance_sec,
        "min_iou": min_iou,
        "manual_group_count": len(groups),
        "manual_fragment_count": len(old_person_ids),
        "reference_face_count": total_reference_faces,
        "matched_face_count": total_matched_faces,
        "unmatched_face_count": total_unmatched_faces,
        "matched_face_rate": round(total_matched_faces / total_reference_faces, 6)
        if total_reference_faces
        else None,
        "positive_pairs": positive_pairs,
        "negative_pairs": negative_pairs,
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "precision": round(precision, 6) if precision is not None else None,
        "recall": round(recall, 6) if recall is not None else None,
        "f1": round(f1, 6) if f1 is not None else None,
        "passes_precision_target": (
            precision is not None and precision >= TARGETS["person_aggregation_pairwise_precision"]
        ),
        "passes_f1_target": f1 is not None and f1 >= TARGETS["person_aggregation_pairwise_f1"],
        "false_positive_pairs": false_positive_pairs[:50],
        "false_negative_pairs": false_negative_pairs[:50],
        "old_person_projection": old_person_reports,
        "note": "Manual merge labels are eval-only; this projects old manual fragments to the current DB by camera/timestamp/bbox.",
    }


def _camera_event_stats(db_path: Path) -> list[dict[str, Any]]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
                camera_id,
                COUNT(*) AS events,
                SUM(CASE WHEN person_id IS NOT NULL THEN 1 ELSE 0 END) AS identified
            FROM events
            GROUP BY camera_id
            ORDER BY camera_id
            """
        ).fetchall()
    result = []
    for row in rows:
        events = int(row["events"] or 0)
        identified = int(row["identified"] or 0)
        result.append(
            {
                "camera_id": row["camera_id"],
                "events": events,
                "identified": identified,
                "identified_rate": round(identified / events, 6) if events else None,
            }
        )
    return result


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _video_duration_sec(path: str | None) -> float | None:
    if not path:
        return None
    try:
        import cv2
    except Exception:
        return None

    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return None
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    frames = float(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
    cap.release()
    if fps <= 0.0 or frames <= 0.0:
        return None
    return frames / fps


def _api_processing_metrics(db_path: Path) -> dict[str, Any]:
    rows: list[sqlite3.Row]
    with _connect(db_path) as conn:
        video_columns = {row["name"] for row in conn.execute("PRAGMA table_info(videos)").fetchall()}
        has_processing_duration = "processing_duration_sec" in video_columns
        duration_select = "processing_duration_sec" if has_processing_duration else "NULL AS processing_duration_sec"
        rows = conn.execute(
            f"""
            SELECT video_id, filename, camera_id, path, created_at, updated_at, {duration_select}
            FROM videos
            WHERE status = 'indexed'
            ORDER BY created_at
            """
        ).fetchall()

    videos = []
    for row in rows:
        created = _parse_datetime(row["created_at"])
        updated = _parse_datetime(row["updated_at"])
        measured_processing_sec = row["processing_duration_sec"]
        processing_sec = (
            float(measured_processing_sec)
            if measured_processing_sec is not None
            else ((updated - created).total_seconds() if created and updated else None)
        )
        processing_source = "processing_duration_sec" if measured_processing_sec is not None else "updated_at_minus_created_at"
        duration_sec = _video_duration_sec(row["path"])
        realtime_factor = (
            processing_sec / duration_sec
            if processing_sec is not None and duration_sec and duration_sec > 0.0
            else None
        )
        videos.append(
            {
                "video_id": row["video_id"],
                "filename": row["filename"],
                "camera_id": row["camera_id"],
                "processing_sec": round(processing_sec, 3) if processing_sec is not None else None,
                "processing_source": processing_source,
                "video_duration_sec": round(duration_sec, 3) if duration_sec is not None else None,
                "realtime_factor": round(realtime_factor, 6) if realtime_factor is not None else None,
            }
        )

    factors = [item["realtime_factor"] for item in videos if item["realtime_factor"] is not None]
    processing = [item["processing_sec"] for item in videos if item["processing_sec"] is not None]
    slower_than_realtime = [
        item
        for item in videos
        if item["realtime_factor"] is not None and item["realtime_factor"] > TARGETS["api_processing_realtime_factor"]
    ]
    slower_than_ideal = [
        item
        for item in videos
        if item["processing_sec"] is not None and item["processing_sec"] > TARGETS["api_processing_ideal_max_sec"]
    ]
    history = {
        "videos": len(videos),
        "mean_processing_sec": round(mean(processing), 6) if processing else None,
        "max_processing_sec": max(processing) if processing else None,
        "mean_realtime_factor": round(mean(factors), 6) if factors else None,
        "max_realtime_factor": max(factors) if factors else None,
        "passes_realtime_mean": bool(factors and mean(factors) <= TARGETS["api_processing_realtime_factor"]),
        "passes_realtime_all": bool(factors and not slower_than_realtime),
        "passes_ideal_max_processing_sec": bool(processing and max(processing) <= TARGETS["api_processing_ideal_max_sec"]),
        "videos_slower_than_realtime": [
            {
                "video_id": item["video_id"],
                "filename": item["filename"],
                "camera_id": item["camera_id"],
                "processing_sec": item["processing_sec"],
                "processing_source": item["processing_source"],
                "video_duration_sec": item["video_duration_sec"],
                "realtime_factor": item["realtime_factor"],
            }
            for item in slower_than_realtime
        ],
        "videos_slower_than_ideal": [
            {
                "video_id": item["video_id"],
                "filename": item["filename"],
                "camera_id": item["camera_id"],
                "processing_sec": item["processing_sec"],
                "processing_source": item["processing_source"],
            }
            for item in slower_than_ideal
        ],
        "per_video": videos,
    }
    benchmark = _api_processing_benchmark_report()
    if benchmark:
        source = benchmark
        metric_source = "current_benchmark"
        slower_realtime = (
            []
            if _metric_leq(source.get("max_realtime_factor"), TARGETS["api_processing_realtime_factor"])
            else [_api_processing_source_summary(source)]
        )
        slower_ideal = (
            []
            if _metric_leq(source.get("max_processing_sec"), TARGETS["api_processing_ideal_max_sec"])
            else [_api_processing_source_summary(source)]
        )
    else:
        source = history
        metric_source = "video_history"
        slower_realtime = history["videos_slower_than_realtime"]
        slower_ideal = history["videos_slower_than_ideal"]

    return {
        "metric_source": metric_source,
        "benchmark": benchmark,
        "history": history,
        "videos": source.get("videos", len(benchmark.get("measured_runs", [])) if benchmark else len(videos)),
        "mean_processing_sec": source.get("mean_processing_sec"),
        "max_processing_sec": source.get("max_processing_sec"),
        "mean_realtime_factor": source.get("mean_realtime_factor"),
        "max_realtime_factor": source.get("max_realtime_factor"),
        "passes_realtime_mean": _metric_leq(
            source.get("mean_realtime_factor"),
            TARGETS["api_processing_realtime_factor"],
        ),
        "passes_realtime_all": _metric_leq(
            source.get("max_realtime_factor"),
            TARGETS["api_processing_realtime_factor"],
        ),
        "passes_ideal_max_processing_sec": _metric_leq(
            source.get("max_processing_sec"),
            TARGETS["api_processing_ideal_max_sec"],
        ),
        "videos_slower_than_realtime": slower_realtime,
        "videos_slower_than_ideal": slower_ideal,
        "per_video": videos,
    }


def _metric_leq(value: Any, target: float) -> bool:
    try:
        return value is not None and float(value) <= float(target)
    except (TypeError, ValueError):
        return False


def _api_processing_benchmark_report() -> dict[str, Any] | None:
    path = settings.data_dir / "evals" / "runtime" / "c1_api_processing_benchmark.json"
    data = _read_json(path)
    if not data:
        return None
    measured = data.get("measured_runs")
    if not isinstance(measured, list) or not measured:
        return None
    return {
        "source": str(path),
        "schema_version": data.get("schema_version"),
        "generated_at": data.get("generated_at"),
        "benchmark_source": data.get("source"),
        "video_id": data.get("video_id"),
        "filename": data.get("filename"),
        "camera_id": data.get("camera_id"),
        "video_duration_sec": data.get("video_duration_sec"),
        "frame_interval_sec": data.get("frame_interval_sec"),
        "videos": len(measured),
        "mean_processing_sec": data.get("mean_processing_sec"),
        "max_processing_sec": data.get("max_processing_sec"),
        "mean_realtime_factor": data.get("mean_realtime_factor"),
        "max_realtime_factor": data.get("max_realtime_factor"),
        "warmup_runs": data.get("warmup_runs") or [],
        "measured_runs": measured,
        "temp_data_dir": data.get("temp_data_dir"),
    }


def _api_processing_source_summary(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "video_id": source.get("video_id"),
        "filename": source.get("filename"),
        "camera_id": source.get("camera_id"),
        "processing_sec": source.get("max_processing_sec"),
        "video_duration_sec": source.get("video_duration_sec"),
        "realtime_factor": source.get("max_realtime_factor"),
        "processing_source": source.get("benchmark_source") or source.get("metric_source"),
    }


def _person_merge_report(current_db: Path) -> dict[str, Any]:
    path = settings.data_dir / "evals" / "person_merge_scorer" / "person_merge_scorer_eval.json"
    data = _read_json(path)
    metrics = data.get("metrics") if isinstance(data.get("metrics"), dict) else {}
    holdout = metrics.get("holdout") if isinstance(metrics.get("holdout"), dict) else {}
    manual = metrics.get("manual_calibration") if isinstance(metrics.get("manual_calibration"), dict) else {}
    current_manual = _manual_person_merge_current_db_report(current_db)
    current_precision = current_manual.get("precision") if current_manual.get("status") == "evaluated" else None
    current_f1 = current_manual.get("f1") if current_manual.get("status") == "evaluated" else None
    precision_for_target = current_precision if current_precision is not None else holdout.get("precision")
    f1_for_target = current_f1 if current_f1 is not None else holdout.get("f1")
    return {
        "source": str(path),
        "model_version": data.get("model_version"),
        "threshold": data.get("threshold"),
        "clothing_features_used": data.get("clothing_features_used"),
        "holdout_precision": holdout.get("precision"),
        "holdout_recall": holdout.get("recall"),
        "holdout_f1": holdout.get("f1"),
        "manual_calibration_precision": manual.get("precision"),
        "manual_calibration_recall": manual.get("recall"),
        "manual_calibration_f1": manual.get("f1"),
        "current_db_manual_eval": current_manual,
        "target_metric_source": "current_db_manual_eval"
        if current_precision is not None and current_f1 is not None
        else "holdout_report",
        "passes_precision_target": (
            precision_for_target is not None
            and float(precision_for_target) >= TARGETS["person_aggregation_pairwise_precision"]
        ),
        "passes_f1_target": (
            f1_for_target is not None
            and float(f1_for_target) >= TARGETS["person_aggregation_pairwise_f1"]
        ),
        "caveat": "Manual merge labels are eval-only and limited, but target pass/fail prefers current DB projection when available.",
    }


def _outfit_grouping_report() -> dict[str, Any]:
    path = settings.data_dir / "evals" / "manual_event_outfit_groups" / "event_outfit_group_eval.json"
    data = _read_json(path)
    pairwise = data.get("pairwise") if isinstance(data.get("pairwise"), dict) else {}
    purity = data.get("purity") if isinstance(data.get("purity"), dict) else {}
    f1 = pairwise.get("f1")
    purity_accuracy = purity.get("purity_accuracy")
    events = int(data.get("events") or 0)
    pair_count = int(pairwise.get("pair_count") or 0)
    purity_total = int(purity.get("purity_total") or 0)
    status = str(data.get("status") or "")
    if not status:
        if not data:
            status = "not_available"
        elif events <= 0 or pair_count <= 0 or purity_total <= 0:
            status = "not_replayable"
        else:
            status = "evaluated"
    metric_available = bool(events > 0 and pair_count > 0 and purity_total > 0)
    target_metric_eligible = bool(data.get("target_metric_eligible", metric_available)) and metric_available
    status_reason = data.get("status_reason")
    if status == "not_replayable" and not status_reason:
        status_reason = "Manual event outfit labels did not match the current DB; rerun remap evaluation first."
    elif status == "not_available" and not status_reason:
        status_reason = "Event outfit grouping evaluation report is missing or unreadable."
    return {
        "source": str(path),
        "status": status,
        "status_reason": status_reason,
        "metric_available": metric_available,
        "target_metric_eligible": target_metric_eligible,
        "grouping_version": data.get("grouping_version"),
        "persons": data.get("persons"),
        "events": events,
        "manual_assignment_count": data.get("manual_assignment_count"),
        "evaluated_assignment_count": data.get("evaluated_assignment_count"),
        "evaluated_assignment_rate": data.get("evaluated_assignment_rate"),
        "manual_group_count": data.get("manual_group_count"),
        "predicted_group_count": data.get("predicted_group_count"),
        "remap": data.get("remap") if isinstance(data.get("remap"), dict) else None,
        "pairwise_precision": pairwise.get("precision"),
        "pairwise_recall": pairwise.get("recall"),
        "pairwise_f1": f1,
        "macro_f1": pairwise.get("macro_f1"),
        "purity": purity_accuracy,
        "passes_f1_target": (
            target_metric_eligible
            and f1 is not None
            and float(f1) >= TARGETS["outfit_grouping_pairwise_f1"]
        ),
        "passes_purity_target": (
            target_metric_eligible
            and purity_accuracy is not None
            and float(purity_accuracy) >= TARGETS["outfit_grouping_purity"]
        ),
    }


def _upper_color_reports() -> dict[str, Any]:
    manual_path = settings.data_dir / "evals" / "manual_clothing_labels" / "manual_clothing_eval.json"
    clip_path = settings.data_dir / "evals" / "clip_upper_color" / "h14_schp_profiles_v3.json"
    manual = _read_json(manual_path)
    clip = _read_json(clip_path)

    upper_only = manual.get("upper_only_sample_event_metrics")
    upper_person = manual.get("upper_only_core_metrics")
    reports = clip.get("reports") if isinstance(clip.get("reports"), dict) else {}
    online_candidate = reports.get("profile_realtime_balanced_prompt_v2")
    if not isinstance(online_candidate, dict):
        online_candidate = {}
    prob_group = online_candidate.get("prob_group_metrics")
    group = online_candidate.get("group_metrics")
    event = online_candidate.get("event_metrics")
    if not isinstance(prob_group, dict):
        prob_group = {}
    if not isinstance(group, dict):
        group = {}
    if not isinstance(event, dict):
        event = {}

    calibrated_group = _calibrated_upper_group_metrics(online_candidate)
    event_unknown_false = _upper_unknown_false_metrics(online_candidate.get("details"))
    group_unknown_false = _upper_unknown_false_metrics(group.get("per_group"))
    prob_group_unknown_false = _upper_unknown_false_metrics(prob_group.get("per_group"))
    calibrated_group_unknown_false = (
        _upper_unknown_false_metrics(calibrated_group.get("per_group")) if calibrated_group else None
    )
    outfit_accuracy = (
        calibrated_group.get("accuracy")
        if calibrated_group
        else prob_group.get("accuracy") or group.get("accuracy")
    )
    selected_unknown_false = calibrated_group_unknown_false or prob_group_unknown_false or group_unknown_false
    return {
        "manual_eval_source": str(manual_path),
        "clip_eval_source": str(clip_path),
        "manual_upper_sample_event_accuracy": (upper_only or {}).get("color_accuracy")
        if isinstance(upper_only, dict)
        else None,
        "manual_upper_person_accuracy": (upper_person or {}).get("color_accuracy")
        if isinstance(upper_person, dict)
        else None,
        "online_candidate": "profile_realtime_balanced_prompt_v2",
        "candidate_event_accuracy": event.get("accuracy"),
        "candidate_group_accuracy": group.get("accuracy"),
        "candidate_prob_group_accuracy": prob_group.get("accuracy"),
        "candidate_calibrated_prob_group_accuracy": calibrated_group.get("accuracy") if calibrated_group else None,
        "candidate_event_unknown_false_metrics": event_unknown_false,
        "candidate_group_unknown_false_metrics": group_unknown_false,
        "candidate_prob_group_unknown_false_metrics": prob_group_unknown_false,
        "candidate_calibrated_prob_group_unknown_false_metrics": calibrated_group_unknown_false,
        "selected_outfit_unknown_false_rate": (
            selected_unknown_false.get("false_unknown_rate") if selected_unknown_false else None
        ),
        "selected_outfit_unknown_false_count": (
            selected_unknown_false.get("false_unknown_count") if selected_unknown_false else None
        ),
        "candidate_calibrated_prob_group_metrics": calibrated_group,
        "selected_outfit_accuracy": outfit_accuracy,
        "passes_outfit_accuracy_target": (
            outfit_accuracy is not None and float(outfit_accuracy) >= TARGETS["upper_color_outfit_accuracy"]
        ),
    }


def _upper_unknown_false_metrics(records: Any) -> dict[str, Any]:
    if not isinstance(records, list):
        return {
            "manual_visible_total": 0,
            "false_unknown_count": 0,
            "false_unknown_rate": None,
            "unknown_prediction_count": 0,
            "unknown_prediction_rate": None,
        }

    manual_visible_total = 0
    false_unknown_count = 0
    unknown_prediction_count = 0
    examples = []
    for record in records:
        if not isinstance(record, dict):
            continue
        manual = str(record.get("manual_upper_color") or "unknown")
        predicted = str(record.get("predicted_upper_color") or "unknown")
        if predicted == "unknown":
            unknown_prediction_count += 1
        if manual in {"unknown", "other"}:
            continue
        manual_visible_total += 1
        if predicted == "unknown":
            false_unknown_count += 1
            if len(examples) < 20:
                examples.append(
                    {
                        "person_id": record.get("person_id"),
                        "split_group": record.get("split_group"),
                        "event_id": record.get("event_id"),
                        "observation_id": record.get("observation_id"),
                        "manual_upper_color": manual,
                        "predicted_upper_color": predicted,
                    }
                )

    return {
        "manual_visible_total": manual_visible_total,
        "false_unknown_count": false_unknown_count,
        "false_unknown_rate": round(false_unknown_count / manual_visible_total, 6)
        if manual_visible_total
        else None,
        "unknown_prediction_count": unknown_prediction_count,
        "unknown_prediction_rate": round(unknown_prediction_count / len(records), 6) if records else None,
        "examples": examples,
    }


def _calibrated_upper_group_metrics(report: dict[str, Any]) -> dict[str, Any] | None:
    details = report.get("details")
    if not isinstance(details, list) or not details:
        return None

    grouped: dict[tuple[str, str], list[dict[str, float]]] = {}
    truth: dict[tuple[str, str], str] = {}
    for detail in details:
        if not isinstance(detail, dict):
            continue
        probs = detail.get("probs")
        if not isinstance(probs, dict):
            continue
        key = (str(detail.get("person_id") or ""), str(detail.get("split_group") or ""))
        if key == ("", ""):
            continue
        truth[key] = str(detail.get("manual_upper_color") or "unknown")
        grouped.setdefault(key, []).append(
            {
                str(color): float(value or 0.0)
                for color, value in probs.items()
                if color not in {"unknown", "other"}
            }
        )

    if not truth:
        return None

    correct = 0
    confusion: Counter[tuple[str, str]] = Counter()
    per_group = []
    for key in sorted(truth):
        sample_probs = grouped.get(key) or []
        if sample_probs:
            totals: Counter[str] = Counter()
            for probs in sample_probs:
                for color, probability in probs.items():
                    totals[color] += float(probability)
            averaged = {color: value / len(sample_probs) for color, value in totals.items()}
            predicted = choose_upper_color_from_probs(averaged)
            confidence = float(averaged.get(predicted, 0.0))
        else:
            predicted = "unknown"
            confidence = 0.0
            averaged = {}
        manual = truth[key]
        is_correct = predicted == manual
        correct += int(is_correct)
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
                "probs": {
                    color: round(float(value), 6)
                    for color, value in sorted(averaged.items())
                },
            }
        )

    total = len(truth)
    return {
        "postprocess": "upper_color_prob_postprocess_v1",
        "total": total,
        "correct": correct,
        "accuracy": round(correct / total, 4) if total else None,
        "confusion_top": [
            {"manual_color": manual, "predicted_color": predicted, "count": count}
            for (manual, predicted), count in confusion.most_common()
        ],
        "per_group": per_group,
    }


def _long_running_memory_report() -> dict[str, Any]:
    path = settings.data_dir / "evals" / "runtime" / "c1_runtime_memory.json"
    data = _read_json(path)
    if not data:
        return {
            "source": str(path),
            "status": "not_measured",
            "note": "Run scripts/monitor_c1_runtime.py for a continuous C1 process memory sample.",
            "passes_memory_stability": False,
        }
    return {
        "source": str(path),
        "status": "measured",
        "generated_at": data.get("generated_at"),
        "duration_sec": data.get("duration_sec"),
        "sample_count": data.get("sample_count"),
        "rss_initial_mb": data.get("rss_initial_mb"),
        "rss_final_mb": data.get("rss_final_mb"),
        "rss_max_mb": data.get("rss_max_mb"),
        "rss_growth_mb": data.get("rss_growth_mb"),
        "rss_slope_mb_per_hour": data.get("rss_slope_mb_per_hour"),
        "gpu_memory_initial_mb": data.get("gpu_memory_initial_mb"),
        "gpu_memory_final_mb": data.get("gpu_memory_final_mb"),
        "gpu_memory_max_mb": data.get("gpu_memory_max_mb"),
        "health_error_count": data.get("health_error_count"),
        "thresholds": data.get("thresholds"),
        "passes_memory_stability": bool(data.get("passes_memory_stability")),
    }


def _count_existing_ids(conn: sqlite3.Connection, table: str, column: str, ids: set[str]) -> int:
    if not ids:
        return 0
    values = sorted(ids)
    total = 0
    for index in range(0, len(values), 500):
        chunk = values[index : index + 500]
        placeholders = ",".join("?" for _ in chunk)
        total += int(
            conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE {column} IN ({placeholders})",
                chunk,
            ).fetchone()[0]
        )
    return total


def _manual_label_replayability(db_path: Path) -> list[dict[str, Any]]:
    label_specs = [
        ("manual_outfit_labels", settings.data_dir / "evals" / "manual_outfit_labels" / "outfit_labels.json"),
        (
            "manual_event_outfit_groups",
            settings.data_dir / "evals" / "manual_event_outfit_groups" / "event_outfit_groups.json",
        ),
        (
            "manual_clothing_labels",
            settings.data_dir / "evals" / "manual_clothing_labels" / "person_clothing_labels.json",
        ),
        (
            "manual_appearance_session_labels",
            settings.data_dir / "evals" / "manual_appearance_session_labels" / "appearance_session_labels.json",
        ),
    ]
    reports = []
    with _connect(db_path) as conn:
        for name, path in label_specs:
            data = _read_json(path)
            labels = data.get("labels") if isinstance(data.get("labels"), dict) else {}
            person_ids: set[str] = set()
            event_ids: set[str] = set()
            observation_ids: set[str] = set()
            snapshot_count = 0
            snapshot_available = 0
            for label in labels.values():
                if not isinstance(label, dict):
                    continue
                if label.get("person_id"):
                    person_ids.add(str(label["person_id"]))
                for event_id in label.get("sample_event_ids") or []:
                    if isinstance(event_id, str) and event_id:
                        event_ids.add(event_id)
                for observation_id in label.get("sample_observation_ids") or []:
                    if isinstance(observation_id, str) and observation_id:
                        observation_ids.add(observation_id)
                for key in ("manual_split_assignments", "manual_assignments"):
                    for assignment in label.get(key) or []:
                        if not isinstance(assignment, dict):
                            continue
                        if assignment.get("event_id"):
                            event_ids.add(str(assignment["event_id"]))
                        if assignment.get("observation_id"):
                            observation_ids.add(str(assignment["observation_id"]))
                for snapshot in label.get("sample_snapshots") or []:
                    if not isinstance(snapshot, dict):
                        continue
                    snapshot_count += 1
                    if snapshot.get("snapshot_available"):
                        snapshot_available += 1

            person_matches = _count_existing_ids(conn, "persons", "person_id", person_ids)
            event_matches = _count_existing_ids(conn, "events", "event_id", event_ids)
            observation_matches = _count_existing_ids(
                conn,
                "person_observations",
                "observation_id",
                observation_ids,
            )
            db_id_replayable = (
                (not person_ids or person_matches == len(person_ids))
                and (not event_ids or event_matches == len(event_ids))
                and (not observation_ids or observation_matches == len(observation_ids))
            )
            snapshot_replayable = bool(snapshot_count and snapshot_available == snapshot_count)
            reports.append(
                {
                    "name": name,
                    "path": str(path),
                    "labels": len(labels),
                    "person_ids": len(person_ids),
                    "person_matches": person_matches,
                    "event_ids": len(event_ids),
                    "event_matches": event_matches,
                    "observation_ids": len(observation_ids),
                    "observation_matches": observation_matches,
                    "snapshot_count": snapshot_count,
                    "snapshot_available": snapshot_available,
                    "db_id_replayable": db_id_replayable,
                    "snapshot_replayable": snapshot_replayable,
                    "replayable": db_id_replayable or snapshot_replayable,
                }
            )
    return reports


def _compare_counts(baseline: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    keys = sorted(set(baseline) | set(current))
    return {
        key: {
            "baseline": baseline.get(key),
            "current": current.get(key),
            "delta": current.get(key) - baseline.get(key)
            if isinstance(current.get(key), (int, float)) and isinstance(baseline.get(key), (int, float))
            else None,
        }
        for key in keys
    }


def evaluate(current_db: Path, baseline_db: Path) -> dict[str, Any]:
    current_counts = _db_counts(current_db)
    baseline_counts = _db_counts(baseline_db) if baseline_db.exists() else {}
    person_merge = _person_merge_report(current_db)
    outfit_grouping = _outfit_grouping_report()
    upper_color = _upper_color_reports()
    api_processing = _api_processing_metrics(current_db)
    memory = _long_running_memory_report()

    return {
        "schema_version": "c1_target_metrics_v1",
        "generated_at": _now_iso(),
        "targets": TARGETS,
        "databases": {
            "current": str(current_db),
            "baseline": str(baseline_db),
        },
        "db_counts": {
            "baseline": baseline_counts,
            "current": current_counts,
            "comparison": _compare_counts(baseline_counts, current_counts) if baseline_counts else {},
        },
        "camera_event_stats": {
            "baseline": _camera_event_stats(baseline_db) if baseline_db.exists() else [],
            "current": _camera_event_stats(current_db),
        },
        "person_fragmentation": {
            "baseline": _person_fragmentation(baseline_db) if baseline_db.exists() else {},
            "current": _person_fragmentation(current_db),
        },
        "person_aggregation": person_merge,
        "outfit_grouping": outfit_grouping,
        "upper_color": upper_color,
        "api_processing": api_processing,
        "long_running_memory": memory,
        "manual_label_replayability": _manual_label_replayability(current_db),
        "pass_summary": {
            "person_aggregation_pairwise_precision": person_merge["passes_precision_target"],
            "person_aggregation_pairwise_f1": person_merge["passes_f1_target"],
            "outfit_grouping_pairwise_f1": outfit_grouping["passes_f1_target"],
            "outfit_grouping_purity": outfit_grouping["passes_purity_target"],
            "upper_color_outfit_accuracy": upper_color["passes_outfit_accuracy_target"],
            "api_processing_realtime_mean": api_processing["passes_realtime_mean"],
            "api_processing_realtime_all": api_processing["passes_realtime_all"],
            "api_processing_ideal_max": api_processing["passes_ideal_max_processing_sec"],
            "long_running_memory": memory["passes_memory_stability"],
        },
    }


def _print_summary(report: dict[str, Any]) -> None:
    counts = report["db_counts"]["current"]
    baseline = report["db_counts"]["baseline"]
    fragmentation = report.get("person_fragmentation", {}).get("current", {})
    print("C1 target metrics")
    print(f"current_db={report['databases']['current']}")
    print(f"baseline_db={report['databases']['baseline']}")
    if baseline:
        print(
            "counts: "
            f"persons {baseline.get('persons')} -> {counts.get('persons')}, "
            f"person_faces {baseline.get('person_faces')} -> {counts.get('person_faces')}, "
            f"identified_events {baseline.get('identified_events')} -> {counts.get('identified_events')}, "
            f"upper_unknown_event_rate {baseline.get('upper_unknown_event_rate')} -> {counts.get('upper_unknown_event_rate')}"
        )
    if fragmentation:
        print(
            "person_fragmentation: "
            f"stable_ge10={fragmentation.get('stable_persons_ge10')}, "
            f"candidate_lt10={int(fragmentation.get('persons') or 0) - int(fragmentation.get('stable_persons_ge10') or 0)}, "
            f"small_le3={fragmentation.get('small_persons_le3')}, "
            f"histogram={fragmentation.get('histogram')}"
        )
    print("pass_summary:")
    for key, value in report["pass_summary"].items():
        print(f"  {key}: {value}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate C1 against the target metric checklist.")
    parser.add_argument("--db", type=Path, default=settings.db_path)
    parser.add_argument("--baseline-db", type=Path, default=DEFAULT_BASELINE_DB)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    report = evaluate(args.db.resolve(), args.baseline_db.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    _print_summary(report)
    print(f"wrote={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
