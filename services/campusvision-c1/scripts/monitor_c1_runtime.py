from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]

import sys

sys.path.insert(0, str(ROOT))

from app.core.config import settings  # noqa: E402


DEFAULT_OUTPUT = settings.data_dir / "evals" / "runtime" / "c1_runtime_memory.json"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _pid_for_port(port: int) -> int | None:
    try:
        output = subprocess.check_output(["ss", "-ltnp"], text=True, stderr=subprocess.DEVNULL)
    except Exception:
        return None
    pattern = re.compile(rf":{int(port)}\b.*pid=(\d+)")
    for line in output.splitlines():
        match = pattern.search(line)
        if match:
            return int(match.group(1))
    return None


def _rss_mb(pid: int) -> float | None:
    status_path = Path("/proc") / str(pid) / "status"
    try:
        for line in status_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("VmRSS:"):
                parts = line.split()
                return int(parts[1]) / 1024.0
    except Exception:
        return None
    return None


def _gpu_memory_mb(pid: int) -> float | None:
    try:
        output = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-compute-apps=pid,used_memory",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=3,
        )
    except Exception:
        return None
    total = 0.0
    found = False
    for line in output.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != 2:
            continue
        try:
            row_pid = int(parts[0])
            used_mb = float(parts[1])
        except ValueError:
            continue
        if row_pid == pid:
            total += used_mb
            found = True
    return total if found else 0.0


def _health_latency_ms(url: str, timeout_sec: float) -> tuple[float | None, str | None]:
    started = time.perf_counter()
    try:
        with urlopen(url, timeout=timeout_sec) as response:
            response.read(512)
            if response.status >= 400:
                return None, f"status_{response.status}"
    except URLError as exc:
        return None, str(exc.reason)
    except Exception as exc:
        return None, str(exc)
    return (time.perf_counter() - started) * 1000.0, None


def _linear_slope_per_hour(samples: list[dict[str, Any]], key: str) -> float | None:
    points = [
        (float(sample["elapsed_sec"]), float(sample[key]))
        for sample in samples
        if sample.get(key) is not None
    ]
    if len(points) < 2:
        return None
    mean_x = sum(x for x, _ in points) / len(points)
    mean_y = sum(y for _, y in points) / len(points)
    denominator = sum((x - mean_x) ** 2 for x, _ in points)
    if denominator <= 0.0:
        return None
    slope_per_sec = sum((x - mean_x) * (y - mean_y) for x, y in points) / denominator
    return slope_per_sec * 3600.0


def _summarize(
    *,
    pid: int,
    samples: list[dict[str, Any]],
    min_pass_duration_sec: float,
    max_rss_growth_mb: float,
    max_rss_slope_mb_per_hour: float,
) -> dict[str, Any]:
    rss_values = [float(sample["rss_mb"]) for sample in samples if sample.get("rss_mb") is not None]
    gpu_values = [float(sample["gpu_memory_mb"]) for sample in samples if sample.get("gpu_memory_mb") is not None]
    health_errors = [sample for sample in samples if sample.get("health_error")]
    duration_sec = samples[-1]["elapsed_sec"] - samples[0]["elapsed_sec"] if len(samples) >= 2 else 0.0
    rss_growth_mb = rss_values[-1] - rss_values[0] if len(rss_values) >= 2 else None
    rss_slope = _linear_slope_per_hour(samples, "rss_mb")
    passes = (
        duration_sec >= min_pass_duration_sec
        and rss_growth_mb is not None
        and rss_growth_mb <= max_rss_growth_mb
        and (rss_slope is None or rss_slope <= max_rss_slope_mb_per_hour)
        and not health_errors
    )
    return {
        "schema_version": "c1_runtime_memory_v1",
        "generated_at": _now(),
        "pid": pid,
        "duration_sec": round(duration_sec, 3),
        "sample_count": len(samples),
        "rss_initial_mb": round(rss_values[0], 3) if rss_values else None,
        "rss_final_mb": round(rss_values[-1], 3) if rss_values else None,
        "rss_min_mb": round(min(rss_values), 3) if rss_values else None,
        "rss_max_mb": round(max(rss_values), 3) if rss_values else None,
        "rss_growth_mb": round(rss_growth_mb, 3) if rss_growth_mb is not None else None,
        "rss_slope_mb_per_hour": round(rss_slope, 3) if rss_slope is not None else None,
        "gpu_memory_initial_mb": round(gpu_values[0], 3) if gpu_values else None,
        "gpu_memory_final_mb": round(gpu_values[-1], 3) if gpu_values else None,
        "gpu_memory_max_mb": round(max(gpu_values), 3) if gpu_values else None,
        "health_error_count": len(health_errors),
        "thresholds": {
            "min_pass_duration_sec": min_pass_duration_sec,
            "max_rss_growth_mb": max_rss_growth_mb,
            "max_rss_slope_mb_per_hour": max_rss_slope_mb_per_hour,
        },
        "passes_memory_stability": passes,
        "samples": samples,
    }


