from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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


def _rss_mb(pid: int | None = None) -> float | None:
    pid = os.getpid() if pid is None else int(pid)
    status_path = Path(f"/proc/{pid}/status")
    try:
        for line in status_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("VmRSS:"):
                parts = line.split()
                return round(float(parts[1]) / 1024.0, 3)
    except OSError:
        return None
    return None


def _gpu_compute_apps() -> list[dict[str, Any]]:
    cmd = [
        "nvidia-smi",
        "--query-compute-apps=pid,process_name,used_memory",
        "--format=csv,noheader,nounits",
    ]
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=10)
    except Exception:
        return []

    apps = []
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 3:
            continue
        try:
            pid = int(parts[0])
        except ValueError:
            continue
        try:
            used_memory_mb = int(parts[2])
        except ValueError:
            used_memory_mb = None
        apps.append(
            {
                "pid": pid,
                "process_name": parts[1],
                "used_memory_mb": used_memory_mb,
            }
        )
    return apps


def _gpu_memory_for_pid(apps: list[dict[str, Any]], pid: int | None = None) -> int | None:
    pid = os.getpid() if pid is None else int(pid)
    values = [
        int(app["used_memory_mb"])
        for app in apps
        if app.get("pid") == pid and app.get("used_memory_mb") is not None
    ]
    return sum(values) if values else None


def _process_metrics() -> dict[str, Any]:
    gpu_apps = _gpu_compute_apps()
    return {
        "pid": os.getpid(),
        "rss_mb": _rss_mb(),
        "this_process_gpu_mb": _gpu_memory_for_pid(gpu_apps),
        "gpu_compute_apps": gpu_apps,
    }


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


def _parse_video_ids(raw: str | None, fallback: str) -> list[str]:
    if not raw:
        return [fallback]
    video_ids = [item.strip() for item in raw.split(",") if item.strip()]
    if not video_ids:
        raise ValueError("--video-ids must contain at least one video id")
    return video_ids


def _video_summary(video: dict[str, Any]) -> dict[str, Any]:
    duration = _video_duration_sec(video.get("path"))
    return {
        "video_id": video.get("video_id"),
        "filename": video.get("filename"),
        "camera_id": video.get("camera_id"),
        "video_path": video.get("path"),
        "duration_sec": round(duration, 6) if duration else None,
    }


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


def _prepare_route_videos(
    db_path: Path,
    source_videos: list[dict[str, Any]],
    route_count: int,
) -> list[dict[str, Any]]:
    route_count = max(1, int(route_count))
    if not source_videos:
        raise ValueError("at least one source video is required")

    route_specs = []
    conn = sqlite3.connect(db_path)
    try:
        ts = _utc_now()
        for index in range(route_count):
            source_video = source_videos[index % len(source_videos)]
            video_id = (
                str(source_video["video_id"])
                if index < len(source_videos)
                else f"{source_video['video_id']}_bench_route_{index + 1:02d}"
            )
            if index >= len(source_videos):
                camera_id = f"{source_video.get('camera_id') or 'camera'}_bench_route_{index + 1:02d}"
                conn.execute(
                    """
                    INSERT OR REPLACE INTO cameras(camera_id, name, location, lat, lng, created_at, updated_at)
                    VALUES (?, ?, NULL, NULL, NULL, ?, ?)
                    """,
                    (camera_id, camera_id, ts, ts),
                )
                conn.execute(
                    """
                    INSERT OR REPLACE INTO videos(
                        video_id, filename, camera_id, recorded_at, path, status,
                        frame_interval_sec, created_at, updated_at,
                        processing_started_at, processing_finished_at,
                        processing_duration_sec, processing_error
                    )
                    VALUES (?, ?, ?, ?, ?, 'uploaded', ?, ?, ?, NULL, NULL, NULL, NULL)
                    """,
                    (
                        video_id,
                        source_video.get("filename") or f"route_{index + 1}.mp4",
                        camera_id,
                        source_video.get("recorded_at"),
                        source_video["path"],
                        source_video.get("frame_interval_sec"),
                        ts,
                        ts,
                    ),
                )
            source_duration = _video_duration_sec(source_video.get("path"))
            route_specs.append(
                {
                    "route_index": index + 1,
                    "video_id": video_id,
                    "source_video_id": source_video.get("video_id"),
                    "source_filename": source_video.get("filename"),
                    "source_camera_id": source_video.get("camera_id"),
                    "source_duration_sec": round(source_duration, 6) if source_duration else None,
                }
            )
        conn.commit()
    finally:
        conn.close()
    return route_specs


