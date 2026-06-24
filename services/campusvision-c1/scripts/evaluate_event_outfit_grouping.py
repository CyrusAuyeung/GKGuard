from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import settings  # noqa: E402
from app.services import outfit_service  # noqa: E402
from app.storage import db  # noqa: E402


LABEL_PATH = settings.data_dir / "evals" / "manual_event_outfit_groups" / "event_outfit_groups.json"
REPORT_PATH = settings.data_dir / "evals" / "manual_event_outfit_groups" / "event_outfit_group_eval.json"
DEFAULT_REFERENCE_DB = (
    settings.data_dir
    / "evals"
    / "database_snapshots"
    / "campusvision_eval_baseline_20260623_pre_full_api_rerun.sqlite3"
)

EXCLUDED_MANUAL_GROUPS = {"", "unassigned", "exclude"}
DEFAULT_REMAP_TIMESTAMP_TOLERANCE_SEC = 0.10
DEFAULT_REMAP_MIN_IOU = 0.35
DEFAULT_REMAP_AMBIGUITY_IOU_MARGIN = 0.05
TARGET_EVAL_MATCH_RATE = 0.80

_TIME_LABEL_RE = re.compile(r"(?P<start>\d+(?:\.\d+)?)s(?:-(?P<end>\d+(?:\.\d+)?)s)?")


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _loads_json(value: str | None) -> Any | None:
    if not value:
        return None
    try:
        return json.loads(value)
    except Exception:
        return None


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_time_label(value: str | None) -> tuple[float | None, float | None]:
    if not value:
        return None, None
    match = _TIME_LABEL_RE.search(value)
    if not match:
        return None, None
    start = _safe_float(match.group("start"))
    end = _safe_float(match.group("end")) if match.group("end") is not None else start
    return start, end