def monitor(
    *,
    pid: int | None,
    port: int,
    duration_sec: float,
    interval_sec: float,
    health_url: str,
    output: Path,
    min_pass_duration_sec: float,
    max_rss_growth_mb: float,
    max_rss_slope_mb_per_hour: float,
) -> dict[str, Any]:
    resolved_pid = pid or _pid_for_port(port)
    if resolved_pid is None:
        raise RuntimeError(f"could not find C1 process listening on port {port}")

    started = time.monotonic()
    samples: list[dict[str, Any]] = []
    while True:
        elapsed = time.monotonic() - started
        rss = _rss_mb(resolved_pid)
        if rss is None:
            raise RuntimeError(f"process {resolved_pid} is not running or RSS is unavailable")
        health_latency, health_error = _health_latency_ms(health_url, timeout_sec=min(5.0, interval_sec))
        samples.append(
            {
                "timestamp": _now(),
                "elapsed_sec": round(elapsed, 3),
                "rss_mb": round(rss, 3),
                "gpu_memory_mb": _gpu_memory_mb(resolved_pid),
                "health_latency_ms": round(health_latency, 3) if health_latency is not None else None,
                "health_error": health_error,
            }
        )
        if elapsed >= duration_sec:
            break
        time.sleep(max(0.2, min(interval_sec, duration_sec - elapsed)))

    report = _summarize(
        pid=resolved_pid,
        samples=samples,
        min_pass_duration_sec=min_pass_duration_sec,
        max_rss_growth_mb=max_rss_growth_mb,
        max_rss_slope_mb_per_hour=max_rss_slope_mb_per_hour,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Monitor C1 API process RSS/GPU memory stability.")
    parser.add_argument("--pid", type=int, default=None)
    parser.add_argument("--port", type=int, default=settings.app_port)
    parser.add_argument("--duration-sec", type=float, default=600.0)
    parser.add_argument("--interval-sec", type=float, default=5.0)
    parser.add_argument("--health-url", default=f"http://{settings.app_host}:{settings.app_port}/health")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--min-pass-duration-sec", type=float, default=1800.0)
    parser.add_argument("--max-rss-growth-mb", type=float, default=128.0)
    parser.add_argument("--max-rss-slope-mb-per-hour", type=float, default=128.0)
    args = parser.parse_args()

    report = monitor(
        pid=args.pid,
        port=args.port,
        duration_sec=max(0.0, args.duration_sec),
        interval_sec=max(0.2, args.interval_sec),
        health_url=args.health_url,
        output=args.output,
        min_pass_duration_sec=max(0.0, args.min_pass_duration_sec),
        max_rss_growth_mb=max(0.0, args.max_rss_growth_mb),
        max_rss_slope_mb_per_hour=max(0.0, args.max_rss_slope_mb_per_hour),
    )
    print(
        "runtime memory:",
        f"duration={report['duration_sec']}s",
        f"rss_growth={report['rss_growth_mb']}MB",
        f"rss_slope={report['rss_slope_mb_per_hour']}MB/h",
        f"passes={report['passes_memory_stability']}",
    )
    print(f"wrote={args.output}")


if __name__ == "__main__":
    main()
