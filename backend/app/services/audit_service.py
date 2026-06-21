from __future__ import annotations

from collections import deque
from datetime import datetime
import json
from pathlib import Path
from typing import Any
from uuid import uuid4


RUNTIME_DIR = Path(__file__).resolve().parents[2] / "runtime"
AUDIT_LOG_PATH = RUNTIME_DIR / "audit.jsonl"
MAX_AUDIT_LOG_BYTES = 1_048_576
MAX_AUDIT_LOG_LINES = 2_000


def _compact_audit_log() -> None:
    if not AUDIT_LOG_PATH.exists() or AUDIT_LOG_PATH.stat().st_size <= MAX_AUDIT_LOG_BYTES:
        return
    with AUDIT_LOG_PATH.open("r", encoding="utf-8") as file:
        retained_lines = deque((line for line in file if line.strip()), maxlen=MAX_AUDIT_LOG_LINES)
    with AUDIT_LOG_PATH.open("w", encoding="utf-8") as file:
        file.writelines(retained_lines)


def record_audit(action: str, actor: str = "security_desk_demo", target: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    _compact_audit_log()
    entry = {
        "audit_id": f"AUD-{uuid4().hex[:10].upper()}",
        "time": datetime.now().replace(microsecond=0).isoformat(),
        "actor": actor,
        "action": action,
        "target": target or {},
        "metadata": metadata or {},
    }
    with AUDIT_LOG_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(entry, ensure_ascii=False) + "\n")
    _compact_audit_log()
    return entry


def read_audit_logs(limit: int = 20) -> list[dict[str, Any]]:
    if not AUDIT_LOG_PATH.exists():
        return []
    with AUDIT_LOG_PATH.open("r", encoding="utf-8") as file:
        lines = deque((line for line in file if line.strip()), maxlen=limit)
    return [json.loads(line) for line in lines]


def clear_audit_logs() -> None:
    if AUDIT_LOG_PATH.exists():
        AUDIT_LOG_PATH.unlink()