def _safe_bbox(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        value = _loads_json(raw)
        return value if isinstance(value, dict) else None
    return None


def _bbox_iou(left: dict[str, Any] | None, right: dict[str, Any] | None) -> float:
    if not left or not right:
        return 0.0
    try:
        left_x1, left_y1, left_x2, left_y2 = (float(left[key]) for key in ("x1", "y1", "x2", "y2"))
        right_x1, right_y1, right_x2, right_y2 = (float(right[key]) for key in ("x1", "y1", "x2", "y2"))
    except (KeyError, TypeError, ValueError):
        return 0.0
    inter_w = max(0.0, min(left_x2, right_x2) - max(left_x1, right_x1))
    inter_h = max(0.0, min(left_y2, right_y2) - max(left_y1, right_y1))
    inter = inter_w * inter_h
    left_area = max(0.0, left_x2 - left_x1) * max(0.0, left_y2 - left_y1)
    right_area = max(0.0, right_x2 - right_x1) * max(0.0, right_y2 - right_y1)
    return inter / max(1e-9, left_area + right_area - inter)


def _video_anchor(conn: sqlite3.Connection, video_id: str | None) -> dict[str, Any]:
    if not video_id:
        return {}
    try:
        row = conn.execute(
            """
            SELECT video_id, filename, camera_id, recorded_at, path, status, frame_interval_sec
            FROM videos
            WHERE video_id = ?
            """,
            (video_id,),
        ).fetchone()
    except sqlite3.OperationalError:
        return {"video_id": video_id, "video_table_missing": True}
    if row is None:
        return {"video_id": video_id, "video_missing": True}
    return dict(row)


def _reference_anchor(
    conn: sqlite3.Connection,
    *,
    event_id: str | None,
    observation_id: str | None,
) -> dict[str, Any]:
    event = None
    observation = None
    if event_id:
        event = _row_to_dict(
            conn.execute(
                """
                SELECT event_id, camera_id, video_id, live_source_id, track_id, person_id,
                       start_time, end_time, start_timestamp_sec, end_timestamp_sec,
                       observation_count, face_count, representative_observation_id,
                       representative_face_id, representative_frame_path
                FROM events
                WHERE event_id = ?
                """,
                (event_id,),
            ).fetchone()
        )
    if observation_id:
        observation = _row_to_dict(
            conn.execute(
                """
                SELECT observation_id, camera_id, video_id, live_source_id, frame_index,
                       video_timestamp_sec, captured_at, frame_path, track_id,
                       body_visibility, person_bbox_json, person_detection_confidence,
                       face_record_id, person_id
                FROM person_observations
                WHERE observation_id = ?
                """,
                (observation_id,),
            ).fetchone()
        )
    if not observation and event and event.get("representative_observation_id"):
        observation = _row_to_dict(
            conn.execute(
                """
                SELECT observation_id, camera_id, video_id, live_source_id, frame_index,
                       video_timestamp_sec, captured_at, frame_path, track_id,
                       body_visibility, person_bbox_json, person_detection_confidence,
                       face_record_id, person_id
                FROM person_observations
                WHERE observation_id = ?
                """,
                (event["representative_observation_id"],),
            ).fetchone()
        )

    if observation:
        observation["person_bbox"] = _safe_bbox(observation.pop("person_bbox_json", None))

    video_id = str((observation or {}).get("video_id") or (event or {}).get("video_id") or "")
    return {
        "event": event or {},
        "observation": observation or {},
        "video": _video_anchor(conn, video_id),
        "reference_event_found": bool(event),
        "reference_observation_found": bool(observation),
    }


def _load_raw_manual_assignment_rows(label_path: Path) -> list[dict[str, Any]]:
    data = _read_json(label_path)
    labels = data.get("labels")
    if not isinstance(labels, dict):
        raise ValueError("manual event outfit labels must contain a labels object")

    rows: list[dict[str, Any]] = []
    for label_key, label in sorted(labels.items()):
        if not isinstance(label, dict):
            continue
        person_id = str(label.get("person_id") or "")
        if not person_id:
            continue
        for index, assignment in enumerate(label.get("manual_assignments") or [], start=1):
            if not isinstance(assignment, dict):
                continue
            manual_group = str(assignment.get("manual_group") or "")
            if manual_group in EXCLUDED_MANUAL_GROUPS:
                continue
            event_id = str(assignment.get("event_id") or "")
            observation_id = str(assignment.get("observation_id") or "")
            assignment_key = f"{person_id}:{event_id or observation_id or index}"
            start_sec, end_sec = _parse_time_label(str(assignment.get("time_label") or ""))
            rows.append(
                {
                    "assignment_key": assignment_key,
                    "label_id": str(label.get("label_id") or label_key),
                    "legacy_person_id": person_id,
                    "legacy_event_id": event_id,
                    "legacy_observation_id": observation_id,
                    "legacy_appearance_session_id": str(assignment.get("appearance_session_id") or ""),
                    "camera_id": str(assignment.get("camera_id") or ""),
                    "time_label": assignment.get("time_label"),
                    "time_label_start_sec": start_sec,
                    "time_label_end_sec": end_sec,
                    "manual_group": manual_group,
                    "model_at_label_save": {
                        "upper_color": assignment.get("model_upper_color") or "unknown",
                        "upper_color_confidence": assignment.get("model_upper_color_confidence"),
                    },
                    "source": label.get("source"),
                    "saved_at": label.get("saved_at"),
                    "eval_only": True,
                }
            )
    return rows


def _load_remappable_assignment_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    rows = data.get("assignments")
    if not isinstance(rows, list):
        raise ValueError("remappable event outfit group export must contain an assignments array")
    out = []
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            continue
        manual_group = str(row.get("manual_group") or "")
        if manual_group in EXCLUDED_MANUAL_GROUPS:
            continue
        legacy = row.get("legacy") if isinstance(row.get("legacy"), dict) else {}
        start_sec, end_sec = _parse_time_label(str(row.get("time_label") or ""))
        out.append(
            {
                "assignment_key": str(row.get("assignment_key") or f"remap:{index}"),
                "label_id": str(row.get("label_id") or ""),
                "legacy_person_id": str(row.get("legacy_person_id") or ""),
                "legacy_event_id": str(legacy.get("event_id") or row.get("legacy_event_id") or ""),
                "legacy_observation_id": str(legacy.get("observation_id") or row.get("legacy_observation_id") or ""),
                "legacy_appearance_session_id": str(
                    legacy.get("appearance_session_id") or row.get("legacy_appearance_session_id") or ""
                ),
                "camera_id": str(row.get("camera_id") or legacy.get("camera_id") or ""),
                "time_label": row.get("time_label"),
                "time_label_start_sec": row.get("time_label_start_sec", start_sec),
                "time_label_end_sec": row.get("time_label_end_sec", end_sec),
                "manual_group": manual_group,
                "model_at_label_save": row.get("model_at_label_save") or {},
                "reference_anchor": row.get("reference_anchor") or {},
                "source": row.get("source"),
                "saved_at": row.get("saved_at"),
                "eval_only": True,
            }
        )
    return out


def _load_manual_assignment_rows(
    label_path: Path,
    *,
    reference_db: Path | None = None,
) -> list[dict[str, Any]]:
    data = _read_json(label_path)
    if str(data.get("schema_version") or "").startswith("remappable_event_outfit_groups"):
        rows = _load_remappable_assignment_rows(data)
    else:
        rows = _load_raw_manual_assignment_rows(label_path)

    needs_reference = any("reference_anchor" not in row for row in rows)
    if not needs_reference or not reference_db or not reference_db.exists():
        return rows

    with _connect(reference_db) as conn:
        for row in rows:
            row["reference_anchor"] = _reference_anchor(
                conn,
                event_id=row.get("legacy_event_id"),
                observation_id=row.get("legacy_observation_id"),
            )
    return rows


def _load_manual_assignments(label_path: Path) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = defaultdict(dict)
    for row in _load_raw_manual_assignment_rows(label_path):
        event_id = str(row.get("legacy_event_id") or "")
        if event_id:
            out[str(row["legacy_person_id"])][event_id] = str(row["manual_group"])
    return dict(out)


def _pairwise_counts(y_true: dict[str, str], y_pred: dict[str, str]) -> dict[str, Any]:
    event_ids = sorted(set(y_true) & set(y_pred))
    true_positive = false_positive = false_negative = true_negative = 0
    for left, right in combinations(event_ids, 2):
        same_true = y_true[left] == y_true[right]
        same_pred = y_pred[left] == y_pred[right]
        if same_true and same_pred:
            true_positive += 1
        elif not same_true and same_pred:
            false_positive += 1
        elif same_true and not same_pred:
            false_negative += 1
        else:
            true_negative += 1

    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "event_count": len(event_ids),
        "pair_count": len(event_ids) * (len(event_ids) - 1) // 2,
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "true_negative": true_negative,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def _cluster_purity(y_true: dict[str, str], y_pred: dict[str, str]) -> dict[str, Any]:
    clusters: dict[str, Counter[str]] = defaultdict(Counter)
    for event_id in sorted(set(y_true) & set(y_pred)):
        clusters[y_pred[event_id]][y_true[event_id]] += 1

    correct = sum(counter.most_common(1)[0][1] for counter in clusters.values() if counter)
    total = sum(sum(counter.values()) for counter in clusters.values())
    mixed_clusters = sum(1 for counter in clusters.values() if len(counter) > 1)
    return {
        "purity_accuracy": correct / total if total else 0.0,
        "purity_correct": correct,
        "purity_total": total,
        "mixed_predicted_groups": mixed_clusters,
    }


def _predicted_assignments(person_id: str, event_ids: set[str], distance_threshold: float) -> dict[str, str]:
    events = [
        event
        for event in db.list_events(person_id=person_id, identified=True, limit=10000)
        if str(event.get("event_id") or "") in event_ids
    ]
    groups = outfit_service.build_outfit_groups_for_events(
        person_id,
        events,
        distance_threshold=distance_threshold,
    )

    assignments = {}
    for group in groups:
        group_id = str(group.get("outfit_id") or group.get("group_index") or "")
        for event in group.get("events") or []:
            event_id = str(event.get("event_id") or "")
            if event_id:
                assignments[event_id] = group_id
    return assignments


def _predicted_assignment_index(distance_threshold: float) -> dict[str, dict[str, str]]:
    predicted: dict[str, dict[str, str]] = {}
    for group in outfit_service.build_outfit_groups(distance_threshold=distance_threshold):
        group_id = str(group.get("outfit_id") or group.get("group_index") or "")
        person_id = str(group.get("person_id") or "")
        for event in group.get("events") or []:
            event_id = str(event.get("event_id") or "")
            if event_id:
                predicted[event_id] = {
                    "group_id": group_id,
                    "person_id": person_id,
                }
    return predicted


def _current_event_by_id(conn: sqlite3.Connection, event_id: str | None) -> dict[str, Any] | None:
    if not event_id:
        return None
    row = conn.execute(
        """
        SELECT event_id, camera_id, video_id, person_id, start_timestamp_sec, end_timestamp_sec
        FROM events
        WHERE event_id = ?
        """,
        (event_id,),
    ).fetchone()
    return dict(row) if row is not None else None


def _current_event_by_observation_id(conn: sqlite3.Connection, observation_id: str | None) -> dict[str, Any] | None:
    if not observation_id:
        return None
    row = conn.execute(
        """
        SELECT e.event_id, e.camera_id, e.video_id, e.person_id, e.start_timestamp_sec, e.end_timestamp_sec
        FROM event_observations eo
        JOIN events e ON e.event_id = eo.event_id
        WHERE eo.observation_id = ?
        """,
        (observation_id,),
    ).fetchone()
    return dict(row) if row is not None else None


def _current_observation_candidates(conn: sqlite3.Connection) -> dict[str, list[dict[str, Any]]]:
    rows = conn.execute(
        """
        SELECT po.observation_id, po.camera_id, po.video_id, po.video_timestamp_sec,
               po.person_bbox_json, po.person_id AS observation_person_id,
               eo.event_id, e.person_id AS event_person_id
        FROM person_observations po
        LEFT JOIN event_observations eo ON eo.observation_id = po.observation_id
        LEFT JOIN events e ON e.event_id = eo.event_id
        """
    ).fetchall()
    by_camera: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        item = dict(row)
        item["person_bbox"] = _safe_bbox(item.pop("person_bbox_json", None))
        by_camera[str(item.get("camera_id") or "")].append(item)
    return by_camera


def _current_event_time_candidates(conn: sqlite3.Connection) -> dict[str, list[dict[str, Any]]]:
    rows = conn.execute(
        """
        SELECT event_id, camera_id, video_id, person_id, start_timestamp_sec, end_timestamp_sec
        FROM events
        """
    ).fetchall()
    by_camera: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_camera[str(row["camera_id"] or "")].append(dict(row))
    return by_camera


def _candidate_camera_ids(row: dict[str, Any]) -> list[str]:
    anchor = row.get("reference_anchor") if isinstance(row.get("reference_anchor"), dict) else {}
    event = anchor.get("event") if isinstance(anchor.get("event"), dict) else {}
    observation = anchor.get("observation") if isinstance(anchor.get("observation"), dict) else {}
    video = anchor.get("video") if isinstance(anchor.get("video"), dict) else {}
    values = [
        row.get("camera_id"),
        observation.get("camera_id"),
        event.get("camera_id"),
        video.get("camera_id"),
    ]
    out: list[str] = []
    for value in values:
        text = str(value or "")
        if text and text not in out:
            out.append(text)
    return out


def _reference_timestamp(row: dict[str, Any]) -> float | None:
    anchor = row.get("reference_anchor") if isinstance(row.get("reference_anchor"), dict) else {}
    event = anchor.get("event") if isinstance(anchor.get("event"), dict) else {}
    observation = anchor.get("observation") if isinstance(anchor.get("observation"), dict) else {}
    for value in (
        observation.get("video_timestamp_sec"),
        event.get("start_timestamp_sec"),
        row.get("time_label_start_sec"),
    ):
        number = _safe_float(value)
        if number is not None:
            return number
    return None


def _reference_bbox(row: dict[str, Any]) -> dict[str, Any] | None:
    anchor = row.get("reference_anchor") if isinstance(row.get("reference_anchor"), dict) else {}
    observation = anchor.get("observation") if isinstance(anchor.get("observation"), dict) else {}
    return _safe_bbox(observation.get("person_bbox"))


def _remap_one_assignment(
    row: dict[str, Any],
    *,
    conn: sqlite3.Connection,
    observation_candidates: dict[str, list[dict[str, Any]]],
    event_time_candidates: dict[str, list[dict[str, Any]]],
    timestamp_tolerance_sec: float,
    min_iou: float,
    ambiguity_iou_margin: float,
) -> dict[str, Any]:
    direct_event = _current_event_by_id(conn, row.get("legacy_event_id"))
    if direct_event:
        return {
            **row,
            "remap_status": "matched",
            "match_strategy": "direct_event_id",
            "current_event_id": direct_event.get("event_id"),
            "current_person_id": direct_event.get("person_id"),
            "match_iou": None,
            "match_time_delta_sec": 0.0,
        }

    direct_observation_event = _current_event_by_observation_id(conn, row.get("legacy_observation_id"))
    if direct_observation_event:
        return {
            **row,
            "remap_status": "matched",
            "match_strategy": "direct_observation_id",
            "current_event_id": direct_observation_event.get("event_id"),
            "current_person_id": direct_observation_event.get("person_id"),
            "match_iou": None,
            "match_time_delta_sec": 0.0,
        }

    timestamp = _reference_timestamp(row)
    camera_ids = _candidate_camera_ids(row)
    reference_bbox = _reference_bbox(row)
    if timestamp is not None and camera_ids and reference_bbox:
        candidates: list[dict[str, Any]] = []
        for camera_id in camera_ids:
            for candidate in observation_candidates.get(camera_id, []):
                candidate_time = _safe_float(candidate.get("video_timestamp_sec"))
                if candidate_time is None:
                    continue
                time_delta = abs(candidate_time - timestamp)
                if time_delta > timestamp_tolerance_sec:
                    continue
                iou = _bbox_iou(reference_bbox, candidate.get("person_bbox"))
                if iou >= min_iou:
                    candidates.append(
                        {
                            **candidate,
                            "match_iou": iou,
                            "match_time_delta_sec": time_delta,
                        }
                    )
        candidates.sort(
            key=lambda item: (
                -float(item.get("match_iou") or 0.0),
                float(item.get("match_time_delta_sec") or 0.0),
                str(item.get("observation_id") or ""),
            )
        )
        if candidates:
            best = candidates[0]
            if len(candidates) > 1:
                second_iou = float(candidates[1].get("match_iou") or 0.0)
                best_iou = float(best.get("match_iou") or 0.0)
                if best_iou - second_iou < ambiguity_iou_margin and second_iou >= max(min_iou, 0.50):
                    return {
                        **row,
                        "remap_status": "ambiguous",
                        "match_strategy": "reference_observation_bbox_time",
                        "candidate_count": len(candidates),
                        "candidate_examples": [
                            {
                                "observation_id": item.get("observation_id"),
                                "event_id": item.get("event_id"),
                                "person_id": item.get("event_person_id") or item.get("observation_person_id"),
                                "match_iou": round(float(item.get("match_iou") or 0.0), 6),
                                "match_time_delta_sec": round(float(item.get("match_time_delta_sec") or 0.0), 6),
                            }
                            for item in candidates[:5]
                        ],
                    }
            if best.get("event_id"):
                return {
                    **row,
                    "remap_status": "matched",
                    "match_strategy": "reference_observation_bbox_time",
                    "current_event_id": best.get("event_id"),
                    "current_person_id": best.get("event_person_id") or best.get("observation_person_id"),
                    "current_observation_id": best.get("observation_id"),
                    "match_iou": round(float(best.get("match_iou") or 0.0), 6),
                    "match_time_delta_sec": round(float(best.get("match_time_delta_sec") or 0.0), 6),
                }
        return {
            **row,
            "remap_status": "missing",
            "match_strategy": "reference_observation_bbox_time",
            "missing_reason": "no_current_observation_bbox_time_candidate",
            "reference_event_found": True,
            "reference_observation_found": True,
        }

    start_sec = _safe_float(row.get("time_label_start_sec"))
    end_sec = _safe_float(row.get("time_label_end_sec"))
    if timestamp is not None and start_sec is None:
        start_sec = timestamp
    if end_sec is None:
        end_sec = start_sec
    if camera_ids and start_sec is not None:
        candidates = []
        for camera_id in camera_ids:
            for event in event_time_candidates.get(camera_id, []):
                event_start = _safe_float(event.get("start_timestamp_sec"))
                event_end = _safe_float(event.get("end_timestamp_sec")) or event_start
                if event_start is None:
                    continue
                overlaps = (
                    event_start <= float(end_sec) + timestamp_tolerance_sec
                    and (event_end if event_end is not None else event_start)
                    >= float(start_sec) - timestamp_tolerance_sec
                )
                if overlaps:
                    candidates.append(event)
        if len(candidates) == 1:
            event = candidates[0]
            return {
                **row,
                "remap_status": "matched",
                "match_strategy": "camera_time_unique_event",
                "current_event_id": event.get("event_id"),
                "current_person_id": event.get("person_id"),
                "match_iou": None,
                "match_time_delta_sec": None,
            }
        if len(candidates) > 1:
            return {
                **row,
                "remap_status": "ambiguous",
                "match_strategy": "camera_time_unique_event",
                "candidate_count": len(candidates),
                "candidate_examples": [
                    {
                        "event_id": item.get("event_id"),
                        "person_id": item.get("person_id"),
                        "camera_id": item.get("camera_id"),
                        "start_timestamp_sec": item.get("start_timestamp_sec"),
                        "end_timestamp_sec": item.get("end_timestamp_sec"),
                    }
                    for item in candidates[:5]
                ],
            }

    anchor = row.get("reference_anchor") if isinstance(row.get("reference_anchor"), dict) else {}
    return {
        **row,
        "remap_status": "missing",
        "match_strategy": "none",
        "missing_reason": "no_current_event_candidate",
        "reference_event_found": bool(anchor.get("reference_event_found")),
        "reference_observation_found": bool(anchor.get("reference_observation_found")),
    }


def _remap_assignments_to_current_events(
    assignments: list[dict[str, Any]],
    *,
    current_db: Path,
    timestamp_tolerance_sec: float = DEFAULT_REMAP_TIMESTAMP_TOLERANCE_SEC,
    min_iou: float = DEFAULT_REMAP_MIN_IOU,
    ambiguity_iou_margin: float = DEFAULT_REMAP_AMBIGUITY_IOU_MARGIN,
) -> dict[str, Any]:
    if not current_db.exists():
        return {
            "status": "not_available",
            "current_db": str(current_db),
            "assignments": [],
            "summary": {
                "manual_assignment_count": len(assignments),
                "matched_assignment_count": 0,
                "matched_assignment_rate": 0.0,
            },
        }

    with _connect(current_db) as conn:
        observation_candidates = _current_observation_candidates(conn)
        event_time_candidates = _current_event_time_candidates(conn)
        remapped = [
            _remap_one_assignment(
                row,
                conn=conn,
                observation_candidates=observation_candidates,
                event_time_candidates=event_time_candidates,
                timestamp_tolerance_sec=timestamp_tolerance_sec,
                min_iou=min_iou,
                ambiguity_iou_margin=ambiguity_iou_margin,
            )
            for row in assignments
        ]

    status_counts = Counter(str(row.get("remap_status") or "unknown") for row in remapped)
    strategy_counts = Counter(str(row.get("match_strategy") or "unknown") for row in remapped)
    matched = [row for row in remapped if row.get("remap_status") == "matched"]
    low_iou = [
        row
        for row in matched
        if row.get("match_iou") is not None and float(row.get("match_iou") or 0.0) < 0.50
    ]
    current_event_counts = Counter(str(row.get("current_event_id") or "") for row in matched if row.get("current_event_id"))
    duplicate_current_event_ids = sorted([event_id for event_id, count in current_event_counts.items() if count > 1])
    total = len(assignments)
    return {
        "status": "evaluated" if matched else "not_replayable",
        "current_db": str(current_db),
        "timestamp_tolerance_sec": timestamp_tolerance_sec,
        "min_iou": min_iou,
        "ambiguity_iou_margin": ambiguity_iou_margin,
        "summary": {
            "manual_assignment_count": total,
            "matched_assignment_count": len(matched),
            "matched_assignment_rate": round(len(matched) / total, 6) if total else None,
            "status_counts": dict(status_counts.most_common()),
            "match_strategy_counts": dict(strategy_counts.most_common()),
            "low_iou_match_count": len(low_iou),
            "duplicate_current_event_count": len(duplicate_current_event_ids),
            "duplicate_current_event_ids": duplicate_current_event_ids[:50],
        },
        "assignments": remapped,
    }


def _evaluation_status(
    *,
    manual_assignment_count: int,
    evaluated_assignment_count: int,
    pair_count: int,
) -> tuple[str, bool, str]:
    if manual_assignment_count <= 0:
        return "no_labels", False, "No manual eval-only assignments are available."
    if evaluated_assignment_count <= 1 or pair_count <= 0:
        return "insufficient_matches", False, "Too few remapped assignments have predicted outfit groups."
    match_rate = evaluated_assignment_count / manual_assignment_count
    if match_rate < TARGET_EVAL_MATCH_RATE:
        return (
            "partial_evaluated",
            False,
            f"Only {match_rate:.2%} of manual assignments could be evaluated; target pass/fail is not reliable.",
        )
    if match_rate < 0.95:
        return (
            "partial_evaluated",
            True,
            f"Evaluation uses {match_rate:.2%} of manual assignments after remap; missing assignments are reported.",
        )
    return "evaluated", True, "Evaluation is replayable for the current database."


def evaluate(
    *,
    label_path: Path = LABEL_PATH,
    distance_threshold: float = 0.42,
    remap: bool = True,
    reference_db: Path | None = DEFAULT_REFERENCE_DB,
    current_db: Path = settings.db_path,
    timestamp_tolerance_sec: float = DEFAULT_REMAP_TIMESTAMP_TOLERANCE_SEC,
    min_iou: float = DEFAULT_REMAP_MIN_IOU,
    ambiguity_iou_margin: float = DEFAULT_REMAP_AMBIGUITY_IOU_MARGIN,
) -> dict[str, Any]:
    db.init_db()
    totals = Counter()
    person_results = []
    all_true: dict[str, str] = {}
    all_pred: dict[str, str] = {}
    predicted_group_count = 0
    remap_report: dict[str, Any] | None = None

    if remap:
        manual_rows = _load_manual_assignment_rows(label_path, reference_db=reference_db)
        remap_report = _remap_assignments_to_current_events(
            manual_rows,
            current_db=current_db,
            timestamp_tolerance_sec=timestamp_tolerance_sec,
            min_iou=min_iou,
            ambiguity_iou_margin=ambiguity_iou_margin,
        )
        predicted_index = _predicted_assignment_index(distance_threshold)
        rows_by_person: dict[str, list[dict[str, Any]]] = defaultdict(list)
        unpredicted_matches = []
        for row in remap_report["assignments"]:
            if row.get("remap_status") != "matched":
                continue
            current_event_id = str(row.get("current_event_id") or "")
            prediction = predicted_index.get(current_event_id)
            if not prediction:
                if len(unpredicted_matches) < 50:
                    unpredicted_matches.append(
                        {
                            "assignment_key": row.get("assignment_key"),
                            "legacy_person_id": row.get("legacy_person_id"),
                            "legacy_event_id": row.get("legacy_event_id"),
                            "current_event_id": current_event_id,
                            "current_person_id": row.get("current_person_id"),
                        }
                    )
                continue
            rows_by_person[str(row.get("legacy_person_id") or "")].append(
                {
                    **row,
                    "predicted_group_id": prediction["group_id"],
                    "predicted_person_id": prediction["person_id"],
                }
            )

        predicted_group_count = len({item["predicted_group_id"] for rows in rows_by_person.values() for item in rows})
        manual_assignment_count = int(remap_report["summary"]["manual_assignment_count"])
        evaluated_assignment_count = sum(len(rows) for rows in rows_by_person.values())

        for person_id, rows in sorted(rows_by_person.items()):
            y_true = {
                str(row["assignment_key"]): f"{person_id}:{row['manual_group']}"
                for row in rows
            }
            y_pred = {
                str(row["assignment_key"]): f"{row['predicted_person_id']}:{row['predicted_group_id']}"
                for row in rows
            }
            counts = _pairwise_counts(y_true, y_pred)
            purity = _cluster_purity(y_true, y_pred)
            manual_counts = Counter(str(row["manual_group"]) for row in rows)
            predicted_counts = Counter(str(row["predicted_group_id"]) for row in rows)
            current_person_counts = Counter(str(row.get("predicted_person_id") or "") for row in rows)

            for key in (
                "event_count",
                "pair_count",
                "true_positive",
                "false_positive",
                "false_negative",
                "true_negative",
            ):
                totals[key] += counts[key]
            for event_id, value in y_true.items():
                all_true[f"{person_id}:{event_id}"] = value
            for event_id, value in y_pred.items():
                all_pred[f"{person_id}:{event_id}"] = value

            person_results.append(
                {
                    "person_id": person_id,
                    "manual_group_counts": dict(manual_counts.most_common()),
                    "predicted_group_sizes": sorted(predicted_counts.values(), reverse=True),
                    "current_person_counts": dict(current_person_counts.most_common()),
                    "metrics": {
                        **{
                            key: round(value, 6) if isinstance(value, float) else value
                            for key, value in counts.items()
                        },
                        **{
                            key: round(value, 6) if isinstance(value, float) else value
                            for key, value in purity.items()
                        },
                    },
                }
            )
    else:
        manual_by_person = _load_manual_assignments(label_path)
        manual_assignment_count = sum(len(value) for value in manual_by_person.values())
        evaluated_assignment_count = 0
        unpredicted_matches = []
        for person_id, manual in sorted(manual_by_person.items()):
            predicted = _predicted_assignments(person_id, set(manual), distance_threshold)
            y_true = {
                event_id: f"{person_id}:{manual_group}"
                for event_id, manual_group in manual.items()
                if event_id in predicted
            }
            y_pred = {
                event_id: f"{person_id}:{predicted_group}"
                for event_id, predicted_group in predicted.items()
                if event_id in manual
            }
            evaluated_assignment_count += len(y_true)
            counts = _pairwise_counts(y_true, y_pred)
            purity = _cluster_purity(y_true, y_pred)
            manual_counts = Counter(manual.values())
            predicted_counts = Counter(predicted.values())
            predicted_group_count += len(predicted_counts)

            for key in (
                "event_count",
                "pair_count",
                "true_positive",
                "false_positive",
                "false_negative",
                "true_negative",
            ):
                totals[key] += counts[key]
            for event_id, value in y_true.items():
                all_true[f"{person_id}:{event_id}"] = value
            for event_id, value in y_pred.items():
                all_pred[f"{person_id}:{event_id}"] = value

            person_results.append(
                {
                    "person_id": person_id,
                    "manual_group_counts": dict(manual_counts.most_common()),
                    "predicted_group_sizes": sorted(predicted_counts.values(), reverse=True),
                    "metrics": {
                        **{
                            key: round(value, 6) if isinstance(value, float) else value
                            for key, value in counts.items()
                        },
                        **{
                            key: round(value, 6) if isinstance(value, float) else value
                            for key, value in purity.items()
                        },
                    },
                }
            )

    precision = (
        totals["true_positive"] / (totals["true_positive"] + totals["false_positive"])
        if totals["true_positive"] + totals["false_positive"]
        else 0.0
    )
    recall = (
        totals["true_positive"] / (totals["true_positive"] + totals["false_negative"])
        if totals["true_positive"] + totals["false_negative"]
        else 0.0
    )
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    purity = _cluster_purity(all_true, all_pred)
    macro_f1 = (
        sum(float(row["metrics"]["f1"]) for row in person_results) / len(person_results)
        if person_results
        else 0.0
    )
    status, target_metric_eligible, status_reason = _evaluation_status(
        manual_assignment_count=manual_assignment_count,
        evaluated_assignment_count=evaluated_assignment_count,
        pair_count=totals["pair_count"],
    )

    report = {
        "schema_version": "event_outfit_group_eval_v2",
        "generated_at": _now(),
        "label_path": str(label_path),
        "eval_only": True,
        "manual_labels_usage": "eval_only_not_training",
        "grouping_version": outfit_service.OUTFIT_GROUPING_VERSION,
        "distance_threshold": distance_threshold,
        "status": status,
        "status_reason": status_reason,
        "target_metric_eligible": target_metric_eligible,
        "remap_enabled": remap,
        "reference_db": str(reference_db) if reference_db else None,
        "current_db": str(current_db),
        "persons": len(person_results),
        "events": totals["event_count"],
        "manual_assignment_count": manual_assignment_count,
        "evaluated_assignment_count": evaluated_assignment_count,
        "evaluated_assignment_rate": round(evaluated_assignment_count / manual_assignment_count, 6)
        if manual_assignment_count
        else None,
        "manual_group_count": len({value for value in all_true.values()}),
        "predicted_group_count": predicted_group_count,
        "unpredicted_match_count": len(unpredicted_matches),
        "unpredicted_match_examples": unpredicted_matches[:50],
        "pairwise": {
            "pair_count": totals["pair_count"],
            "true_positive": totals["true_positive"],
            "false_positive": totals["false_positive"],
            "false_negative": totals["false_negative"],
            "true_negative": totals["true_negative"],
            "precision": round(precision, 6),
            "recall": round(recall, 6),
            "f1": round(f1, 6),
            "macro_f1": round(macro_f1, 6),
        },
        "purity": {
            key: round(value, 6) if isinstance(value, float) else value
            for key, value in purity.items()
        },
        "worst_persons": sorted(
            person_results,
            key=lambda row: (float(row["metrics"]["f1"]), row["person_id"]),
        )[:10],
        "results": person_results,
    }
    if remap_report is not None:
        remap_examples = [
            {
                key: row.get(key)
                for key in (
                    "assignment_key",
                    "legacy_person_id",
                    "legacy_event_id",
                    "legacy_observation_id",
                    "camera_id",
                    "time_label",
                    "remap_status",
                    "match_strategy",
                    "missing_reason",
                    "candidate_count",
                )
                if row.get(key) is not None
            }
            for row in remap_report["assignments"]
            if row.get("remap_status") != "matched"
        ][:50]
        report["remap"] = {
            key: value
            for key, value in remap_report.items()
            if key not in {"assignments"}
        }
        report["remap"]["unmatched_or_ambiguous_examples"] = remap_examples
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate event outfit grouping against eval-only manual labels.")
    parser.add_argument("--label-path", type=Path, default=LABEL_PATH)
    parser.add_argument("--output", type=Path, default=REPORT_PATH)
    parser.add_argument("--distance-threshold", type=float, default=0.42)
    parser.add_argument("--reference-db", type=Path, default=DEFAULT_REFERENCE_DB)
    parser.add_argument("--current-db", type=Path, default=settings.db_path)
    parser.add_argument("--timestamp-tolerance-sec", type=float, default=DEFAULT_REMAP_TIMESTAMP_TOLERANCE_SEC)
    parser.add_argument("--min-iou", type=float, default=DEFAULT_REMAP_MIN_IOU)
    parser.add_argument("--ambiguity-iou-margin", type=float, default=DEFAULT_REMAP_AMBIGUITY_IOU_MARGIN)
    parser.add_argument("--no-remap", action="store_true", help="Use legacy event IDs directly.")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()

    report = evaluate(
        label_path=args.label_path,
        distance_threshold=args.distance_threshold,
        remap=not args.no_remap,
        reference_db=args.reference_db,
        current_db=args.current_db,
        timestamp_tolerance_sec=args.timestamp_tolerance_sec,
        min_iou=args.min_iou,
        ambiguity_iou_margin=args.ambiguity_iou_margin,
    )
    if not args.no_write:
        _write_json(args.output, report)

    pairwise = report["pairwise"]
    purity = report["purity"]
    print(
        "event_outfit_grouping",
        f"version={report['grouping_version']}",
        f"status={report['status']}",
        f"target_metric_eligible={report['target_metric_eligible']}",
        f"persons={report['persons']}",
        f"events={report['events']}",
        f"evaluated={report['evaluated_assignment_count']}/{report['manual_assignment_count']}",
        f"precision={pairwise['precision']:.4f}",
        f"recall={pairwise['recall']:.4f}",
        f"f1={pairwise['f1']:.4f}",
        f"macro_f1={pairwise['macro_f1']:.4f}",
        f"purity={purity['purity_accuracy']:.4f}",
    )
    if report.get("remap"):
        print(f"remap={json.dumps(report['remap']['summary'], ensure_ascii=False, sort_keys=True)}")
    if not args.no_write:
        print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
