from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import settings


DEFAULT_VIDEO_ID = "43e841af00cd4259a80310d038a84a19"
DEFAULT_OUTPUT = settings.data_dir / "evals" / "runtime" / "c1_api_processing_benchmark.json"


def _utc_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


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


def _fetch_video(db_path: Path, video_id: str) -> dict[str, Any]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM videos WHERE video_id = ?", (video_id,)).fetchone()
    finally:
        conn.close()
    if row is None:
        raise KeyError(f"video_id not found in source db: {video_id}")
    return dict(row)


def _clean_video_records(db_path: Path, video_id: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        face_ids = [
            row[0]
            for row in conn.execute(
                "SELECT face_id FROM face_records WHERE video_id = ?",
                (video_id,),
            ).fetchall()
        ]
        if face_ids:
            conn.executemany("DELETE FROM person_faces WHERE face_id = ?", [(face_id,) for face_id in face_ids])
        conn.execute("DELETE FROM face_records WHERE video_id = ?", (video_id,))
        conn.execute("DELETE FROM person_observations WHERE video_id = ?", (video_id,))
        conn.execute("DELETE FROM events WHERE video_id = ?", (video_id,))
        conn.execute(
            """
            UPDATE videos SET
                status = 'uploaded',
                processing_started_at = NULL,
                processing_finished_at = NULL,
                processing_duration_sec = NULL,
                processing_error = NULL
            WHERE video_id = ?
            """,
            (video_id,),
        )
        conn.commit()
    finally:
        conn.close()


def _set_temp_data_dir(data_dir: Path) -> None:
    settings.data_dir = data_dir
    settings.uploads_dir = data_dir / "uploads"
    settings.video_uploads_dir = settings.uploads_dir / "videos"
    settings.query_uploads_dir = settings.uploads_dir / "query_images"
    settings.frames_dir = data_dir / "frames"
    settings.db_path = data_dir / "campusvision.sqlite3"


def _run_once(video_id: str, frame_interval_sec: float | None, *, collect_profile: bool) -> dict[str, Any]:
    from app.storage import db
    from app.services import video_service

    db.init_db()
    started = time.perf_counter()
    result = video_service.index_video(
        video_id,
        frame_interval_sec=frame_interval_sec,
        collect_profile=collect_profile,
    )
    elapsed = time.perf_counter() - started
    video = db.get_video(video_id) or {}
    return {
        "elapsed_sec": round(elapsed, 6),
        "processing_duration_sec": (
            round(float(video.get("processing_duration_sec")), 6)
            if video.get("processing_duration_sec") is not None
            else None
        ),
        "indexed_faces": result.get("indexed_faces"),
        "indexed_observations": result.get("indexed_observations"),
        "detected_bodies": result.get("detected_bodies"),
        "source_observations": (result.get("event_result") or {}).get("source_observations"),
        "events": (result.get("event_result") or {}).get("events"),
        "performance_profile": result.get("performance_profile"),
    }


def run_benchmark(
    *,
    video_id: str,
    frame_interval_sec: float | None,
    warmup_runs: int,
    runs: int,
    output: Path,
    collect_profile: bool,
) -> dict[str, Any]:
    source_db = settings.db_path
    source_data_dir = settings.data_dir
    video = _fetch_video(source_db, video_id)
    video_duration = _video_duration_sec(video.get("path"))

    bench_root = (
        source_data_dir
        / "evals"
        / "runtime"
        / f"api_processing_benchmark_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    )
    bench_root.mkdir(parents=True, exist_ok=True)
    source_copy = bench_root / "source.sqlite3"
    shutil.copyfile(source_db, source_copy)

    _set_temp_data_dir(bench_root)
    settings.ensure_dirs()

    warmup_results = []
    measured_results = []
    for index in range(max(0, warmup_runs) + max(1, runs)):
        shutil.copyfile(source_copy, settings.db_path)
        _clean_video_records(settings.db_path, video_id)
        result = _run_once(video_id, frame_interval_sec, collect_profile=collect_profile)
        if index < warmup_runs:
            warmup_results.append(result)
        else:
            measured_results.append(result)

    processing_values = [
        float(item.get("processing_duration_sec") or item["elapsed_sec"])
        for item in measured_results
    ]
    realtime_values = [
        value / video_duration
        for value in processing_values
        if video_duration and video_duration > 0.0
    ]
    report = {
        "schema_version": "c1_api_processing_benchmark_v1",
        "generated_at": _utc_now(),
        "source": "clean_temp_db_index_video",
        "temp_data_dir": str(bench_root),
        "video_id": video_id,
        "filename": video.get("filename"),
        "camera_id": video.get("camera_id"),
        "video_path": video.get("path"),
        "video_duration_sec": round(video_duration, 6) if video_duration else None,
        "frame_interval_sec": frame_interval_sec,
        "collect_profile": collect_profile,
        "warmup_runs": warmup_results,
        "measured_runs": measured_results,
        "mean_processing_sec": round(mean(processing_values), 6) if processing_values else None,
        "max_processing_sec": round(max(processing_values), 6) if processing_values else None,
        "mean_realtime_factor": round(mean(realtime_values), 6) if realtime_values else None,
        "max_realtime_factor": round(max(realtime_values), 6) if realtime_values else None,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark current C1 video API processing on a clean temp DB.")
    parser.add_argument("--video-id", default=DEFAULT_VIDEO_ID)
    parser.add_argument("--frame-interval-sec", type=float, default=1.0)
    parser.add_argument("--warmup-runs", type=int, default=1)
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--collect-profile", action="store_true")
    args = parser.parse_args()
    report = run_benchmark(
        video_id=args.video_id,
        frame_interval_sec=args.frame_interval_sec,
        warmup_runs=args.warmup_runs,
        runs=args.runs,
        output=args.output,
        collect_profile=args.collect_profile,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
