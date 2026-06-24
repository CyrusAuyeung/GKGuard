from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import settings  # noqa: E402
from scripts.evaluate_event_outfit_grouping import (  # noqa: E402
    DEFAULT_REFERENCE_DB,
    LABEL_PATH,
    _load_manual_assignment_rows,
    _now,
    _write_json,
)


DEFAULT_EXPORT_ROOT = settings.data_dir / "evals" / "manual_event_outfit_groups" / "remap_exports"


def _safe_component(value: object) -> str:
    raw = str(value or "item")
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in raw).strip("._")
    return safe[:96] or "item"


def _assignment_export(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "assignment_key": row.get("assignment_key"),
        "label_id": row.get("label_id"),
        "legacy_person_id": row.get("legacy_person_id"),
        "manual_group": row.get("manual_group"),
        "camera_id": row.get("camera_id"),
        "time_label": row.get("time_label"),
        "time_label_start_sec": row.get("time_label_start_sec"),
        "time_label_end_sec": row.get("time_label_end_sec"),
        "legacy": {
            "event_id": row.get("legacy_event_id"),
            "observation_id": row.get("legacy_observation_id"),
            "appearance_session_id": row.get("legacy_appearance_session_id"),
        },
        "model_at_label_save": row.get("model_at_label_save") or {},
        "reference_anchor": row.get("reference_anchor") or {},
        "source": row.get("source"),
        "saved_at": row.get("saved_at"),
        "eval_only": True,
    }


def export_remappable_event_outfit_groups(
    *,
    label_path: Path,
    reference_db: Path,
    export_root: Path,
) -> dict[str, Any]:
    assignments = _load_manual_assignment_rows(label_path, reference_db=reference_db)
    export_id = f"remappable_event_outfit_groups_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    export_dir = export_root / _safe_component(export_id)
    exported = [_assignment_export(row) for row in assignments]

    reference_event_matches = sum(
        1
        for item in exported
        if (item.get("reference_anchor") or {}).get("reference_event_found")
    )
    reference_observation_matches = sum(
        1
        for item in exported
        if (item.get("reference_anchor") or {}).get("reference_observation_found")
    )
    camera_counts = Counter(str(item.get("camera_id") or "unknown") for item in exported)
    manual_group_counts = Counter(
        f"{item.get('legacy_person_id')}:{item.get('manual_group')}" for item in exported
    )
    report = {
        "schema_version": "remappable_event_outfit_groups_v1",
        "generated_at": _now(),
        "export_id": export_id,
        "export_dir": str(export_dir),
        "source_label_path": str(label_path),
        "reference_db": str(reference_db),
        "policy": {
            "manual_labels_usage": "eval_only",
            "training_allowed": False,
            "purpose": "Replay manual event outfit grouping labels after database/event-id regeneration.",
        },
        "remap_guidance": [
            "Primary remap anchor: reference observation camera_id + video_timestamp_sec + person_bbox IoU.",
            "Fallback anchor: camera_id + time_label when exactly one current event overlaps.",
            "Legacy IDs are trace fields; event_id/person_id/observation_id are not expected to survive a full rerun.",
        ],
        "summary": {
            "assignment_count": len(exported),
            "reference_event_matches": reference_event_matches,
            "reference_observation_matches": reference_observation_matches,
            "manual_group_count": len(manual_group_counts),
            "camera_counts": dict(camera_counts.most_common()),
        },
        "assignments": exported,
    }

    report_path = export_dir / "remappable_event_outfit_groups.json"
    latest_path = export_root / "remappable_event_outfit_groups_latest.json"
    _write_json(report_path, report)
    _write_json(latest_path, report)
    return {
        "report_path": str(report_path),
        "latest_path": str(latest_path),
        "summary": report["summary"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Export remappable eval-only event outfit grouping labels.")
    parser.add_argument("--labels", type=Path, default=LABEL_PATH)
    parser.add_argument("--reference-db", type=Path, default=DEFAULT_REFERENCE_DB)
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    args = parser.parse_args()

    result = export_remappable_event_outfit_groups(
        label_path=args.labels,
        reference_db=args.reference_db,
        export_root=args.export_root,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