def _set_temp_data_dir(data_dir: Path) -> None:
    settings.data_dir = data_dir
    settings.uploads_dir = data_dir / "uploads"
    settings.video_uploads_dir = settings.uploads_dir / "videos"
    settings.query_uploads_dir = settings.uploads_dir / "query_images"
    settings.frames_dir = data_dir / "frames"
    settings.db_path = data_dir / "campusvision.sqlite3"


def _capture_data_dir_settings() -> dict[str, Path]:
    return {
        "data_dir": settings.data_dir,
        "uploads_dir": settings.uploads_dir,
        "video_uploads_dir": settings.video_uploads_dir,
        "query_uploads_dir": settings.query_uploads_dir,
        "frames_dir": settings.frames_dir,
        "db_path": settings.db_path,
    }


def _restore_data_dir_settings(snapshot: dict[str, Path]) -> None:
    settings.data_dir = snapshot["data_dir"]
    settings.uploads_dir = snapshot["uploads_dir"]
    settings.video_uploads_dir = snapshot["video_uploads_dir"]
    settings.query_uploads_dir = snapshot["query_uploads_dir"]
    settings.frames_dir = snapshot["frames_dir"]
    settings.db_path = snapshot["db_path"]


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
        "memory_cleanup": result.get("memory_cleanup"),
        "performance_profile": result.get("performance_profile"),
    }


