from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import settings
from scripts.benchmark_api_processing import run_benchmark


DEFAULT_VIDEO_IDS = [
    "e378f9e55a10465994feb315f7d6a80b",
    "5f4a2fbd4fcc4cfe8f584566d6ff97d5",
    "d938f136b73643b7bfbdf1ec7c333ed1",
    "3f801186e1ba45b6b5ba0f2b7aec86e0",
    "43e841af00cd4259a80310d038a84a19",
    "df683997ad2f4968b5f957e514eff0c1",
]
DEFAULT_OUTPUT = settings.data_dir / "evals" / "runtime" / "c1_realtime_mixed6_stability.json"


def _utc_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _parse_video_ids(raw: str | None) -> list[str]:
    if not raw:
        return list(DEFAULT_VIDEO_IDS)
    video_ids = [item.strip() for item in raw.split(",") if item.strip()]
    if not video_ids:
        raise ValueError("--video-ids must contain at least one video id")
    return video_ids


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


def _gpu_memory_for_pid(apps: list[dict[str, Any]], pid: int) -> int | None:
    values = [
        int(app["used_memory_mb"])
        for app in apps
        if app.get("pid") == pid and app.get("used_memory_mb") is not None
    ]
    return sum(values) if values else None


def _settings_snapshot() -> dict[str, Any]:
    keys = [
        "insightface_det_size",
        "insightface_engine_pool_size",
        "insightface_max_concurrent_inferences",
        "event_persistence_mode",
        "event_build_worker_count",
        "serialize_live_analysis",
        "body_detection_backend",
        "body_detection_frame_stride",
        "clothing_analysis_frame_stride",
        "upper_color_backend",
        "clothing_model_version",
        "data_dir",
        "db_path",
    ]
    return {key: str(getattr(settings, key)) for key in keys}


def _cycle_summary(
    *,
    cycle_index: int,
    cycle_report: dict[str, Any],
    output_path: Path,
    started_at: str,
    finished_at: str,
    wall_sec: float,
    rss_before_mb: float | None,
    rss_after_mb: float | None,
    gpu_before: list[dict[str, Any]],
    gpu_after: list[dict[str, Any]],
) -> dict[str, Any]:
    pid = os.getpid()
    return {
        "cycle_index": cycle_index,
        "started_at": started_at,
        "finished_at": finished_at,
        "wall_sec": round(wall_sec, 6),
        "report_path": str(output_path),
        "failed_routes": sum(int(item.get("failed_routes") or 0) for item in cycle_report.get("measured_runs") or []),
        "max_processing_sec": cycle_report.get("max_processing_sec"),
        "mean_processing_sec": cycle_report.get("mean_processing_sec"),
        "max_wall_realtime_factor": cycle_report.get("max_wall_realtime_factor"),
        "mean_wall_realtime_factor": cycle_report.get("mean_wall_realtime_factor"),
        "max_route_realtime_factor": cycle_report.get("max_route_realtime_factor"),
        "mean_route_realtime_factor": cycle_report.get("mean_route_realtime_factor"),
        "passes_realtime_all_routes": cycle_report.get("passes_realtime_all_routes"),
        "rss_before_mb": rss_before_mb,
        "rss_after_mb": rss_after_mb,
        "rss_delta_mb": round(rss_after_mb - rss_before_mb, 3)
        if rss_before_mb is not None and rss_after_mb is not None
        else None,
        "this_process_gpu_before_mb": _gpu_memory_for_pid(gpu_before, pid),
        "this_process_gpu_after_mb": _gpu_memory_for_pid(gpu_after, pid),
        "gpu_compute_apps_after": gpu_after,
    }


def _aggregate(cycles: list[dict[str, Any]]) -> dict[str, Any]:
    processing = [
        float(item["max_processing_sec"])
        for item in cycles
        if item.get("max_processing_sec") is not None
    ]
    wall_factors = [
        float(item["max_wall_realtime_factor"])
        for item in cycles
        if item.get("max_wall_realtime_factor") is not None
    ]
    route_factors = [
        float(item["max_route_realtime_factor"])
        for item in cycles
        if item.get("max_route_realtime_factor") is not None
    ]
    rss_values = [
        float(item["rss_after_mb"])
        for item in cycles
        if item.get("rss_after_mb") is not None
    ]
    gpu_values = [
        int(item["this_process_gpu_after_mb"])
        for item in cycles
        if item.get("this_process_gpu_after_mb") is not None
    ]
    return {
        "cycles": len(cycles),
        "failed_cycles": sum(1 for item in cycles if int(item.get("failed_routes") or 0) > 0),
        "failed_routes": sum(int(item.get("failed_routes") or 0) for item in cycles),
        "passes_realtime_all_cycles": bool(cycles)
        and all(bool(item.get("passes_realtime_all_routes")) for item in cycles),
        "max_processing_sec": round(max(processing), 6) if processing else None,
        "mean_cycle_max_processing_sec": round(mean(processing), 6) if processing else None,
        "max_wall_realtime_factor": round(max(wall_factors), 6) if wall_factors else None,
        "mean_cycle_max_wall_realtime_factor": round(mean(wall_factors), 6) if wall_factors else None,
        "max_route_realtime_factor": round(max(route_factors), 6) if route_factors else None,
        "mean_cycle_max_route_realtime_factor": round(mean(route_factors), 6) if route_factors else None,
        "rss_start_mb": rss_values[0] if rss_values else None,
        "rss_end_mb": rss_values[-1] if rss_values else None,
        "rss_min_mb": min(rss_values) if rss_values else None,
        "rss_max_mb": max(rss_values) if rss_values else None,
        "rss_delta_mb": round(rss_values[-1] - rss_values[0], 3) if len(rss_values) >= 2 else None,
        "this_process_gpu_min_mb": min(gpu_values) if gpu_values else None,
        "this_process_gpu_max_mb": max(gpu_values) if gpu_values else None,
    }


