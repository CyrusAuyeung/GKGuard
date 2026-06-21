from __future__ import annotations

from collections import deque
from datetime import datetime
import json
from pathlib import Path
import threading
from typing import Any
from uuid import uuid4


RUNTIME_DIR = Path(__file__).resolve().parents[2] / "runtime"
AUDIT_LOG_PATH = RUNTIME_DIR / "audit.jsonl"
MAX_AUDIT_LOG_BYTES = 1_048_576
MAX_AUDIT_LOG_LINES = 2_000
MAX_AUDIT_VALUE_CHARS = 4_096
_AUDIT_LOCK = threading.Lock()


def _sanitize_for_audit(value: Any, depth: int = 0) -> Any:
    if depth > 6:
        return "[truncated]"
    if isinstance(value, str):
        if len(value) > MAX_AUDIT_VALUE_CHARS:
            return value[:MAX_AUDIT_VALUE_CHARS] + "...[truncated]"
        return value
    if isinstance(value, dict):
        return {str(k)[:128]: _sanitize_for_audit(v, depth + 1) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_for_audit(item, depth + 1) for item in value[:200]]
    return value


def _compact_lines_to_byte_budget(lines: list[str]) -> list[str]:
    retained: list[str] = []
    total = 0
    for line in reversed(lines[-MAX_AUDIT_LOG_LINES:]):
        size = len(line.encode("utf-8"))
        if size > MAX_AUDIT_LOG_BYTES:
            continue
        if total + size > MAX_AUDIT_LOG_BYTES:
            break
        retained.append(line)
        total += size
    retained.reverse()
    return retained


def _compact_audit_log_unlocked() -> None:
    if not AUDIT_LOG_PATH.exists() or AUDIT_LOG_PATH.stat().st_size <= MAX_AUDIT_LOG_BYTES:
        return
    with AUDIT_LOG_PATH.open("r", encoding="utf-8") as file:
        retained_lines = _compact_lines_to_byte_budget([line for line in file if line.strip()])
    temp_path = AUDIT_LOG_PATH.with_suffix(".jsonl.tmp")
    with temp_path.open("w", encoding="utf-8") as file:
        file.writelines(retained_lines)
    temp_path.replace(AUDIT_LOG_PATH)


def record_audit(action: str, actor: str = "security_desk_demo", target: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    sanitized_target = _sanitize_for_audit(target or {})
    sanitized_metadata = _sanitize_for_audit(metadata or {})
    entry = {
        "audit_id": f"AUD-{uuid4().hex[:10].upper()}",
        "time": datetime.now().replace(microsecond=0).isoformat(),
        "actor": _sanitize_for_audit(actor),
        "action": action,
        "target": sanitized_target,
        "metadata": sanitized_metadata,
    }
    with _AUDIT_LOCK:
        RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        _compact_audit_log_unlocked()
        with AUDIT_LOG_PATH.open("a", encoding="utf-8") as file:
            file.write(json.dumps(entry, ensure_ascii=False) + "\n")
        _compact_audit_log_unlocked()
    return entry


def read_audit_logs(limit: int = 20) -> list[dict[str, Any]]:
    if not AUDIT_LOG_PATH.exists():
        return []
    with _AUDIT_LOCK:
        with AUDIT_LOG_PATH.open("r", encoding="utf-8") as file:
            lines = deque((line for line in file if line.strip()), maxlen=limit)
    return [json.loads(line) for line in lines]


def clear_audit_logs() -> None:
    with _AUDIT_LOCK:
        if AUDIT_LOG_PATH.exists():
            AUDIT_LOG_PATH.unlink()