def _enrich_route_result(route_spec: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    route_processing_sec = float(result.get("processing_duration_sec") or result.get("elapsed_sec") or 0.0)
    duration = route_spec.get("source_duration_sec")
    realtime_factor = (
        round(route_processing_sec / float(duration), 6)
        if duration and float(duration) > 0.0
        else None
    )
    return {
        **route_spec,
        **result,
        "route_processing_sec": round(route_processing_sec, 6),
        "route_realtime_factor": realtime_factor,
    }


def _run_concurrent(
    route_specs: list[dict[str, Any]],
    frame_interval_sec: float | None,
    *,
    collect_profile: bool,
) -> dict[str, Any]:
    # Prewarm shared model singletons before worker threads start, otherwise
    # first-touch concurrent runs can race and duplicate expensive model init.
    from app.vision.body_detector import get_body_detector
    from app.vision.face_engine import get_face_engine

    get_face_engine()
    get_body_detector()

    started = time.perf_counter()
    route_results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=len(route_specs)) as executor:
        futures = {
            executor.submit(
                _run_once,
                str(route_spec["video_id"]),
                frame_interval_sec,
                collect_profile=collect_profile,
            ): route_spec
            for route_spec in route_specs
        }
        for future in as_completed(futures):
            route_spec = futures[future]
            try:
                route_results.append(_enrich_route_result(route_spec, future.result()))
            except Exception as exc:
                route_results.append(
                    {
                        **route_spec,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
    elapsed = time.perf_counter() - started
    route_results.sort(key=lambda item: int(item.get("route_index") or 0))
    route_realtime_values = [
        float(item["route_realtime_factor"])
        for item in route_results
        if item.get("route_realtime_factor") is not None and not item.get("error")
    ]
    return {
        "elapsed_sec": round(elapsed, 6),
        "route_count": len(route_specs),
        "routes": route_results,
        "failed_routes": sum(1 for item in route_results if item.get("error")),
        "mean_route_processing_sec": round(
            mean(
                float(item.get("processing_duration_sec") or item.get("elapsed_sec") or 0.0)
                for item in route_results
                if not item.get("error")
            ),
            6,
        )
        if any(not item.get("error") for item in route_results)
        else None,
        "mean_route_realtime_factor": round(mean(route_realtime_values), 6)
        if route_realtime_values
        else None,
        "max_route_realtime_factor": round(max(route_realtime_values), 6)
        if route_realtime_values
        else None,
        "passes_realtime_all_routes": (
            bool(route_realtime_values)
            and len(route_realtime_values) == len(route_specs)
            and max(route_realtime_values) <= 1.0
        ),
    }


def run_benchmark(
    *,
    video_id: str,
    video_ids: list[str] | None = None,
    frame_interval_sec: float | None,
    warmup_runs: int,
    runs: int,
    output: Path,
    collect_profile: bool,
    concurrent_routes: int,
) -> dict[str, Any]:
    data_settings_snapshot = _capture_data_dir_settings()
    source_db = settings.db_path
    source_data_dir = settings.data_dir
    source_video_ids = video_ids or [video_id]
    source_videos = [_fetch_video(source_db, item) for item in source_video_ids]
    video = source_videos[0]
    source_summaries = [_video_summary(item) for item in source_videos]
    source_durations = [
        float(item["duration_sec"])
        for item in source_summaries
        if item.get("duration_sec") is not None
    ]
    video_duration = source_durations[0] if source_durations else None
    benchmark_duration = max(source_durations) if source_durations else video_duration

    bench_root = (
        source_data_dir
        / "evals"
        / "runtime"
        / f"api_processing_benchmark_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    )
    bench_root.mkdir(parents=True, exist_ok=True)
    source_copy = bench_root / "source.sqlite3"
    shutil.copyfile(source_db, source_copy)

    try:
        _set_temp_data_dir(bench_root)
        settings.ensure_dirs()

        warmup_results = []
        measured_results = []
        for index in range(max(0, warmup_runs) + max(1, runs)):
            run_type = "warmup" if index < warmup_runs else "measured"
            run_index = index if run_type == "warmup" else index - warmup_runs
            run_started_at = _utc_now()
            run_metrics_before = _process_metrics()
            shutil.copyfile(source_copy, settings.db_path)
            route_specs = _prepare_route_videos(settings.db_path, source_videos, concurrent_routes)
            for route_spec in route_specs:
                _clean_video_records(settings.db_path, str(route_spec["video_id"]))
            if concurrent_routes <= 1:
                result = _run_once(
                    str(route_specs[0]["video_id"]),
                    frame_interval_sec,
                    collect_profile=collect_profile,
                )
                result = _enrich_route_result(route_specs[0], result)
            else:
                result = _run_concurrent(
                    route_specs,
                    frame_interval_sec,
                    collect_profile=collect_profile,
                )
            if (settings.event_persistence_mode or "sync").strip().lower() == "async":
                from app.services import event_build_queue

                event_build_queue.wait_for_idle(timeout=600.0)
            result.update(
                {
                    "run_index": run_index,
                    "run_type": run_type,
                    "started_at": run_started_at,
                    "finished_at": _utc_now(),
                    "process_metrics_before": run_metrics_before,
                    "process_metrics_after": _process_metrics(),
                }
            )
            if index < warmup_runs:
                warmup_results.append(result)
            else:
                measured_results.append(result)
    finally:
        _restore_data_dir_settings(data_settings_snapshot)

    processing_values = [
        float(item["elapsed_sec"] if concurrent_routes > 1 else item.get("processing_duration_sec") or item["elapsed_sec"])
        for item in measured_results
    ]
    realtime_values = [
        value / benchmark_duration
        for value in processing_values
        if benchmark_duration and benchmark_duration > 0.0
    ]
    route_realtime_values = [
        float(route["route_realtime_factor"])
        for item in measured_results
        for route in (item.get("routes") or [item])
        if isinstance(route, dict)
        and route.get("route_realtime_factor") is not None
        and not route.get("error")
    ]
    measured_rss_values = [
        float(metrics["rss_mb"])
        for item in measured_results
        for metrics in (
            item.get("process_metrics_before") or {},
            item.get("process_metrics_after") or {},
        )
        if metrics.get("rss_mb") is not None
    ]
    measured_gpu_values = [
        int(metrics["this_process_gpu_mb"])
        for item in measured_results
        for metrics in (
            item.get("process_metrics_before") or {},
            item.get("process_metrics_after") or {},
        )
        if metrics.get("this_process_gpu_mb") is not None
    ]
    measured_rss_start = (
        measured_results[0].get("process_metrics_before", {}).get("rss_mb")
        if measured_results
        else None
    )
    measured_rss_end = (
        measured_results[-1].get("process_metrics_after", {}).get("rss_mb")
        if measured_results
        else None
    )
    report = {
        "schema_version": "c1_api_processing_benchmark_v2",
        "generated_at": _utc_now(),
        "source": "clean_temp_db_index_video",
        "temp_data_dir": str(bench_root),
        "video_id": video_id,
        "video_ids": source_video_ids,
        "filename": video.get("filename"),
        "camera_id": video.get("camera_id"),
        "video_path": video.get("path"),
        "video_duration_sec": round(video_duration, 6) if video_duration else None,
        "benchmark_duration_sec": round(benchmark_duration, 6) if benchmark_duration else None,
        "source_videos": source_summaries,
        "frame_interval_sec": frame_interval_sec,
        "collect_profile": collect_profile,
        "concurrent_routes": max(1, int(concurrent_routes)),
        "warmup_runs": warmup_results,
        "measured_runs": measured_results,
        "mean_processing_sec": round(mean(processing_values), 6) if processing_values else None,
        "max_processing_sec": round(max(processing_values), 6) if processing_values else None,
        "mean_realtime_factor": round(mean(realtime_values), 6) if realtime_values else None,
        "max_realtime_factor": round(max(realtime_values), 6) if realtime_values else None,
        "mean_wall_realtime_factor": round(mean(realtime_values), 6) if realtime_values else None,
        "max_wall_realtime_factor": round(max(realtime_values), 6) if realtime_values else None,
        "mean_route_realtime_factor": round(mean(route_realtime_values), 6)
        if route_realtime_values
        else None,
        "max_route_realtime_factor": round(max(route_realtime_values), 6)
        if route_realtime_values
        else None,
        "passes_realtime_all_routes": (
            bool(route_realtime_values)
            and len(route_realtime_values)
            == max(1, int(concurrent_routes)) * len(measured_results)
            and max(route_realtime_values) <= 1.0
        ),
        "mean_effective_realtime_streams": (
            round((max(1, int(concurrent_routes)) / mean(realtime_values)), 6)
            if realtime_values
            else None
        ),
        "measured_rss_start_mb": measured_rss_start,
        "measured_rss_end_mb": measured_rss_end,
        "measured_rss_min_mb": round(min(measured_rss_values), 3)
        if measured_rss_values
        else None,
        "measured_rss_max_mb": round(max(measured_rss_values), 3)
        if measured_rss_values
        else None,
        "measured_rss_delta_mb": (
            round(float(measured_rss_end) - float(measured_rss_start), 3)
            if measured_rss_start is not None and measured_rss_end is not None
            else None
        ),
        "measured_gpu_min_mb": min(measured_gpu_values) if measured_gpu_values else None,
        "measured_gpu_max_mb": max(measured_gpu_values) if measured_gpu_values else None,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark current C1 video API processing on a clean temp DB.")
    parser.add_argument("--video-id", default=DEFAULT_VIDEO_ID)
    parser.add_argument(
        "--video-ids",
        default=None,
        help="Comma-separated source video IDs. When set, routes use these sources in order and cycle if needed.",
    )
    parser.add_argument("--frame-interval-sec", type=float, default=1.0)
    parser.add_argument("--warmup-runs", type=int, default=1)
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--collect-profile", action="store_true")
    parser.add_argument("--concurrent-routes", type=int, default=1)
    args = parser.parse_args()
    video_ids = _parse_video_ids(args.video_ids, args.video_id) if args.video_ids else None
    report = run_benchmark(
        video_id=args.video_id,
        video_ids=video_ids,
        frame_interval_sec=args.frame_interval_sec,
        warmup_runs=args.warmup_runs,
        runs=args.runs,
        output=args.output,
        collect_profile=args.collect_profile,
        concurrent_routes=args.concurrent_routes,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