def _write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def run_stability(
    *,
    video_ids: list[str],
    frame_interval_sec: float,
    concurrent_routes: int,
    cycles: int | None,
    duration_sec: float | None,
    warmup_runs: int,
    sleep_sec: float,
    output: Path,
) -> dict[str, Any]:
    started_at = _utc_now()
    started = time.perf_counter()
    output.parent.mkdir(parents=True, exist_ok=True)
    cycle_dir = output.with_suffix("")
    cycle_dir.mkdir(parents=True, exist_ok=True)

    report: dict[str, Any] = {
        "schema_version": "c1_realtime_stability_v1",
        "generated_at": started_at,
        "finished_at": None,
        "video_ids": video_ids,
        "frame_interval_sec": frame_interval_sec,
        "concurrent_routes": concurrent_routes,
        "requested_cycles": cycles,
        "requested_duration_sec": duration_sec,
        "settings": _settings_snapshot(),
        "cycles": [],
        "summary": {},
    }
    _write_report(output, report)

    cycle_index = 0
    while True:
        if cycles is not None and cycle_index >= cycles:
            break
        elapsed = time.perf_counter() - started
        if duration_sec is not None and cycle_index > 0 and elapsed >= duration_sec:
            break

        cycle_index += 1
        cycle_started_at = _utc_now()
        cycle_started = time.perf_counter()
        rss_before = _rss_mb()
        gpu_before = _gpu_compute_apps()
        cycle_output = cycle_dir / f"cycle_{cycle_index:03d}.json"

        cycle_report = run_benchmark(
            video_id=video_ids[0],
            video_ids=video_ids,
            frame_interval_sec=frame_interval_sec,
            warmup_runs=warmup_runs if cycle_index == 1 else 0,
            runs=1,
            output=cycle_output,
            collect_profile=False,
            concurrent_routes=concurrent_routes,
        )

        cycle_finished_at = _utc_now()
        cycle_wall = time.perf_counter() - cycle_started
        rss_after = _rss_mb()
        gpu_after = _gpu_compute_apps()
        report["cycles"].append(
            _cycle_summary(
                cycle_index=cycle_index,
                cycle_report=cycle_report,
                output_path=cycle_output,
                started_at=cycle_started_at,
                finished_at=cycle_finished_at,
                wall_sec=cycle_wall,
                rss_before_mb=rss_before,
                rss_after_mb=rss_after,
                gpu_before=gpu_before,
                gpu_after=gpu_after,
            )
        )
        report["summary"] = _aggregate(report["cycles"])
        report["finished_at"] = cycle_finished_at
        report["elapsed_sec"] = round(time.perf_counter() - started, 6)
        _write_report(output, report)

        if sleep_sec > 0.0:
            time.sleep(sleep_sec)

    report["finished_at"] = _utc_now()
    report["elapsed_sec"] = round(time.perf_counter() - started, 6)
    report["summary"] = _aggregate(report["cycles"])
    _write_report(output, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run repeated mixed-source C1 realtime stability benchmarks.")
    parser.add_argument("--video-ids", default=",".join(DEFAULT_VIDEO_IDS))
    parser.add_argument("--frame-interval-sec", type=float, default=1.0)
    parser.add_argument("--concurrent-routes", type=int, default=6)
    parser.add_argument("--cycles", type=int, default=10)
    parser.add_argument("--duration-sec", type=float, default=None)
    parser.add_argument("--warmup-runs", type=int, default=1)
    parser.add_argument("--sleep-sec", type=float, default=0.0)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    report = run_stability(
        video_ids=_parse_video_ids(args.video_ids),
        frame_interval_sec=args.frame_interval_sec,
        concurrent_routes=args.concurrent_routes,
        cycles=args.cycles if args.cycles and args.cycles > 0 else None,
        duration_sec=args.duration_sec if args.duration_sec and args.duration_sec > 0.0 else None,
        warmup_runs=max(0, int(args.warmup_runs)),
        sleep_sec=max(0.0, float(args.sleep_sec)),
        output=args.output,
    )
    print(json.dumps({"summary": report["summary"], "output": str(args.output)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
