from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

import sys

sys.path.insert(0, str(ROOT))

from app.core.config import settings  # noqa: E402


DEFAULT_BASELINE_DB = (
    settings.data_dir
    / "evals"
    / "database_snapshots"
    / "campusvision_eval_baseline_20260623_pre_full_api_rerun.sqlite3"
)
DEFAULT_OUTPUT = settings.data_dir / "evals" / "target_metrics" / "c1_target_metrics.json"

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
        rows = conn.execute(
            """
            SELECT video_id, filename, camera_id, path, created_at, updated_at
            FROM videos
            WHERE status = 'indexed'
            ORDER BY created_at
            """
        ).fetchall()

    videos = []
    for row in rows:
        created = _parse_datetime(row["created_at"])
        updated = _parse_datetime(row["updated_at"])
        processing_sec = (updated - created).total_seconds() if created and updated else None
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
    return {
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
            }
            for item in slower_than_ideal
        ],
        "per_video": videos,
    }


def _person_merge_report() -> dict[str, Any]:
    path = settings.data_dir / "evals" / "person_merge_scorer" / "person_merge_scorer_eval.json"
    data = _read_json(path)
    metrics = data.get("metrics") if isinstance(data.get("metrics"), dict) else {}
    holdout = metrics.get("holdout") if isinstance(metrics.get("holdout"), dict) else {}
    manual = metrics.get("manual_calibration") if isinstance(metrics.get("manual_calibration"), dict) else {}
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
        "passes_precision_target": (
            holdout.get("precision") is not None
            and float(holdout["precision"]) >= TARGETS["person_aggregation_pairwise_precision"]
        ),
        "passes_f1_target": (
            holdout.get("f1") is not None
            and float(holdout["f1"]) >= TARGETS["person_aggregation_pairwise_f1"]
        ),
        "caveat": "Limited calibration/holdout report; not a full identity ground-truth evaluation.",
    }


def _outfit_grouping_report() -> dict[str, Any]:
    path = settings.data_dir / "evals" / "manual_event_outfit_groups" / "event_outfit_group_eval.json"
    data = _read_json(path)
    pairwise = data.get("pairwise") if isinstance(data.get("pairwise"), dict) else {}
    purity = data.get("purity") if isinstance(data.get("purity"), dict) else {}
    f1 = pairwise.get("f1")
    purity_accuracy = purity.get("purity_accuracy")
    return {
        "source": str(path),
        "grouping_version": data.get("grouping_version"),
        "persons": data.get("persons"),
        "events": data.get("events"),
        "manual_group_count": data.get("manual_group_count"),
        "predicted_group_count": data.get("predicted_group_count"),
        "pairwise_precision": pairwise.get("precision"),
        "pairwise_recall": pairwise.get("recall"),
        "pairwise_f1": f1,
        "macro_f1": pairwise.get("macro_f1"),
        "purity": purity_accuracy,
        "passes_f1_target": f1 is not None and float(f1) >= TARGETS["outfit_grouping_pairwise_f1"],
        "passes_purity_target": (
            purity_accuracy is not None and float(purity_accuracy) >= TARGETS["outfit_grouping_purity"]
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

    outfit_accuracy = prob_group.get("accuracy") or group.get("accuracy")
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
        "selected_outfit_accuracy": outfit_accuracy,
        "passes_outfit_accuracy_target": (
            outfit_accuracy is not None and float(outfit_accuracy) >= TARGETS["upper_color_outfit_accuracy"]
        ),
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
    person_merge = _person_merge_report()
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
