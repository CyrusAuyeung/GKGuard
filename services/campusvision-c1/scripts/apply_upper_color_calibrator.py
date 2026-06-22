from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import settings  # noqa: E402
from app.services import event_service  # noqa: E402
from app.storage import db  # noqa: E402
from app.vision import person_analysis, upper_color_calibrator  # noqa: E402


def _event_upper_roi(event: dict[str, Any], *, allow_face_estimated: bool = True):
    observation_id = event.get("representative_observation_id")
    observation = db.get_person_observation(observation_id) if observation_id else None
    image = None
    body_box = None
    roi_source = "db_body"
    if observation and observation.get("frame_path"):
        image = cv2.imread(observation["frame_path"])
        body_box = observation.get("person_bbox")

    if image is None and event.get("representative_frame_path"):
        image = cv2.imread(event["representative_frame_path"])
    if image is None:
        return None, "frame_missing"

    if not body_box and allow_face_estimated:
        face_id = event.get("representative_face_id")
        face_record = db.get_face_record(face_id) if face_id else None
        if face_record and face_record.get("bbox"):
            body_box = person_analysis.estimate_body_bbox_from_face(
                face_record["bbox"],
                image.shape[1],
                image.shape[0],
            )
            roi_source = "face_estimated_body"

    if not body_box:
        return None, "body_missing"

    roi = person_analysis._roi_from_ratio(
        image,
        body_box,
        settings.upper_roi_start_ratio,
        settings.upper_roi_end_ratio,
    )
    if roi is None or roi.size == 0:
        return None, "roi_missing"
    return roi, roi_source


def _update_event_upper(event_id: str, color: str, confidence: float, *, dry_run: bool) -> None:
    if dry_run:
        return
    with db.get_conn() as conn:
        conn.execute(
            """
            UPDATE events SET
                upper_color = ?,
                upper_color_confidence = ?,
                upper_visible = ?,
                raw_upper_color = ?,
                raw_upper_color_confidence = ?,
                raw_upper_visible = ?,
                normalized_upper_color = ?,
                normalized_upper_color_confidence = ?,
                normalized_upper_visible = ?,
                clothing_normalization_version = ?,
                clothing_normalization_reason_json = ?,
                updated_at = ?
            WHERE event_id = ?
            """,
            (
                color,
                confidence,
                1 if color != "unknown" else 0,
                color,
                confidence,
                1 if color != "unknown" else 0,
                color,
                confidence,
                1 if color != "unknown" else 0,
                upper_color_calibrator.MODEL_VERSION,
                json.dumps(
                    {
                        "action": "apply_upper_color_calibrator",
                        "model_version": upper_color_calibrator.MODEL_VERSION,
                    },
                    ensure_ascii=False,
                ),
                db.now_iso(),
                event_id,
            ),
        )


def _update_observation_upper(observation_id: str | None, color: str, confidence: float, *, dry_run: bool) -> None:
    if dry_run or not observation_id:
        return
    with db.get_conn() as conn:
        conn.execute(
            """
            UPDATE person_observations SET
                upper_color = ?,
                upper_color_confidence = ?,
                upper_visible = ?,
                clothing_model_version = ?,
                updated_at = ?
            WHERE observation_id = ?
            """,
            (
                color,
                confidence,
                1 if color != "unknown" else 0,
                upper_color_calibrator.MODEL_VERSION,
                db.now_iso(),
                observation_id,
            ),
        )


def apply_calibrator(
    *,
    person_id: str | None = None,
    limit: int = 5000,
    dry_run: bool = False,
    rebuild_appearance_sessions: bool = True,
    allow_face_estimated: bool = True,
) -> dict[str, Any]:
    db.init_db()
    model = upper_color_calibrator.get_default_model()
    if model is None:
        raise RuntimeError(f"upper color calibrator not found: {settings.upper_color_calibrator_path}")

    events = db.list_events(person_id=person_id, identified=True, limit=limit)
    stats = {
        "dry_run": dry_run,
        "events_total": len(events),
        "events_updated": 0,
        "skipped": Counter(),
        "before_colors": Counter(),
        "after_colors": Counter(),
        "roi_sources": Counter(),
        "changed": Counter(),
        "touched_person_ids": set(),
    }

    for event in events:
        before = event.get("normalized_upper_color") or event.get("upper_color") or "unknown"
        stats["before_colors"][before] += 1
        roi, roi_source = _event_upper_roi(event, allow_face_estimated=allow_face_estimated)
        if roi is None:
            stats["skipped"][roi_source] += 1
            stats["after_colors"][before] += 1
            continue

        result = person_analysis.classify_clothing_color(roi, part="upper")
        color = result.color or "unknown"
        confidence = float(result.confidence if result.confidence is not None else 0.0)
        stats["roi_sources"][roi_source] += 1
        stats["after_colors"][color] += 1
        stats["changed"][(before, color)] += 1
        _update_event_upper(event["event_id"], color, confidence, dry_run=dry_run)
        _update_observation_upper(event.get("representative_observation_id"), color, confidence, dry_run=dry_run)
        stats["events_updated"] += 1
        if event.get("person_id"):
            stats["touched_person_ids"].add(event["person_id"])

    appearance_result = None
    if rebuild_appearance_sessions and stats["touched_person_ids"] and not dry_run:
        appearance_result = event_service.rebuild_appearance_sessions_for_persons(stats["touched_person_ids"])

    return {
        "dry_run": stats["dry_run"],
        "events_total": stats["events_total"],
        "events_updated": stats["events_updated"],
        "skipped": dict(stats["skipped"].most_common()),
        "before_colors": dict(stats["before_colors"].most_common()),
        "after_colors": dict(stats["after_colors"].most_common()),
        "roi_sources": dict(stats["roi_sources"].most_common()),
        "changed": [
            {"from": before, "to": after, "count": count}
            for (before, after), count in stats["changed"].most_common()
        ],
        "touched_person_count": len(stats["touched_person_ids"]),
        "appearance_sessions": appearance_result,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply the trained upper-color calibrator to existing C1 events.")
    parser.add_argument("--person-id", default=None)
    parser.add_argument("--limit", type=int, default=5000)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-rebuild-appearance-sessions", action="store_true")
    parser.add_argument("--no-face-estimated", action="store_true")
    args = parser.parse_args()
    result = apply_calibrator(
        person_id=args.person_id,
        limit=args.limit,
        dry_run=args.dry_run,
        rebuild_appearance_sessions=not args.no_rebuild_appearance_sessions,
        allow_face_estimated=not args.no_face_estimated,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
