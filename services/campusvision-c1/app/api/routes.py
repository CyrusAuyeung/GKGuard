from __future__ import annotations

import base64
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response

from app.api.security import require_c1_api_key
from app.schemas import (
    AppearanceSessionOut,
    CameraCreate,
    CameraOut,
    EventOut,
    IndexResult,
    LiveCaptureResult,
    LiveMonitorStart,
    LiveMonitorStatus,
    LiveSourceCreate,
    LiveSourceOut,
    LiveSourceStatus,
    PersonAttributeQueryRequest,
    PersonAttributeQueryResult,
    PersonEventOut,
    PersonIndexResult,
    PersonObservationOut,
    PersonOut,
    VideoOut,
)
from app.core.config import settings
from app.services import (
    event_service,
    gender_presentation_service,
    glasses_status_service,
    live_service,
    outfit_service,
    person_attribute_query_service,
    person_service,
    search_service,
    video_service,
)
from app.services.upload_limits import UploadTooLarge
from app.storage import db

router = APIRouter()

_MANUAL_LABEL_DIR = settings.data_dir / "evals" / "manual_clothing_labels"
_MANUAL_LABEL_PATH = _MANUAL_LABEL_DIR / "person_clothing_labels.json"
_MANUAL_SESSION_LABEL_DIR = settings.data_dir / "evals" / "manual_appearance_session_labels"
_MANUAL_SESSION_LABEL_PATH = _MANUAL_SESSION_LABEL_DIR / "appearance_session_labels.json"
_MANUAL_OUTFIT_LABEL_DIR = settings.data_dir / "evals" / "manual_outfit_labels"
_MANUAL_OUTFIT_LABEL_PATH = _MANUAL_OUTFIT_LABEL_DIR / "outfit_labels.json"
_MANUAL_EVENT_OUTFIT_GROUP_DIR = settings.data_dir / "evals" / "manual_event_outfit_groups"
_MANUAL_EVENT_OUTFIT_GROUP_PATH = _MANUAL_EVENT_OUTFIT_GROUP_DIR / "event_outfit_groups.json"
_MANUAL_GENDER_PRESENTATION_LABEL_DIR = settings.data_dir / "evals" / "manual_gender_presentation_labels"
_MANUAL_GENDER_PRESENTATION_LABEL_PATH = (
    _MANUAL_GENDER_PRESENTATION_LABEL_DIR / "person_gender_presentation_labels.json"
)
_MANUAL_PERSON_GLASSES_LABEL_DIR = settings.data_dir / "evals" / "manual_person_glasses_labels"
_MANUAL_PERSON_GLASSES_LABEL_PATH = _MANUAL_PERSON_GLASSES_LABEL_DIR / "person_glasses_labels.json"
_MANUAL_SAMPLE_SNAPSHOT_DIR = settings.data_dir / "evals" / "manual_sample_snapshots"
_MANUAL_SAMPLE_SNAPSHOT_VERSION = "manual_sample_snapshots_v1"

_SESSION_REVIEW_STATUS_LABELS = {
    "unreviewed": "未审核",
    "confirmed": "模型正确",
    "corrected": "已修正",
    "uncertain": "存疑",
    "ignore": "不纳入评估",
}

_OUTFIT_SPLIT_GROUPS = ("A", "B", "C", "D", "E", "F", "exclude")
_MANUAL_OUTFIT_GROUPS = ("unassigned", "A", "B", "C", "D", "E", "F", "exclude")
_OUTFIT_SPLIT_GROUP_LABELS = {
    "unassigned": "未分组",
    "A": "A",
    "B": "B",
    "C": "C",
    "D": "D",
    "E": "E",
    "F": "F",
    "exclude": "排除",
}

_GENDER_PRESENTATION_OPTIONS = {
    "masculine": "偏男性",
    "feminine": "偏女性",
    "neutral": "中性风",
    "unknown": "无法判断",
}

_GENDER_EVIDENCE_QUALITY_OPTIONS = {
    "clear": "清晰",
    "partial": "部分可见",
    "poor": "画质较差",
}

_GLASSES_STATUS_OPTIONS = {
    "glasses": "戴眼镜",
    "no_glasses": "未戴眼镜",
    "unknown": "无法判断",
}

_GLASSES_EVIDENCE_QUALITY_OPTIONS = {
    "clear": "清晰",
    "partial": "部分可见",
    "poor": "画质较差",
}


_COLOR_HEX = {
    "black": "#17191c",
    "white": "#f7f7f2",
    "gray": "#8b929c",
    "red": "#c0392b",
    "orange": "#d2691e",
    "yellow": "#d4a017",
    "green": "#2e7d32",
    "blue": "#2364aa",
    "purple": "#6f42c1",
    "brown": "#795548",
    "pink": "#c64f8a",
    "striped": "repeating-linear-gradient(45deg, #17191c 0 5px, #f7f7f2 5px 10px)",
    "other": "#4f5d75",
    "unknown": "#d7dce2",
}

_COLOR_LABELS = {
    "black": "black",
    "white": "white",
    "gray": "gray",
    "red": "red",
    "orange": "orange",
    "yellow": "yellow",
    "green": "green",
    "blue": "blue",
    "purple": "purple",
    "brown": "brown",
    "pink": "pink",
    "striped": "条纹",
    "other": "other",
    "unknown": "unknown",
}


def _h(value: object) -> str:
    return escape(str(value or ""), quote=True)


def _parse_query_face_indices(raw: str | None, fallback_index: int | None = None) -> list[int | None] | None:
    if raw is None or not str(raw).strip():
        return [int(fallback_index)] if fallback_index is not None else None

    text = str(raw).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = [item.strip() for item in text.split(",")]

    if isinstance(parsed, int):
        parsed = [parsed]
    if not isinstance(parsed, list):
        raise HTTPException(status_code=400, detail="query_face_indices must be a JSON array, integer, or comma list")

    out: list[int | None] = []
    for item in parsed:
        if item is None or item == "":
            out.append(None)
            continue
        try:
            value = int(item)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="query_face_indices values must be integers or null") from exc
        if value < 0:
            raise HTTPException(status_code=400, detail="query_face_indices values must be non-negative")
        out.append(value)
    return out


def _color_label(color: str | None) -> str:
    label = color or "unknown"
    return _COLOR_LABELS.get(label, label)


def _short_id(value: str | None, keep: int = 8) -> str:
    if not value:
        return ""
    if len(value) <= keep:
        return value
    return value[-keep:]


def _color_chip(color: str | None, confidence: float | None = None, support: int | None = None) -> str:
    label = color or "unknown"
    hex_value = _COLOR_HEX.get(label, _COLOR_HEX["unknown"])
    meta = []
    if confidence is not None:
        meta.append(f"{float(confidence):.2f}")
    if support is not None:
        meta.append(f"n={int(support)}")
    suffix = f'<span class="chip-meta">{_h(" / ".join(meta))}</span>' if meta else ""
    return (
        '<span class="color-chip">'
        f'<span class="swatch" style="background:{_h(hex_value)}"></span>'
        f'<span>{_h(_color_label(label))}</span>{suffix}'
        "</span>"
    )


def _session_time_label(session: dict) -> str:
    if session.get("start_time") or session.get("end_time"):
        return f"{session.get('start_time') or ''} - {session.get('end_time') or ''}"
    start = session.get("start_timestamp_sec")
    end = session.get("end_timestamp_sec")
    if start is not None or end is not None:
        return f"{float(start or 0.0):.1f}s - {float(end or 0.0):.1f}s"
    return ""


def _event_time_label(event: dict) -> str:
    if event.get("start_time") or event.get("end_time"):
        return event.get("start_time") or event.get("end_time") or ""
    start = event.get("start_timestamp_sec")
    end = event.get("end_timestamp_sec")
    if start is not None or end is not None:
        return f"{float(start or 0.0):.1f}s-{float(end or 0.0):.1f}s"
    return ""


def _part_change(event: dict, prefix: str) -> bool:
    raw_color = event.get(f"raw_{prefix}_color") or "unknown"
    normalized_color = event.get(f"normalized_{prefix}_color") or event.get(f"{prefix}_color") or "unknown"
    raw_visible = event.get(f"raw_{prefix}_visible")
    normalized_visible = event.get(f"normalized_{prefix}_visible")
    return raw_visible != normalized_visible or raw_color != normalized_color


def _part_line(event: dict, prefix: str, label: str) -> str:
    raw_color = event.get(f"raw_{prefix}_color") or "unknown"
    raw_conf = event.get(f"raw_{prefix}_color_confidence")
    raw_visible = event.get(f"raw_{prefix}_visible")
    normalized_color = event.get(f"normalized_{prefix}_color") or event.get(f"{prefix}_color") or "unknown"
    normalized_conf = event.get(f"normalized_{prefix}_color_confidence") or event.get(
        f"{prefix}_color_confidence"
    )
    normalized_visible = event.get(f"normalized_{prefix}_visible")

    if raw_visible is False and normalized_visible is False:
        return f'<span class="part-line"><b>{_h(label)}</b><span class="muted">未见</span></span>'

    if _part_change(event, prefix):
        return (
            f'<span class="part-line changed"><b>{_h(label)}</b>'
            f'{_color_chip(raw_color, raw_conf)}<span class="arrow">→</span>'
            f'{_color_chip(normalized_color, normalized_conf)}</span>'
        )

    return f'<span class="part-line"><b>{_h(label)}</b>{_color_chip(normalized_color, normalized_conf)}</span>'


def _event_tile(event: dict) -> str:
    image_url = (
        event.get("representative_body_crop_url")
        or event.get("representative_frame_url")
        or event.get("representative_face_crop_url")
        or ""
    )
    face_url = event.get("representative_face_crop_url") or ""
    changed = _part_change(event, "upper")
    changed_class = " changed-event" if changed else ""
    image_html = (
        f'<img class="body-img" src="{_h(image_url)}" alt="{_h(event.get("event_id"))}">'
        if image_url
        else '<div class="body-img placeholder"></div>'
    )
    face_html = (
        f'<img class="face-img" src="{_h(face_url)}" alt="{_h(event.get("representative_face_id"))}">'
        if face_url
        else '<div class="face-img placeholder"></div>'
    )
    return f"""
        <article class="event-tile{changed_class}">
            <div class="event-media">{image_html}{face_html}</div>
            <div class="event-copy">
                <strong>{_h(event.get("camera_id"))}</strong>
                <span class="muted">{_h(_event_time_label(event))}</span>
                {_part_line(event, "upper", "上装")}
            </div>
        </article>
    """


def _outfit_time_label(group: dict) -> str:
    if group.get("start_time") or group.get("end_time"):
        return f"{group.get('start_time') or ''} - {group.get('end_time') or ''}"
    start = group.get("start_timestamp_sec")
    end = group.get("end_timestamp_sec")
    if start is not None or end is not None:
        return f"{float(start or 0.0):.1f}s - {float(end or 0.0):.1f}s"
    return ""


def _appearance_outfit_card(group: dict) -> str:
    events = sorted(
        group.get("events") or [],
        key=lambda event: (
            event.get("start_time") or "",
            float(event.get("start_timestamp_sec") or 0.0),
            event.get("event_id") or "",
        ),
    )
    event_tiles = "".join(_event_tile(event) for event in events)
    camera_ids = [item for item in group.get("camera_ids") or [] if item]
    camera_text = ", ".join(camera_ids[:6])
    if len(camera_ids) > 6:
        camera_text = f"{camera_text} +{len(camera_ids) - 6}"
    color_counts = group.get("model_upper_color_counts") or {}
    count_text = ", ".join(f"{_color_label(color)}:{count}" for color, count in color_counts.items())
    return f"""
        <section class="outfit-row" data-outfit-id="{_h(group.get("outfit_id"))}">
            <div class="outfit-meta">
                <div class="outfit-head">
                    <strong title="{_h(group.get("outfit_id"))}">装束 {int(group.get("group_index") or 0)}</strong>
                    <span>{int(group.get("event_count") or 0)} events</span>
                </div>
                <div class="outfit-color">
                    {_color_chip(group.get("model_upper_color"), group.get("model_upper_color_confidence"))}
                </div>
                <div class="outfit-note">{_h(_outfit_time_label(group))}</div>
                <div class="outfit-note" title="{_h(camera_text)}">来源 {_h(camera_text or "-")}</div>
                <div class="outfit-note" title="{_h(count_text)}">上装分布 {_h(count_text or "-")}</div>
            </div>
            <div class="event-strip">
                {event_tiles or '<p class="empty">No events</p>'}
            </div>
        </section>
    """


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _url_with_query(path: str, **params: object) -> str:
    query: dict[str, str] = {}
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, bool):
            query[key] = str(value).lower()
        else:
            query[key] = str(value)
    encoded = urlencode(query)
    return f"{path}?{encoded}" if encoded else path


def _person_scope_tabs(path: str, include_candidates: bool, **params: object) -> str:
    all_href = _url_with_query(path, include_candidates=True, **params)
    stable_href = _url_with_query(path, include_candidates=False, **params)
    all_class = "scope-tab active" if include_candidates else "scope-tab"
    stable_class = "scope-tab active" if not include_candidates else "scope-tab"
    return f"""
        <nav class="scope-tabs" aria-label="人物范围">
            <a class="{all_class}" href="{_h(all_href)}">全部人物</a>
            <a class="{stable_class}" href="{_h(stable_href)}">只看稳定人物</a>
        </nav>
    """


def _scoped_persons(person_id: Optional[str], include_candidates: bool) -> list[dict]:
    persons = [
        dict(person) | {"identity_status": person_service.identity_status(person)}
        for person in db.list_persons()
        if not person_id or person["person_id"] == person_id
    ]
    if not include_candidates:
        persons = [person for person in persons if person.get("identity_status") == "stable"]
    return persons


def _safe_path_component(value: object) -> str:
    raw = str(value or "item")
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in raw).strip("._")
    return safe[:96] or "item"


def _path_for_label_json(path: Path) -> str:
    try:
        return path.resolve().relative_to(settings.data_dir.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _snapshot_url(path: Path) -> str:
    try:
        rel = path.resolve().relative_to(_MANUAL_SAMPLE_SNAPSHOT_DIR.resolve()).as_posix()
    except ValueError:
        return ""
    return f"/api/v1/eval-sample-snapshots/{rel}"


def _write_jpeg_snapshot(path: Path, image, *, quality: int = 92) -> bool:
    import cv2

    if image is None or getattr(image, "size", 0) <= 0:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 0:
        return True
    return bool(cv2.imwrite(str(path), image, [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)]))


def _crop_bbox_image(image, bbox: dict, *, padding_ratio: float = 0.04):
    from app.vision.person_analysis import clamp_bbox

    if image is None or not bbox:
        return None
    height, width = image.shape[:2]
    raw_w = max(1.0, float(bbox.get("x2", 0) - bbox.get("x1", 0)))
    raw_h = max(1.0, float(bbox.get("y2", 0) - bbox.get("y1", 0)))
    padded = {
        **bbox,
        "x1": float(bbox["x1"]) - raw_w * padding_ratio,
        "y1": float(bbox["y1"]) - raw_h * padding_ratio,
        "x2": float(bbox["x2"]) + raw_w * padding_ratio,
        "y2": float(bbox["y2"]) + raw_h * padding_ratio,
    }
    box = clamp_bbox(padded, width, height)
    crop = image[box["y1"] : box["y2"], box["x1"] : box["x2"]]
    return crop if getattr(crop, "size", 0) > 0 else None


def _manual_sample_refs(
    *,
    sample_event_ids: list[str] | None = None,
    sample_observation_ids: list[str] | None = None,
    assignments: list[dict] | None = None,
    group_field: str | None = None,
) -> list[dict]:
    refs: list[dict] = []
    lookup: dict[tuple[str, str], dict] = {}

    def add_ref(event_id: object = "", observation_id: object = "", group_value: object = "") -> None:
        event_text = str(event_id or "")
        observation_text = str(observation_id or "")
        if not event_text and not observation_text:
            return
        key = (event_text, observation_text)
        if key not in lookup:
            item = {"event_id": event_text, "observation_id": observation_text}
            lookup[key] = item
            refs.append(item)
        if group_field and group_value:
            lookup[key][group_field] = str(group_value)

    event_ids = sample_event_ids or []
    observation_ids = sample_observation_ids or []
    for index, event_id in enumerate(event_ids):
        observation_id = observation_ids[index] if index < len(observation_ids) else ""
        add_ref(event_id, observation_id)
    if len(observation_ids) > len(event_ids):
        for observation_id in observation_ids[len(event_ids) :]:
            add_ref("", observation_id)

    for assignment in assignments or []:
        if not isinstance(assignment, dict):
            continue
        add_ref(
            assignment.get("event_id") or "",
            assignment.get("observation_id") or "",
            assignment.get(group_field) if group_field else "",
        )
    return refs


def _snapshot_manual_samples(label_set: str, label_id: str, refs: list[dict]) -> list[dict]:
    import cv2

    snapshots: list[dict] = []
    label_dir = _MANUAL_SAMPLE_SNAPSHOT_DIR / _safe_path_component(label_set) / _safe_path_component(label_id)

    for ref in refs:
        if not isinstance(ref, dict):
            continue
        event_id = str(ref.get("event_id") or "")
        observation_id = str(ref.get("observation_id") or "")
        key_material = f"{label_set}|{label_id}|{event_id}|{observation_id}"
        digest = hashlib.sha1(key_material.encode("utf-8")).hexdigest()[:14]
        prefix = f"sample_{digest}"
        out: dict = {
            "snapshot_version": _MANUAL_SAMPLE_SNAPSHOT_VERSION,
            "sample_key": observation_id or event_id or digest,
            "event_id": event_id,
            "observation_id": observation_id,
            "snapshot_errors": [],
        }
        for key, value in ref.items():
            if key not in out and value:
                out[key] = value

        try:
            event = db.get_event(event_id) if event_id else None
            observation = db.get_person_observation(observation_id) if observation_id else None
            if observation is None and event and event.get("representative_observation_id"):
                observation = db.get_person_observation(str(event["representative_observation_id"]))
                if observation and not out.get("observation_id"):
                    out["observation_id"] = str(observation.get("observation_id") or "")

            face_id = (
                (observation or {}).get("face_record_id")
                or (event or {}).get("representative_face_id")
                or ""
            )
            face_record = db.get_face_record(str(face_id)) if face_id else None
            if face_id:
                out["face_id"] = str(face_id)

            frame_path = (
                (observation or {}).get("frame_path")
                or (event or {}).get("representative_frame_path")
                or (face_record or {}).get("frame_path")
                or ""
            )
            frame_image = cv2.imread(str(frame_path)) if frame_path else None
            if frame_image is None:
                out["snapshot_errors"].append("frame_missing")
            else:
                out["source_frame_path"] = str(frame_path)
                out["frame_shape"] = [int(frame_image.shape[1]), int(frame_image.shape[0])]
                frame_out = label_dir / f"{prefix}_frame.jpg"
                if _write_jpeg_snapshot(frame_out, frame_image):
                    out["snapshot_frame_path"] = _path_for_label_json(frame_out)
                    out["snapshot_frame_url"] = _snapshot_url(frame_out)
                else:
                    out["snapshot_errors"].append("frame_write_failed")

                body_bbox = (observation or {}).get("person_bbox")
                if body_bbox:
                    out["body_bbox"] = body_bbox
                    body_crop = _crop_bbox_image(frame_image, body_bbox)
                    body_out = label_dir / f"{prefix}_body.jpg"
                    if body_crop is not None and _write_jpeg_snapshot(body_out, body_crop):
                        out["snapshot_body_path"] = _path_for_label_json(body_out)
                        out["snapshot_body_url"] = _snapshot_url(body_out)
                    else:
                        out["snapshot_errors"].append("body_write_failed")
                else:
                    out["snapshot_errors"].append("body_bbox_missing")

            if face_record and face_record.get("bbox"):
                face_frame_path = face_record.get("frame_path") or frame_path
                face_image = cv2.imread(str(face_frame_path)) if face_frame_path else frame_image
                face_crop = _crop_bbox_image(face_image, face_record["bbox"], padding_ratio=0.0)
                face_out = label_dir / f"{prefix}_face.jpg"
                if face_crop is not None and _write_jpeg_snapshot(face_out, face_crop):
                    out["snapshot_face_path"] = _path_for_label_json(face_out)
                    out["snapshot_face_url"] = _snapshot_url(face_out)
                else:
                    out["snapshot_errors"].append("face_write_failed")
            elif face_id:
                out["snapshot_errors"].append("face_record_missing")

            out["snapshot_available"] = bool(
                out.get("snapshot_body_path") or out.get("snapshot_frame_path") or out.get("snapshot_face_path")
            )
        except Exception as exc:  # Snapshotting must never block saving eval labels.
            out["snapshot_available"] = False
            out.setdefault("snapshot_errors", []).append(f"{type(exc).__name__}: {exc}")

        snapshots.append(out)
    return snapshots


def _snapshot_count(snapshots: list[dict]) -> int:
    return sum(1 for item in snapshots if isinstance(item, dict) and item.get("snapshot_available"))


def _load_manual_clothing_labels() -> dict:
    if not _MANUAL_LABEL_PATH.exists():
        return {
            "schema_version": "person_clothing_labels_v1",
            "created_at": _utc_now(),
            "updated_at": None,
            "labels": {},
        }
    try:
        data = json.loads(_MANUAL_LABEL_PATH.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    labels = data.get("labels")
    if not isinstance(labels, dict):
        labels = {}
    return {
        "schema_version": data.get("schema_version") or "person_clothing_labels_v1",
        "created_at": data.get("created_at") or _utc_now(),
        "updated_at": data.get("updated_at"),
        "labels": labels,
    }


def _save_manual_clothing_labels(data: dict) -> None:
    _MANUAL_LABEL_DIR.mkdir(parents=True, exist_ok=True)
    tmp_path = _MANUAL_LABEL_PATH.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    tmp_path.replace(_MANUAL_LABEL_PATH)


def _load_manual_appearance_session_labels() -> dict:
    if not _MANUAL_SESSION_LABEL_PATH.exists():
        return {
            "schema_version": "appearance_session_clothing_labels_v1",
            "created_at": _utc_now(),
            "updated_at": None,
            "labels": {},
        }
    try:
        data = json.loads(_MANUAL_SESSION_LABEL_PATH.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    labels = data.get("labels")
    if not isinstance(labels, dict):
        labels = {}
    return {
        "schema_version": data.get("schema_version") or "appearance_session_clothing_labels_v1",
        "created_at": data.get("created_at") or _utc_now(),
        "updated_at": data.get("updated_at"),
        "labels": labels,
    }


def _save_manual_appearance_session_labels(data: dict) -> None:
    _MANUAL_SESSION_LABEL_DIR.mkdir(parents=True, exist_ok=True)
    tmp_path = _MANUAL_SESSION_LABEL_PATH.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    tmp_path.replace(_MANUAL_SESSION_LABEL_PATH)


def _load_manual_outfit_labels() -> dict:
    if not _MANUAL_OUTFIT_LABEL_PATH.exists():
        return {
            "schema_version": "outfit_clothing_labels_v1",
            "created_at": _utc_now(),
            "updated_at": None,
            "labels": {},
        }
    try:
        data = json.loads(_MANUAL_OUTFIT_LABEL_PATH.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    labels = data.get("labels")
    if not isinstance(labels, dict):
        labels = {}
    return {
        "schema_version": data.get("schema_version") or "outfit_clothing_labels_v1",
        "created_at": data.get("created_at") or _utc_now(),
        "updated_at": data.get("updated_at"),
        "labels": labels,
    }


def _save_manual_outfit_labels(data: dict) -> None:
    _MANUAL_OUTFIT_LABEL_DIR.mkdir(parents=True, exist_ok=True)
    tmp_path = _MANUAL_OUTFIT_LABEL_PATH.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    tmp_path.replace(_MANUAL_OUTFIT_LABEL_PATH)


def _load_manual_event_outfit_groups() -> dict:
    if not _MANUAL_EVENT_OUTFIT_GROUP_PATH.exists():
        return {
            "schema_version": "manual_event_outfit_groups_v1",
            "source": "manual_event_outfit_grouping_eval",
            "eval_only": True,
            "created_at": _utc_now(),
            "updated_at": None,
            "labels": {},
        }
    try:
        data = json.loads(_MANUAL_EVENT_OUTFIT_GROUP_PATH.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    labels = data.get("labels")
    if not isinstance(labels, dict):
        labels = {}
    return {
        "schema_version": data.get("schema_version") or "manual_event_outfit_groups_v1",
        "source": data.get("source") or "manual_event_outfit_grouping_eval",
        "eval_only": True,
        "created_at": data.get("created_at") or _utc_now(),
        "updated_at": data.get("updated_at"),
        "labels": labels,
    }


def _save_manual_event_outfit_groups(data: dict) -> None:
    data["schema_version"] = data.get("schema_version") or "manual_event_outfit_groups_v1"
    data["source"] = "manual_event_outfit_grouping_eval"
    data["eval_only"] = True
    _MANUAL_EVENT_OUTFIT_GROUP_DIR.mkdir(parents=True, exist_ok=True)
    tmp_path = _MANUAL_EVENT_OUTFIT_GROUP_PATH.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    tmp_path.replace(_MANUAL_EVENT_OUTFIT_GROUP_PATH)


def _load_manual_gender_presentation_labels() -> dict:
    if not _MANUAL_GENDER_PRESENTATION_LABEL_PATH.exists():
        return {
            "schema_version": "manual_gender_presentation_labels_v1",
            "source": "manual_gender_presentation_review_eval",
            "eval_only": True,
            "created_at": _utc_now(),
            "updated_at": None,
            "labels": {},
        }
    try:
        data = json.loads(_MANUAL_GENDER_PRESENTATION_LABEL_PATH.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    labels = data.get("labels")
    if not isinstance(labels, dict):
        labels = {}
    return {
        "schema_version": data.get("schema_version") or "manual_gender_presentation_labels_v1",
        "source": "manual_gender_presentation_review_eval",
        "eval_only": True,
        "created_at": data.get("created_at") or _utc_now(),
        "updated_at": data.get("updated_at"),
        "labels": labels,
    }


def _save_manual_gender_presentation_labels(data: dict) -> None:
    data["schema_version"] = data.get("schema_version") or "manual_gender_presentation_labels_v1"
    data["source"] = "manual_gender_presentation_review_eval"
    data["eval_only"] = True
    _MANUAL_GENDER_PRESENTATION_LABEL_DIR.mkdir(parents=True, exist_ok=True)
    tmp_path = _MANUAL_GENDER_PRESENTATION_LABEL_PATH.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    tmp_path.replace(_MANUAL_GENDER_PRESENTATION_LABEL_PATH)


def _load_manual_person_glasses_labels() -> dict:
    if not _MANUAL_PERSON_GLASSES_LABEL_PATH.exists():
        return {
            "schema_version": "manual_person_glasses_labels_v1",
            "source": "manual_person_glasses_review",
            "created_at": _utc_now(),
            "updated_at": None,
            "labels": {},
        }
    try:
        data = json.loads(_MANUAL_PERSON_GLASSES_LABEL_PATH.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    labels = data.get("labels")
    if not isinstance(labels, dict):
        labels = {}
    return {
        "schema_version": data.get("schema_version") or "manual_person_glasses_labels_v1",
        "source": "manual_person_glasses_review",
        "created_at": data.get("created_at") or _utc_now(),
        "updated_at": data.get("updated_at"),
        "labels": labels,
    }


def _save_manual_person_glasses_labels(data: dict) -> None:
    data["schema_version"] = data.get("schema_version") or "manual_person_glasses_labels_v1"
    data["source"] = "manual_person_glasses_review"
    _MANUAL_PERSON_GLASSES_LABEL_DIR.mkdir(parents=True, exist_ok=True)
    tmp_path = _MANUAL_PERSON_GLASSES_LABEL_PATH.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    tmp_path.replace(_MANUAL_PERSON_GLASSES_LABEL_PATH)


def _review_status_options(selected: str | None) -> str:
    selected = selected or "unreviewed"
    return "".join(
        f'<option value="{_h(value)}"{" selected" if value == selected else ""}>{_h(label)}</option>'
        for value, label in _SESSION_REVIEW_STATUS_LABELS.items()
    )


def _split_group_options(selected: str | None) -> str:
    selected = selected if selected in _OUTFIT_SPLIT_GROUPS else "A"
    return "".join(
        f'<option value="{_h(value)}"{" selected" if value == selected else ""}>{_h(_OUTFIT_SPLIT_GROUP_LABELS[value])}</option>'
        for value in _OUTFIT_SPLIT_GROUPS
    )


def _manual_group_options(selected: str | None) -> str:
    selected = selected if selected in _MANUAL_OUTFIT_GROUPS else "unassigned"
    return "".join(
        f'<option value="{_h(value)}"{" selected" if value == selected else ""}>{_h(_OUTFIT_SPLIT_GROUP_LABELS[value])}</option>'
        for value in _MANUAL_OUTFIT_GROUPS
    )


def _gender_presentation_options(selected: str | None) -> str:
    selected = selected if selected in _GENDER_PRESENTATION_OPTIONS else "unknown"
    return "".join(
        f'<option value="{_h(value)}"{" selected" if value == selected else ""}>{_h(label)}</option>'
        for value, label in _GENDER_PRESENTATION_OPTIONS.items()
    )


def _gender_evidence_quality_options(selected: str | None) -> str:
    selected = selected if selected in _GENDER_EVIDENCE_QUALITY_OPTIONS else "partial"
    return "".join(
        f'<option value="{_h(value)}"{" selected" if value == selected else ""}>{_h(label)}</option>'
        for value, label in _GENDER_EVIDENCE_QUALITY_OPTIONS.items()
    )


def _glasses_status_options(selected: str | None) -> str:
    selected = selected if selected in _GLASSES_STATUS_OPTIONS else "unknown"
    return "".join(
        f'<option value="{_h(value)}"{" selected" if value == selected else ""}>{_h(label)}</option>'
        for value, label in _GLASSES_STATUS_OPTIONS.items()
    )


def _glasses_evidence_quality_options(selected: str | None) -> str:
    selected = selected if selected in _GLASSES_EVIDENCE_QUALITY_OPTIONS else "partial"
    return "".join(
        f'<option value="{_h(value)}"{" selected" if value == selected else ""}>{_h(label)}</option>'
        for value, label in _GLASSES_EVIDENCE_QUALITY_OPTIONS.items()
    )


def _manual_person_outfit_label_id(person_id: str) -> str:
    return f"manual_person_outfits_{person_id}"


def _manual_event_outfit_group_label_id(person_id: str) -> str:
    return f"manual_event_outfit_groups_{person_id}"


def _manual_split_groups(assignments: list[dict[str, str]]) -> dict[str, dict]:
    groups: dict[str, dict] = {}
    for assignment in assignments:
        split_group = assignment.get("split_group")
        if split_group not in _OUTFIT_SPLIT_GROUPS or split_group == "exclude":
            continue
        group = groups.setdefault(
            split_group,
            {
                "split_group": split_group,
                "sample_count": 0,
                "sample_event_ids": [],
                "sample_observation_ids": [],
            },
        )
        group["sample_count"] += 1
        if assignment.get("event_id"):
            group["sample_event_ids"].append(assignment["event_id"])
        if assignment.get("observation_id"):
            group["sample_observation_ids"].append(assignment["observation_id"])
    return {key: groups[key] for key in sorted(groups)}


def _sample_evenly(items: list[dict], count: int) -> list[dict]:
    if count <= 0:
        return []
    if len(items) <= count:
        return items
    if count == 1:
        return [items[len(items) // 2]]
    last_index = len(items) - 1
    indexes = {
        round(index * last_index / (count - 1))
        for index in range(count)
    }
    return [items[index] for index in sorted(indexes)]


def _appearance_session_samples(events: list[dict], sample_count: int) -> list[dict]:
    ordered = sorted(
        events,
        key=lambda event: (
            event.get("start_time") or "",
            float(event.get("start_timestamp_sec") or 0.0),
            event.get("event_id") or "",
        ),
    )
    samples = []
    for event in _sample_evenly(ordered, max(1, min(int(sample_count), 12))):
        image_url = (
            event.get("representative_body_crop_url")
            or event.get("representative_frame_url")
            or event.get("representative_face_crop_url")
            or ""
        )
        samples.append(
            {
                "event_id": event.get("event_id"),
                "observation_id": event.get("representative_observation_id"),
                "camera_id": event.get("camera_id"),
                "time_label": _event_time_label(event),
                "image_url": image_url,
                "frame_url": event.get("representative_frame_url") or image_url,
                "face_url": event.get("representative_face_crop_url") or "",
                "model_upper_color": event.get("normalized_upper_color") or event.get("upper_color") or "unknown",
                "model_upper_confidence": event.get("normalized_upper_color_confidence")
                or event.get("upper_color_confidence"),
                "raw_upper_color": event.get("raw_upper_color"),
            }
        )
    return samples


def _person_body_samples(person_id: str, sample_count: int) -> list[dict]:
    samples = []
    for event in db.list_events(person_id=person_id, limit=5000):
        observation_id = event.get("representative_observation_id")
        if not observation_id:
            continue
        observation = db.get_person_observation(observation_id)
        if not observation or not observation.get("person_bbox"):
            continue
        samples.append(
            {
                "event_id": event["event_id"],
                "observation_id": observation_id,
                "camera_id": event.get("camera_id"),
                "video_id": event.get("video_id"),
                "time_label": _event_time_label(event),
                "body_crop_url": f"/api/v1/media/event/body/{event['event_id']}",
                "frame_url": f"/api/v1/media/event/frame/{event['event_id']}",
                "face_crop_url": f"/api/v1/media/face/{event['representative_face_id']}"
                if event.get("representative_face_id")
                else "",
                "model_upper_color": event.get("normalized_upper_color") or event.get("upper_color"),
                "model_upper_visible": event.get("normalized_upper_visible"),
                "raw_upper_color": event.get("raw_upper_color"),
            }
        )
    return samples[: max(1, min(int(sample_count), 12))]


def _person_face_samples(person_id: str, sample_count: int) -> list[dict]:
    samples = []
    events = sorted(
        db.list_events(person_id=person_id, identified=True, limit=5000),
        key=lambda event: (
            event.get("start_time") or "",
            float(event.get("start_timestamp_sec") or 0.0),
            event.get("event_id") or "",
        ),
    )
    for event in _sample_evenly(events, max(1, min(int(sample_count), 12))):
        face_id = event.get("representative_face_id")
        observation_id = event.get("representative_observation_id")
        body_crop_url = None
        if observation_id:
            observation = db.get_person_observation(str(observation_id))
            if observation and observation.get("person_bbox"):
                body_crop_url = f"/api/v1/media/event/body/{event['event_id']}"
        samples.append(
            {
                "event_id": event.get("event_id"),
                "observation_id": observation_id,
                "camera_id": event.get("camera_id"),
                "video_id": event.get("video_id"),
                "time_label": _event_time_label(event),
                "face_crop_url": f"/api/v1/media/face/{face_id}" if face_id else "",
                "frame_url": f"/api/v1/media/event/frame/{event['event_id']}",
                "body_crop_url": body_crop_url,
                "face_count": int(event.get("face_count") or 0),
            }
        )
    return samples


def _person_event_glasses_labels(person_id: str, glasses_status: str, evidence_quality: str) -> list[dict]:
    labels = []
    for event in db.list_events(person_id=person_id, identified=True, limit=5000):
        labels.append(
            {
                "event_id": event["event_id"],
                "person_id": person_id,
                "camera_id": event.get("camera_id"),
                "video_id": event.get("video_id"),
                "start_time": event.get("start_time"),
                "end_time": event.get("end_time"),
                "start_timestamp_sec": event.get("start_timestamp_sec"),
                "end_timestamp_sec": event.get("end_timestamp_sec"),
                "representative_observation_id": event.get("representative_observation_id"),
                "representative_face_id": event.get("representative_face_id"),
                "glasses_status": glasses_status,
                "glasses_status_label": _GLASSES_STATUS_OPTIONS[glasses_status],
                "glasses_evidence_quality": evidence_quality,
                "glasses_evidence_quality_label": _GLASSES_EVIDENCE_QUALITY_OPTIONS[evidence_quality],
                "propagation_source": "manual_person_level",
            }
        )
    return labels


def _person_outfit_group_samples(person_id: str, sample_count: int) -> list[dict]:
    events = db.list_events(person_id=person_id, identified=True, limit=5000)
    ordered = sorted(
        events,
        key=lambda event: (
            event.get("start_time") or "",
            float(event.get("start_timestamp_sec") or 0.0),
            event.get("event_id") or "",
        ),
    )
    samples = []
    for event in _sample_evenly(ordered, max(1, min(int(sample_count), 200))):
        image_url = (
            event.get("representative_body_crop_url")
            or event.get("representative_frame_url")
            or event.get("representative_face_crop_url")
            or ""
        )
        samples.append(
            {
                "event_id": event.get("event_id"),
                "observation_id": event.get("representative_observation_id"),
                "camera_id": event.get("camera_id"),
                "time_label": _event_time_label(event),
                "image_url": image_url,
                "frame_url": event.get("representative_frame_url") or image_url,
                "face_url": event.get("representative_face_crop_url") or "",
            }
        )
    return samples


def _color_options(selected: str | None) -> str:
    selected = selected or "unknown"
    return "".join(
        f'<option value="{_h(color)}"{" selected" if color == selected else ""}>{_h(_color_label(color))}</option>'
        for color in settings.clothing_color_labels
    )


def _visibility_checked(value: object) -> str:
    return " checked" if bool(value) else ""


def _validate_query_upload_count(files: list[UploadFile]) -> None:
    if len(files) > settings.max_query_images:
        raise HTTPException(
            status_code=413,
            detail=f"Too many query images; maximum is {settings.max_query_images}.",
        )


def _cleanup_query_uploads(paths: list[str], search_id: str) -> None:
    for path in paths:
        try:
            Path(path).unlink(missing_ok=True)
        except OSError:
            pass
    try:
        upload_dir = settings.query_uploads_dir / search_id
        upload_dir.rmdir()
    except OSError:
        pass


def _face_crop_jpeg(face_id: str) -> bytes:
    import cv2

    record = db.get_face_record(face_id)
    if not record:
        raise HTTPException(status_code=404, detail="face_id not found")

    image = cv2.imread(record["frame_path"])
    if image is None:
        raise HTTPException(status_code=404, detail="frame image not found")

    height, width = image.shape[:2]
    bbox = record["bbox"]
    x1 = max(0, min(width - 1, int(bbox["x1"])))
    y1 = max(0, min(height - 1, int(bbox["y1"])))
    x2 = max(x1 + 1, min(width, int(bbox["x2"])))
    y2 = max(y1 + 1, min(height, int(bbox["y2"])))

    crop = image[y1:y2, x1:x2]
    ok, encoded = cv2.imencode(".jpg", crop)
    if not ok:
        raise HTTPException(status_code=500, detail="failed to encode face crop")
    return encoded.tobytes()


def _face_crop_data_url(face_id: str | None) -> str:
    if not face_id:
        return ""
    try:
        encoded = base64.b64encode(_face_crop_jpeg(str(face_id))).decode("ascii")
    except HTTPException:
        return ""
    return f"data:image/jpeg;base64,{encoded}"


@router.post("/cameras", response_model=CameraOut)
def create_camera(payload: CameraCreate):
    return db.upsert_camera(payload.model_dump())


@router.get("/cameras", response_model=list[CameraOut])
def list_cameras():
    return db.list_cameras()


@router.post("/videos/upload", response_model=VideoOut)
async def upload_video(
    _: None = Depends(require_c1_api_key),
    file: UploadFile = File(...),
    camera_id: str = Form(...),
    recorded_at: Optional[str] = Form(None),
    frame_interval_sec: Optional[float] = Form(None),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename.")

    try:
        video = video_service.save_uploaded_video(
            file.file,
            filename=file.filename,
            camera_id=camera_id,
            recorded_at=recorded_at,
            frame_interval_sec=frame_interval_sec,
        )
    except UploadTooLarge as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    return video


@router.get("/videos", response_model=list[VideoOut])
def list_videos():
    return db.list_videos()


@router.post("/live-sources", response_model=LiveSourceOut)
def upsert_live_source(payload: LiveSourceCreate):
    try:
        return live_service.upsert_live_source(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/live-sources", response_model=list[LiveSourceOut])
def list_live_sources():
    return live_service.list_live_sources()


@router.get("/live-sources/{source_id}/status", response_model=LiveSourceStatus)
def live_source_status(source_id: str, read_timeout_sec: float = 5.0):
    try:
        return live_service.probe_live_source(source_id, read_timeout_sec=read_timeout_sec)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/live-sources/{source_id}/capture", response_model=LiveCaptureResult)
def capture_live_source(
    source_id: str,
    duration_sec: float = 10.0,
    frame_interval_sec: Optional[float] = None,
    index: bool = False,
    recorded_at: Optional[str] = None,
):
    try:
        capture_recorded_at = recorded_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
            "+00:00", "Z"
        )
        return live_service.capture_live_source(
            source_id,
            duration_sec=duration_sec,
            frame_interval_sec=frame_interval_sec,
            index=index,
            recorded_at=capture_recorded_at,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Live source capture failed: {exc}") from exc


@router.post("/live-sources/{source_id}/monitor/start", response_model=LiveMonitorStatus)
def start_live_monitor(source_id: str, payload: LiveMonitorStart):
    try:
        return live_service.start_live_monitor(
            source_id,
            segment_sec=payload.segment_sec,
            frame_interval_sec=payload.frame_interval_sec,
            update_person_index=payload.update_person_index,
            person_update_interval_segments=payload.person_update_interval_segments,
            retention_hours=payload.retention_hours,
            cleanup_interval_segments=payload.cleanup_interval_segments,
            merge_threshold=payload.merge_threshold,
            person_match_threshold=payload.person_match_threshold,
            min_faces=payload.min_faces,
            min_face_area=payload.min_face_area,
            min_detection_score=payload.min_detection_score,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/live-sources/{source_id}/monitor/stop", response_model=LiveMonitorStatus)
def stop_live_monitor(source_id: str):
    return live_service.stop_live_monitor(source_id)


@router.get("/live-sources/{source_id}/monitor", response_model=LiveMonitorStatus)
def live_monitor_status(source_id: str):
    try:
        return live_service.live_monitor_status(source_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/live-monitors", response_model=list[LiveMonitorStatus])
def list_live_monitors():
    return live_service.list_live_monitors()


@router.post("/persons/rebuild-index", response_model=PersonIndexResult)
def rebuild_person_index(
    _: None = Depends(require_c1_api_key),
    merge_threshold: Optional[float] = Form(None),
    min_faces: int = Form(2),
    min_face_area: float = Form(2500.0),
    min_detection_score: float = Form(0.85),
):
    return person_service.rebuild_person_index(
        merge_threshold=merge_threshold,
        min_faces=min_faces,
        min_face_area=min_face_area,
        min_detection_score=min_detection_score,
    )


@router.post("/persons/update-index", response_model=PersonIndexResult)
def update_person_index(
    _: None = Depends(require_c1_api_key),
    merge_threshold: Optional[float] = Form(0.80),
    person_match_threshold: float = Form(0.82),
    ambiguous_person_match_threshold: Optional[float] = Form(0.78),
    min_faces: int = Form(4),
    min_face_area: float = Form(2500.0),
    min_detection_score: float = Form(0.85),
    camera_id_prefix: Optional[str] = Form(None),
    create_unmatched_persons: bool = Form(True),
    candidate_display_name_prefix: Optional[str] = Form(None),
    use_pose_fragment_merge: bool = Form(False),
    recover_weak_stable: bool = Form(False),
    min_cluster_mean_similarity: float = Form(0.0),
    dry_run: bool = Form(False),
):
    return person_service.update_person_index(
        merge_threshold=merge_threshold,
        person_match_threshold=person_match_threshold,
        ambiguous_person_match_threshold=ambiguous_person_match_threshold,
        min_faces=min_faces,
        min_face_area=min_face_area,
        min_detection_score=min_detection_score,
        camera_id_prefix=camera_id_prefix,
        create_unmatched_persons=create_unmatched_persons,
        candidate_display_name_prefix=candidate_display_name_prefix,
        use_pose_fragment_merge=use_pose_fragment_merge,
        recover_weak_stable=recover_weak_stable,
        min_cluster_mean_similarity=min_cluster_mean_similarity,
        dry_run=dry_run,
    )


@router.get("/persons", response_model=list[PersonOut])
def list_persons(include_candidates: bool = False):
    return person_service.list_persons(include_candidates=include_candidates)


@router.get("/persons/gallery", response_class=HTMLResponse)
def persons_gallery(include_candidates: bool = False):
    persons = person_service.person_gallery_items(include_candidates=include_candidates)
    cards = []
    for person in persons:
        events = person.get("events", [])
        latest_clothing = person.get("latest_clothing") or {}
        upper = latest_clothing.get("upper_color") or "unknown"
        gender_profile = person.get("gender_presentation_profile") or {}
        gender_label = gender_profile.get("gender_presentation_label") or "未计算"
        gender_value = gender_profile.get("gender_presentation") or "unknown"
        gender_confidence = gender_profile.get("confidence")
        gender_confidence_text = (
            f"{float(gender_confidence):.2f}" if gender_confidence is not None else "-"
        )
        gender_quality = gender_profile.get("evidence_quality_label") or "-"
        glasses_profile = person.get("glasses_status_profile") or {}
        glasses_label = glasses_profile.get("glasses_status_label") or "未计算"
        glasses_value = glasses_profile.get("glasses_status") or "unknown"
        glasses_confidence = glasses_profile.get("confidence")
        glasses_confidence_text = (
            f"{float(glasses_confidence):.2f}" if glasses_confidence is not None else "-"
        )
        glasses_quality = glasses_profile.get("evidence_quality_label") or "-"
        for event in events:
            event["display_time"] = event.get("start_time") or (
                f'{event.get("start_time_display") or ""} - {event.get("end_time_display") or ""}'
            )
            event["body_image_url"] = (
                event.get("representative_body_crop_url")
                or event.get("representative_frame_url")
                or event.get("representative_face_crop_url")
                or ""
            )
            event["face_image_url"] = event.get("representative_face_crop_url") or ""
            event["upper_label"] = event.get("normalized_upper_color") or event.get("upper_color") or "unknown"
            event["raw_upper_label"] = event.get("raw_upper_color") or event["upper_label"]
            event["session_label"] = (event.get("appearance_session_id") or "").replace("appearance_", "session:")
            event["upper_changed"] = event["raw_upper_label"] != event["upper_label"]
            event["glasses_label"] = event.get("glasses_status_label") or "未计算"
        event_tiles = "".join(
            f"""
            <article class="event-tile">
                <div class="event-images">
                    <img class="body-shot" src="{escape(event["body_image_url"])}" alt="{escape(event.get("event_id") or "")}">
                    <img class="face-shot" src="{escape(event["face_image_url"])}" alt="{escape(event.get("representative_face_id") or "")}">
                </div>
                <div class="event-copy">
                    <strong>{escape(event.get("camera_name") or event.get("camera_id") or "")}</strong>
                    <span>{escape(str(event.get("display_time") or ""))}</span>
                    <span>上装 {escape(str(event["upper_label"]))}</span>
                    <span>眼镜 {escape(str(event["glasses_label"]))}</span>
                    <span>{escape(str(event["session_label"] or "no session"))}</span>
                    <span>{int(event.get("face_count") or 0)} faces</span>
                </div>
            </article>
            """
            for event in events
        )
        cards.append(
            f"""
            <article class="person-card">
                <img class="hero-face" src="{escape(person.get('representative_face_crop_url') or '')}" alt="representative face">
                <div class="person-meta">
                    <h2>{escape(person['person_id'])}</h2>
                    <dl>
                        <div><dt>identity_status</dt><dd>{escape(str(person.get('identity_status') or ''))}</dd></div>
                        <div><dt>face_count</dt><dd>{int(person.get('face_count') or 0)}</dd></div>
                        <div><dt>event_count</dt><dd>{int(person.get('event_count') or 0)}</dd></div>
                        <div><dt>latest_upper</dt><dd>{escape(str(upper))}</dd></div>
                        <div><dt>外观倾向</dt><dd>{escape(str(gender_label))} · {escape(str(gender_value))} · conf {escape(gender_confidence_text)} · {escape(str(gender_quality))}</dd></div>
                        <div><dt>眼镜状态</dt><dd>{escape(str(glasses_label))} · {escape(str(glasses_value))} · conf {escape(glasses_confidence_text)} · {escape(str(glasses_quality))}</dd></div>
                        <div><dt>representative_face_id</dt><dd>{escape(str(person.get('representative_face_id') or ''))}</dd></div>
                        <div><dt>first_seen_at</dt><dd>{escape(str(person.get('first_seen_at') or ''))}</dd></div>
                        <div><dt>last_seen_at</dt><dd>{escape(str(person.get('last_seen_at') or ''))}</dd></div>
                    </dl>
                </div>
                <div class="events">{event_tiles or '<p class="empty">No events</p>'}</div>
            </article>
            """
        )

    body = "\n".join(cards) or '<p class="empty">No persons indexed yet.</p>'
    mode_text = "全部身份含候选" if include_candidates else "稳定身份"
    toggle_href = "/api/v1/persons/gallery" if include_candidates else "/api/v1/persons/gallery?include_candidates=true"
    toggle_text = "只看稳定身份" if include_candidates else "查看候选碎片"
    return HTMLResponse(
        f"""
        <!doctype html>
        <html lang="zh-CN">
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>CampusVision 人物库</title>
            <style>
                body {{ margin: 0; font-family: Arial, sans-serif; background: #f6f7f9; color: #20242a; }}
                main {{ max-width: 1180px; margin: 0 auto; padding: 24px; }}
                header {{ display: flex; justify-content: space-between; align-items: baseline; gap: 16px; margin-bottom: 18px; }}
                h1 {{ font-size: 24px; margin: 0; }}
                .count, .mode-link {{ color: #69717d; }}
                .mode-link {{ font-size: 13px; text-decoration: none; border-bottom: 1px solid #aeb6c2; }}
                .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(360px, 1fr)); gap: 16px; }}
                .person-card {{ display: grid; grid-template-columns: 128px 1fr; gap: 14px; padding: 14px; background: #fff; border: 1px solid #dde1e7; border-radius: 8px; }}
                .hero-face {{ width: 128px; height: 128px; object-fit: cover; background: #e9edf2; border-radius: 6px; }}
                h2 {{ font-size: 16px; margin: 0 0 10px; word-break: break-all; }}
                dl {{ margin: 0; display: grid; gap: 6px; }}
                dl div {{ display: grid; grid-template-columns: 128px 1fr; gap: 8px; }}
                dt {{ color: #69717d; }}
                dd {{ margin: 0; word-break: break-all; }}
                .events {{ grid-column: 1 / -1; display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 8px; padding-top: 4px; }}
                .event-tile {{ display: grid; grid-template-columns: 86px 1fr; gap: 8px; align-items: center; min-width: 0; padding: 8px; border: 1px solid #e4e8ee; border-radius: 6px; background: #fbfcfd; }}
                .event-images {{ width: 86px; height: 72px; display: grid; grid-template-columns: 52px 30px; gap: 4px; }}
                .event-images img {{ width: 100%; height: 72px; object-fit: cover; border-radius: 5px; background: #e9edf2; }}
                .event-images .face-shot {{ height: 30px; align-self: start; }}
                .event-copy {{ min-width: 0; display: grid; gap: 3px; }}
                .event-tile strong, .event-tile span {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
                .event-tile strong {{ font-size: 13px; }}
                .event-tile span {{ color: #69717d; font-size: 12px; }}
                .empty {{ color: #69717d; }}
            </style>
        </head>
        <body>
            <main>
                <header>
                    <h1>CampusVision 人物库</h1>
                    <span class="count">{escape(mode_text)} · {len(persons)} persons · <a class="mode-link" href="{toggle_href}">{escape(toggle_text)}</a></span>
                </header>
                <section class="grid">{body}</section>
            </main>
        </body>
        </html>
        """
    )


@router.get("/appearance-sessions/gallery", response_class=HTMLResponse)
def appearance_sessions_gallery(
    person_id: Optional[str] = None,
    changed_only: bool = False,
    outfit_distance_threshold: float = 0.42,
    limit: int = 200,
    include_candidates: bool = True,
):
    scoped_persons = _scoped_persons(person_id, include_candidates)
    scoped_person_ids = {person["person_id"] for person in scoped_persons}
    sessions = event_service.list_appearance_sessions(person_id=person_id)
    sessions = [
        session
        for session in sessions
        if session.get("person_id") in scoped_person_ids
    ]
    sessions = sessions[: max(1, min(int(limit), 1000))]
    events = db.list_events(person_id=person_id, identified=True, limit=5000)
    events = [
        event
        for event in events
        if event.get("person_id") in scoped_person_ids
    ]
    events_by_session: dict[str, list[dict]] = defaultdict(list)
    for event in events:
        session_id = event.get("appearance_session_id")
        if session_id:
            events_by_session[session_id].append(event)

    if changed_only:
        sessions = [
            session
            for session in sessions
            if any(
                _part_change(event, "upper")
                for event in events_by_session.get(session["session_id"], [])
            )
        ]

    persons = {person["person_id"]: person for person in scoped_persons}
    sessions_by_person: dict[str, list[dict]] = defaultdict(list)
    for session in sessions:
        sessions_by_person[session["person_id"]].append(session)

    changed_event_count = sum(
        1
        for event in events
        if event.get("appearance_session_id")
        and _part_change(event, "upper")
    )
    assigned_event_count = sum(1 for event in events if event.get("appearance_session_id"))

    person_blocks = []
    for current_person_id in sorted(sessions_by_person):
        person = persons.get(current_person_id, {})
        face_id = person.get("representative_face_id")
        face_html = (
            f'<img class="person-face" src="/api/v1/media/face/{_h(face_id)}" alt="{_h(face_id)}">'
            if face_id
            else '<div class="person-face placeholder"></div>'
        )
        session_rows = []
        for session in sorted(
            sessions_by_person[current_person_id],
            key=lambda item: (
                item.get("start_time") or "",
                float(item.get("start_timestamp_sec") or 0.0),
                item.get("session_id") or "",
            ),
        ):
            session_events = sorted(
                events_by_session.get(session["session_id"], []),
                key=lambda event: (
                    event.get("start_time") or "",
                    float(event.get("start_timestamp_sec") or 0.0),
                    event.get("event_id") or "",
                ),
            )
            outfit_groups = outfit_service.build_outfit_groups_for_events(
                current_person_id,
                session_events,
                distance_threshold=max(0.1, min(float(outfit_distance_threshold), 0.9)),
            )
            outfit_cards = "".join(_appearance_outfit_card(group) for group in outfit_groups)
            session_rows.append(
                f"""
                <section class="session-row">
                    <div class="session-meta">
                        <div class="session-head">
                            <strong title="{_h(session.get("session_id"))}">session:{_h(_short_id(session.get("session_id")))}</strong>
                            <span>{int(session.get("event_count") or 0)} events</span>
                        </div>
                        <div class="session-time">{_h(_session_time_label(session))}</div>
                        <div class="session-colors">
                            <span class="label">上装</span>
                            {_color_chip(session.get("upper_color"), session.get("upper_color_confidence"), session.get("upper_color_support"))}
                        </div>
                    </div>
                    <div class="outfit-list">
                        {outfit_cards or '<p class="empty">No outfits</p>'}
                    </div>
                </section>
                """
            )

        person_blocks.append(
            f"""
            <section class="person-block">
                <header class="person-header">
                    {face_html}
                    <div>
                        <h2 title="{_h(current_person_id)}">{_h(current_person_id)}</h2>
                        <div class="person-stats">
                            <span>{_h(person.get("identity_status") or "")}</span>
                            <span>{int(person.get("face_count") or 0)} faces</span>
                            <span>{len(sessions_by_person[current_person_id])} sessions</span>
                        </div>
                    </div>
                </header>
                <div class="session-list">
                    {"".join(session_rows)}
                </div>
            </section>
            """
        )

    body = "\n".join(person_blocks) or '<p class="empty">No appearance sessions</p>'
    scope_tabs = _person_scope_tabs(
        "/api/v1/appearance-sessions/gallery",
        include_candidates,
        person_id=person_id,
        changed_only=changed_only,
        outfit_distance_threshold=float(outfit_distance_threshold),
        limit=limit,
    )
    scope_label = "全部人物" if include_candidates else "只看稳定人物"
    return HTMLResponse(
        f"""
        <!doctype html>
        <html lang="zh-CN">
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>Appearance Sessions</title>
            <style>
                * {{ box-sizing: border-box; }}
                body {{ margin: 0; font-family: Arial, sans-serif; background: #f5f6f8; color: #20242a; }}
                main {{ max-width: 1440px; margin: 0 auto; padding: 20px; }}
                .topbar {{ display: flex; justify-content: space-between; align-items: end; gap: 16px; margin-bottom: 16px; }}
                h1 {{ margin: 0; font-size: 24px; font-weight: 700; }}
                h2 {{ margin: 0; font-size: 15px; word-break: break-all; }}
                .summary {{ display: flex; flex-wrap: wrap; gap: 8px; color: #56606b; font-size: 13px; }}
                .summary span, .person-stats span, .session-head span {{
                    display: inline-flex; align-items: center; height: 24px; padding: 0 8px;
                    border: 1px solid #d9dee5; border-radius: 6px; background: #fff;
                }}
                .scope-tabs {{ display: inline-flex; align-items: center; height: 34px; padding: 3px; border: 1px solid #cdd4df; border-radius: 7px; background: #fff; }}
                .scope-tab {{ display: inline-flex; align-items: center; height: 26px; padding: 0 10px; border-radius: 5px; color: #56606b; text-decoration: none; font-size: 13px; }}
                .scope-tab.active {{ background: #20242a; color: #fff; }}
                .person-block {{ margin-bottom: 18px; border: 1px solid #d9dee5; border-radius: 8px; background: #fff; overflow: hidden; }}
                .person-header {{ display: flex; align-items: center; gap: 12px; padding: 12px 14px; border-bottom: 1px solid #e5e9ef; background: #fbfcfd; }}
                .person-face {{ width: 54px; height: 54px; object-fit: cover; border-radius: 6px; background: #e8ecf1; }}
                .person-stats {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 7px; font-size: 12px; color: #56606b; }}
                .session-list {{ display: grid; }}
                .session-row {{ display: grid; grid-template-columns: 280px 1fr; gap: 12px; padding: 12px 14px; border-bottom: 1px solid #e9edf2; }}
                .session-row:last-child {{ border-bottom: 0; }}
                .session-meta {{ min-width: 0; display: grid; align-content: start; gap: 9px; }}
                .session-head {{ display: flex; align-items: center; justify-content: space-between; gap: 8px; }}
                .session-head strong {{ font-size: 13px; }}
                .session-time {{ font-size: 12px; color: #56606b; word-break: break-word; }}
                .session-colors {{ display: grid; grid-template-columns: 42px 1fr; gap: 7px 8px; align-items: center; }}
                .label {{ color: #56606b; font-size: 12px; }}
                .color-chip {{ min-width: 0; display: inline-flex; align-items: center; gap: 6px; color: #20242a; font-size: 12px; }}
                .swatch {{ flex: 0 0 auto; width: 14px; height: 14px; border-radius: 3px; border: 1px solid #aeb6c2; }}
                .chip-meta {{ color: #707b87; }}
                .outfit-list {{ min-width: 0; display: grid; gap: 10px; }}
                .outfit-row {{ min-width: 0; display: grid; grid-template-columns: 190px 1fr; gap: 10px; padding: 10px; border: 1px solid #dfe5ed; border-radius: 8px; background: #fbfcfd; }}
                .outfit-meta {{ min-width: 0; display: grid; align-content: start; gap: 7px; }}
                .outfit-head {{ display: flex; justify-content: space-between; align-items: center; gap: 8px; }}
                .outfit-head strong {{ font-size: 13px; }}
                .outfit-head span {{ display: inline-flex; align-items: center; height: 22px; padding: 0 7px; border: 1px solid #d9dee5; border-radius: 6px; background: #fff; color: #56606b; font-size: 12px; }}
                .outfit-color {{ min-width: 0; }}
                .outfit-note {{ min-width: 0; color: #56606b; font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
                .event-strip {{ min-width: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 8px; }}
                .event-tile {{ min-width: 0; display: grid; grid-template-columns: 82px 1fr; gap: 8px; padding: 8px; border: 1px solid #e2e7ee; border-radius: 6px; background: #fbfcfd; }}
                .changed-event {{ border-color: #b7cbe8; background: #f7fbff; }}
                .event-media {{ width: 82px; height: 72px; display: grid; grid-template-columns: 52px 26px; gap: 4px; }}
                .body-img {{ width: 52px; height: 72px; object-fit: cover; border-radius: 5px; background: #e8ecf1; }}
                .face-img {{ width: 26px; height: 26px; object-fit: cover; border-radius: 5px; background: #e8ecf1; }}
                .placeholder {{ background: repeating-linear-gradient(45deg, #e8ecf1, #e8ecf1 7px, #dde3ea 7px, #dde3ea 14px); }}
                .event-copy {{ min-width: 0; display: grid; gap: 4px; align-content: start; }}
                .event-copy strong, .event-copy span {{ min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
                .event-copy strong {{ font-size: 12px; }}
                .part-line {{ display: flex; align-items: center; gap: 5px; font-size: 12px; }}
                .part-line b {{ flex: 0 0 auto; font-size: 12px; color: #39424e; }}
                .part-line.changed {{ color: #174a86; }}
                .arrow {{ color: #707b87; }}
                .muted, .empty {{ color: #707b87; }}
                .empty {{ margin: 0; padding: 10px 0; font-size: 13px; }}
                @media (max-width: 760px) {{
                    main {{ padding: 12px; }}
                    .topbar {{ display: grid; align-items: start; }}
                    .session-row {{ grid-template-columns: 1fr; }}
                    .outfit-row {{ grid-template-columns: 1fr; }}
                    .session-colors {{ grid-template-columns: 38px 1fr; }}
                }}
            </style>
        </head>
        <body>
            <main>
                <div class="topbar">
                    <h1>Appearance Sessions</h1>
                    <div class="summary">
                        <span>{_h(scope_label)}</span>
                        <span>{len(sessions)} sessions</span>
                        <span>{assigned_event_count} assigned events</span>
                        <span>{changed_event_count} normalized changes</span>
                        {scope_tabs}
                    </div>
                </div>
                {body}
            </main>
        </body>
        </html>
        """
    )


@router.get("/person-clothing-labels")
def get_manual_person_clothing_labels():
    data = _load_manual_clothing_labels()
    return data | {"path": str(_MANUAL_LABEL_PATH)}


@router.get("/appearance-session-labels")
def get_manual_appearance_session_labels():
    data = _load_manual_appearance_session_labels()
    return data | {"path": str(_MANUAL_SESSION_LABEL_PATH)}


@router.get("/outfit-labels")
def get_manual_outfit_labels():
    data = _load_manual_outfit_labels()
    return data | {"path": str(_MANUAL_OUTFIT_LABEL_PATH)}


@router.get("/event-outfit-groups")
def get_manual_event_outfit_groups():
    data = _load_manual_event_outfit_groups()
    return data | {"path": str(_MANUAL_EVENT_OUTFIT_GROUP_PATH)}


@router.get("/gender-presentation-labels")
def get_manual_gender_presentation_labels():
    data = _load_manual_gender_presentation_labels()
    return data | {"path": str(_MANUAL_GENDER_PRESENTATION_LABEL_PATH)}


@router.get("/person-glasses-labels")
def get_manual_person_glasses_labels():
    data = _load_manual_person_glasses_labels()
    return data | {"path": str(_MANUAL_PERSON_GLASSES_LABEL_PATH)}


@router.get("/glasses-status-profiles")
def get_glasses_status_profiles():
    return glasses_status_service.load_profiles()


@router.get("/glasses-status-profiles/evaluation")
def get_glasses_status_profile_evaluation():
    return glasses_status_service.evaluate_profiles()


@router.post("/glasses-status-profiles/rebuild")
def rebuild_glasses_status_profiles(
    include_candidates: bool = Form(True),
    sample_count: int = Form(8),
    limit: Optional[int] = Form(None),
):
    return glasses_status_service.rebuild_profiles(
        include_candidates=include_candidates,
        sample_count=sample_count,
        limit=limit,
    )


@router.get("/gender-presentation-profiles")
def get_gender_presentation_profiles():
    return gender_presentation_service.load_profiles()


@router.get("/gender-presentation-profiles/evaluation")
def get_gender_presentation_profile_evaluation():
    return gender_presentation_service.evaluate_profiles()


@router.post("/gender-presentation-profiles/rebuild")
def rebuild_gender_presentation_profiles(
    include_candidates: bool = Form(True),
    sample_count: int = Form(8),
    limit: Optional[int] = Form(None),
):
    return gender_presentation_service.rebuild_profiles(
        include_candidates=include_candidates,
        sample_count=sample_count,
        limit=limit,
    )


@router.post("/outfit-labels")
async def save_manual_outfit_labels(request: Request):
    payload = await request.json()
    labels = payload.get("labels") if isinstance(payload, dict) else None
    if not isinstance(labels, list):
        raise HTTPException(status_code=400, detail="labels must be a list")

    allowed_colors = set(settings.clothing_color_labels)
    allowed_statuses = set(_SESSION_REVIEW_STATUS_LABELS)
    distance_threshold = 0.42
    for label in labels:
        if isinstance(label, dict) and label.get("distance_threshold") is not None:
            try:
                distance_threshold = max(0.1, min(float(label.get("distance_threshold")), 0.9))
            except (TypeError, ValueError):
                distance_threshold = 0.42
            break
    group_lookup = {
        group["outfit_id"]: group
        for group in outfit_service.build_outfit_groups(distance_threshold=distance_threshold)
    }
    now = _utc_now()
    data = _load_manual_outfit_labels()
    saved = 0

    for label in labels:
        if not isinstance(label, dict):
            continue
        outfit_id = str(label.get("outfit_id") or "")
        group = group_lookup.get(outfit_id)
        if not group:
            raise HTTPException(status_code=400, detail=f"unknown outfit_id: {outfit_id}")

        upper_color = str(label.get("upper_color") or "unknown")
        if upper_color not in allowed_colors:
            raise HTTPException(status_code=400, detail=f"unsupported color for outfit_id: {outfit_id}")

        review_status = str(label.get("review_status") or "unreviewed")
        if review_status not in allowed_statuses:
            raise HTTPException(status_code=400, detail=f"unsupported review_status for outfit_id: {outfit_id}")

        sample_event_ids = [
            str(item)
            for item in label.get("sample_event_ids", [])
            if isinstance(item, str) and item
        ]
        sample_observation_ids = [
            str(item)
            for item in label.get("sample_observation_ids", [])
            if isinstance(item, str) and item
        ]
        group_event_ids = {str(event.get("event_id") or "") for event in group.get("events") or []}
        group_observation_ids = {
            str(sample.get("observation_id") or "")
            for sample in group.get("samples") or []
            if sample.get("observation_id")
        }
        split_assignments = []
        for assignment in label.get("split_assignments", []):
            if not isinstance(assignment, dict):
                continue
            event_id = str(assignment.get("event_id") or "")
            observation_id = str(assignment.get("observation_id") or "")
            split_group = str(assignment.get("split_group") or "A")
            if split_group not in _OUTFIT_SPLIT_GROUPS:
                split_group = "A"
            if event_id and event_id not in group_event_ids:
                continue
            if observation_id and observation_id not in group_observation_ids:
                continue
            split_assignments.append(
                {
                    "event_id": event_id,
                    "observation_id": observation_id,
                    "split_group": split_group,
                }
            )
        split_groups = _manual_split_groups(split_assignments)
        manual_split_required = bool(label.get("manual_split_required")) or len(split_groups) > 1
        raw_split_group_labels = label.get("split_group_labels") or label.get("manual_split_group_labels") or {}
        if isinstance(raw_split_group_labels, dict):
            split_group_label_items = []
            for split_group, group_label in raw_split_group_labels.items():
                if isinstance(group_label, dict):
                    item = dict(group_label)
                    item["split_group"] = split_group
                    split_group_label_items.append(item)
        elif isinstance(raw_split_group_labels, list):
            split_group_label_items = [
                group_label
                for group_label in raw_split_group_labels
                if isinstance(group_label, dict)
            ]
        else:
            split_group_label_items = []

        split_group_label_lookup = {}
        for group_label in split_group_label_items:
            split_group = str(group_label.get("split_group") or "")
            if split_group not in _OUTFIT_SPLIT_GROUPS or split_group == "exclude":
                continue
            group_upper_color = str(group_label.get("upper_color") or upper_color or "unknown")
            if group_upper_color not in allowed_colors:
                raise HTTPException(
                    status_code=400,
                    detail=f"unsupported split upper_color for outfit_id: {outfit_id}, group: {split_group}",
                )
            split_group_label_lookup[split_group] = {
                "split_group": split_group,
                "upper_visible": bool(group_label.get("upper_visible", label.get("upper_visible"))),
                "upper_color": group_upper_color,
                "note": str(group_label.get("note") or "").strip(),
            }

        manual_split_group_labels = {}
        if manual_split_required:
            for split_group, group_data in split_groups.items():
                group_label = split_group_label_lookup.get(split_group, {})
                manual_split_group_labels[split_group] = {
                    "split_group": split_group,
                    "upper_visible": bool(group_label.get("upper_visible", label.get("upper_visible"))),
                    "upper_color": str(group_label.get("upper_color") or upper_color or "unknown"),
                    "sample_count": int(group_data.get("sample_count") or 0),
                    "sample_event_ids": group_data.get("sample_event_ids") or [],
                    "sample_observation_ids": group_data.get("sample_observation_ids") or [],
                    "note": str(group_label.get("note") or "").strip(),
                }

        snapshot_refs = _manual_sample_refs(
            sample_event_ids=sample_event_ids,
            sample_observation_ids=sample_observation_ids,
            assignments=split_assignments,
            group_field="split_group",
        )
        sample_snapshots = _snapshot_manual_samples("manual_outfit_labels", outfit_id, snapshot_refs)

        data["labels"][outfit_id] = {
            "outfit_id": outfit_id,
            "person_id": group.get("person_id"),
            "identity_valid": bool(label.get("identity_valid", True)),
            "outfit_valid": bool(label.get("outfit_valid", True)) and not manual_split_required,
            "manual_split_required": manual_split_required,
            "manual_split_assignments": split_assignments,
            "manual_split_groups": split_groups,
            "manual_split_group_labels": manual_split_group_labels,
            "manual_split_group_count": len(split_groups),
            "upper_visible": bool(label.get("upper_visible")),
            "upper_color": upper_color,
            "review_status": review_status,
            "note": str(label.get("note") or "").strip(),
            "model_upper_color": group.get("model_upper_color") or "unknown",
            "model_upper_color_confidence": group.get("model_upper_color_confidence"),
            "model_upper_color_counts": group.get("model_upper_color_counts") or {},
            "event_count": int(group.get("event_count") or 0),
            "source_session_ids": group.get("source_session_ids") or [],
            "camera_ids": group.get("camera_ids") or [],
            "sample_event_ids": sample_event_ids,
            "sample_observation_ids": sample_observation_ids,
            "sample_snapshot_version": _MANUAL_SAMPLE_SNAPSHOT_VERSION,
            "sample_snapshot_count": _snapshot_count(sample_snapshots),
            "sample_snapshots": sample_snapshots,
            "grouping_version": group.get("grouping_version") or outfit_service.OUTFIT_GROUPING_VERSION,
            "distance_threshold": distance_threshold,
            "source": "manual_outfit_review",
            "saved_at": now,
        }
        saved += 1

    data["updated_at"] = now
    _save_manual_outfit_labels(data)
    return {
        "saved": saved,
        "updated_at": now,
        "path": str(_MANUAL_OUTFIT_LABEL_PATH),
    }


@router.post("/outfit-labels/person-groups")
async def save_manual_person_outfit_groups(request: Request):
    payload = await request.json()
    labels = payload.get("labels") if isinstance(payload, dict) else None
    if not isinstance(labels, list):
        raise HTTPException(status_code=400, detail="labels must be a list")

    allowed_colors = set(settings.clothing_color_labels)
    allowed_statuses = set(_SESSION_REVIEW_STATUS_LABELS)
    person_ids = {person["person_id"] for person in db.list_persons()}
    now = _utc_now()
    data = _load_manual_outfit_labels()
    saved = 0

    for label in labels:
        if not isinstance(label, dict):
            continue
        person_id = str(label.get("person_id") or "")
        if person_id not in person_ids:
            raise HTTPException(status_code=400, detail=f"unknown person_id: {person_id}")

        review_status = str(label.get("review_status") or "unreviewed")
        if review_status not in allowed_statuses:
            raise HTTPException(status_code=400, detail=f"unsupported review_status for person_id: {person_id}")

        person_events = db.list_events(person_id=person_id, identified=True, limit=5000)
        person_event_ids = {str(event.get("event_id") or "") for event in person_events}
        person_observation_ids = {
            str(event.get("representative_observation_id") or "")
            for event in person_events
            if event.get("representative_observation_id")
        }

        split_assignments = []
        for assignment in label.get("split_assignments", []):
            if not isinstance(assignment, dict):
                continue
            event_id = str(assignment.get("event_id") or "")
            observation_id = str(assignment.get("observation_id") or "")
            split_group = str(assignment.get("split_group") or "unassigned")
            if split_group not in _MANUAL_OUTFIT_GROUPS:
                split_group = "unassigned"
            if event_id and event_id not in person_event_ids:
                continue
            if observation_id and observation_id not in person_observation_ids:
                continue
            split_assignments.append(
                {
                    "event_id": event_id,
                    "observation_id": observation_id,
                    "split_group": split_group,
                }
            )

        split_groups = _manual_split_groups(split_assignments)
        raw_split_group_labels = label.get("split_group_labels") or label.get("manual_split_group_labels") or {}
        if isinstance(raw_split_group_labels, dict):
            split_group_label_items = []
            for split_group, group_label in raw_split_group_labels.items():
                if isinstance(group_label, dict):
                    item = dict(group_label)
                    item["split_group"] = split_group
                    split_group_label_items.append(item)
        elif isinstance(raw_split_group_labels, list):
            split_group_label_items = [
                group_label
                for group_label in raw_split_group_labels
                if isinstance(group_label, dict)
            ]
        else:
            split_group_label_items = []

        split_group_label_lookup = {}
        for group_label in split_group_label_items:
            split_group = str(group_label.get("split_group") or "")
            if split_group not in _OUTFIT_SPLIT_GROUPS or split_group == "exclude":
                continue
            upper_color = str(group_label.get("upper_color") or "unknown")
            if upper_color not in allowed_colors:
                raise HTTPException(
                    status_code=400,
                    detail=f"unsupported split upper_color for person_id: {person_id}, group: {split_group}",
                )
            split_group_label_lookup[split_group] = {
                "split_group": split_group,
                "upper_visible": bool(group_label.get("upper_visible", upper_color != "unknown")),
                "upper_color": upper_color,
                "note": str(group_label.get("note") or "").strip(),
            }

        manual_split_group_labels = {}
        for split_group, group_data in split_groups.items():
            group_label = split_group_label_lookup.get(split_group, {})
            manual_split_group_labels[split_group] = {
                "split_group": split_group,
                "upper_visible": bool(group_label.get("upper_visible", True)),
                "upper_color": str(group_label.get("upper_color") or "unknown"),
                "sample_count": int(group_data.get("sample_count") or 0),
                "sample_event_ids": group_data.get("sample_event_ids") or [],
                "sample_observation_ids": group_data.get("sample_observation_ids") or [],
                "note": str(group_label.get("note") or "").strip(),
            }

        sample_event_ids = [
            str(item)
            for item in label.get("sample_event_ids", [])
            if isinstance(item, str) and item
        ]
        sample_observation_ids = [
            str(item)
            for item in label.get("sample_observation_ids", [])
            if isinstance(item, str) and item
        ]
        snapshot_refs = _manual_sample_refs(
            sample_event_ids=sample_event_ids,
            sample_observation_ids=sample_observation_ids,
            assignments=split_assignments,
            group_field="split_group",
        )
        sample_snapshots = _snapshot_manual_samples("manual_person_outfit_groups", person_id, snapshot_refs)

        label_id = _manual_person_outfit_label_id(person_id)
        data["labels"][label_id] = {
            "label_id": label_id,
            "person_id": person_id,
            "source": "manual_person_outfit_grouping",
            "manual_grouping": True,
            "identity_valid": bool(label.get("identity_valid", True)),
            "manual_split_required": len(split_groups) > 1,
            "manual_split_assignments": split_assignments,
            "manual_split_groups": split_groups,
            "manual_split_group_labels": manual_split_group_labels,
            "manual_split_group_count": len(split_groups),
            "review_status": review_status,
            "note": str(label.get("note") or "").strip(),
            "event_count": len(person_events),
            "sample_event_ids": sample_event_ids,
            "sample_observation_ids": sample_observation_ids,
            "sample_snapshot_version": _MANUAL_SAMPLE_SNAPSHOT_VERSION,
            "sample_snapshot_count": _snapshot_count(sample_snapshots),
            "sample_snapshots": sample_snapshots,
            "saved_at": now,
        }
        saved += 1

    data["updated_at"] = now
    _save_manual_outfit_labels(data)
    return {
        "saved": saved,
        "updated_at": now,
        "path": str(_MANUAL_OUTFIT_LABEL_PATH),
    }


@router.post("/event-outfit-groups")
async def save_manual_event_outfit_groups(request: Request):
    payload = await request.json()
    labels = payload.get("labels") if isinstance(payload, dict) else None
    if not isinstance(labels, list):
        raise HTTPException(status_code=400, detail="labels must be a list")

    allowed_colors = set(settings.clothing_color_labels)
    allowed_statuses = set(_SESSION_REVIEW_STATUS_LABELS)
    person_ids = {person["person_id"] for person in db.list_persons()}
    now = _utc_now()
    data = _load_manual_event_outfit_groups()
    saved = 0

    for label in labels:
        if not isinstance(label, dict):
            continue
        person_id = str(label.get("person_id") or "")
        if person_id not in person_ids:
            raise HTTPException(status_code=400, detail=f"unknown person_id: {person_id}")

        review_status = str(label.get("review_status") or "unreviewed")
        if review_status not in allowed_statuses:
            raise HTTPException(status_code=400, detail=f"unsupported review_status for person_id: {person_id}")

        person_events = db.list_events(person_id=person_id, identified=True, limit=10000)
        event_lookup = {
            str(event.get("event_id") or ""): event
            for event in person_events
            if event.get("event_id")
        }

        assignments = []
        for assignment in label.get("assignments", []):
            if not isinstance(assignment, dict):
                continue
            event_id = str(assignment.get("event_id") or "")
            if event_id not in event_lookup:
                continue
            event = event_lookup[event_id]
            manual_group = str(assignment.get("manual_group") or "unassigned")
            if manual_group not in _MANUAL_OUTFIT_GROUPS:
                manual_group = "unassigned"
            assignments.append(
                {
                    "event_id": event_id,
                    "observation_id": str(event.get("representative_observation_id") or ""),
                    "appearance_session_id": str(event.get("appearance_session_id") or ""),
                    "camera_id": str(event.get("camera_id") or ""),
                    "time_label": _event_time_label(event),
                    "manual_group": manual_group,
                    "model_upper_color": str(
                        event.get("normalized_upper_color")
                        or event.get("upper_color")
                        or "unknown"
                    ),
                    "model_upper_color_confidence": event.get("normalized_upper_color_confidence")
                    or event.get("upper_color_confidence"),
                }
            )

        assignments.sort(
            key=lambda item: (
                event_lookup[item["event_id"]].get("start_time") or "",
                float(event_lookup[item["event_id"]].get("start_timestamp_sec") or 0.0),
                item["event_id"],
            )
        )

        raw_group_labels = label.get("group_labels") or label.get("manual_group_labels") or {}
        if isinstance(raw_group_labels, dict):
            group_label_items = []
            for group_key, group_label in raw_group_labels.items():
                if isinstance(group_label, dict):
                    item = dict(group_label)
                    item["manual_group"] = group_key
                    group_label_items.append(item)
        elif isinstance(raw_group_labels, list):
            group_label_items = [
                group_label
                for group_label in raw_group_labels
                if isinstance(group_label, dict)
            ]
        else:
            group_label_items = []

        group_label_lookup = {}
        for group_label in group_label_items:
            manual_group = str(group_label.get("manual_group") or "")
            if manual_group not in _OUTFIT_SPLIT_GROUPS or manual_group == "exclude":
                continue
            upper_color = str(group_label.get("upper_color") or "unknown")
            if upper_color not in allowed_colors:
                raise HTTPException(
                    status_code=400,
                    detail=f"unsupported group upper_color for person_id: {person_id}, group: {manual_group}",
                )
            group_label_lookup[manual_group] = {
                "manual_group": manual_group,
                "upper_visible": bool(group_label.get("upper_visible", upper_color != "unknown")),
                "upper_color": upper_color,
                "note": str(group_label.get("note") or "").strip(),
            }

        assignments_by_group: dict[str, list[dict]] = defaultdict(list)
        for assignment in assignments:
            manual_group = assignment["manual_group"]
            if manual_group in _OUTFIT_SPLIT_GROUPS and manual_group != "exclude":
                assignments_by_group[manual_group].append(assignment)

        manual_groups = {}
        for manual_group in _OUTFIT_SPLIT_GROUPS:
            if manual_group == "exclude":
                continue
            group_assignments = assignments_by_group.get(manual_group, [])
            if not group_assignments and manual_group not in group_label_lookup:
                continue
            group_label = group_label_lookup.get(manual_group, {})
            color_counts = Counter(
                assignment.get("model_upper_color") or "unknown"
                for assignment in group_assignments
            )
            manual_groups[manual_group] = {
                "manual_group": manual_group,
                "event_count": len(group_assignments),
                "event_ids": [assignment["event_id"] for assignment in group_assignments],
                "observation_ids": [
                    assignment["observation_id"]
                    for assignment in group_assignments
                    if assignment.get("observation_id")
                ],
                "appearance_session_ids": sorted(
                    {
                        assignment["appearance_session_id"]
                        for assignment in group_assignments
                        if assignment.get("appearance_session_id")
                    }
                ),
                "camera_ids": sorted(
                    {
                        assignment["camera_id"]
                        for assignment in group_assignments
                        if assignment.get("camera_id")
                    }
                ),
                "model_upper_color_counts": dict(color_counts.most_common()),
                "upper_visible": bool(group_label.get("upper_visible", True)),
                "upper_color": str(group_label.get("upper_color") or "unknown"),
                "note": str(group_label.get("note") or "").strip(),
            }

        snapshot_refs = _manual_sample_refs(assignments=assignments, group_field="manual_group")
        sample_snapshots = _snapshot_manual_samples("manual_event_outfit_groups", person_id, snapshot_refs)
        snapshots_by_group: dict[str, list[dict]] = defaultdict(list)
        for snapshot in sample_snapshots:
            if isinstance(snapshot, dict) and snapshot.get("manual_group"):
                snapshots_by_group[str(snapshot["manual_group"])].append(snapshot)
        for manual_group, snapshots in snapshots_by_group.items():
            if manual_group in manual_groups:
                manual_groups[manual_group]["sample_snapshot_count"] = _snapshot_count(snapshots)
                manual_groups[manual_group]["sample_snapshots"] = snapshots

        group_counts = Counter(assignment["manual_group"] for assignment in assignments)
        label_id = _manual_event_outfit_group_label_id(person_id)
        data["labels"][label_id] = {
            "label_id": label_id,
            "person_id": person_id,
            "source": "manual_event_outfit_grouping_eval",
            "eval_only": True,
            "manual_grouping": True,
            "identity_valid": bool(label.get("identity_valid", True)),
            "review_status": review_status,
            "note": str(label.get("note") or "").strip(),
            "event_count": len(person_events),
            "assigned_event_count": len(assignments),
            "manual_group_counts": dict(group_counts.most_common()),
            "manual_groups": manual_groups,
            "manual_assignments": assignments,
            "sample_snapshot_version": _MANUAL_SAMPLE_SNAPSHOT_VERSION,
            "sample_snapshot_count": _snapshot_count(sample_snapshots),
            "sample_snapshots": sample_snapshots,
            "saved_at": now,
        }
        saved += 1

    data["updated_at"] = now
    _save_manual_event_outfit_groups(data)
    return {
        "saved": saved,
        "updated_at": now,
        "path": str(_MANUAL_EVENT_OUTFIT_GROUP_PATH),
        "eval_only": True,
    }


def _manual_person_outfit_group_review(
    person_id: Optional[str],
    sample_count: int,
    unsaved_only: bool,
    status: Optional[str],
    limit: int,
    include_candidates: bool,
) -> HTMLResponse:
    saved_data = _load_manual_outfit_labels()
    saved_labels = saved_data.get("labels", {})
    persons = _scoped_persons(person_id, include_candidates)[: max(1, min(int(limit), 3000))]

    if unsaved_only:
        persons = [
            person
            for person in persons
            if _manual_person_outfit_label_id(person["person_id"]) not in saved_labels
        ]
    if status:
        persons = [
            person
            for person in persons
            if (
                saved_labels.get(_manual_person_outfit_label_id(person["person_id"]), {}).get("review_status")
                or "unreviewed"
            )
            == status
        ]

    person_cards = []
    saved_count = 0
    sample_total = 0
    for person in persons:
        current_person_id = person["person_id"]
        label_id = _manual_person_outfit_label_id(current_person_id)
        saved = saved_labels.get(label_id, {})
        if saved:
            saved_count += 1

        review_status = saved.get("review_status") or "unreviewed"
        identity_valid = saved.get("identity_valid", True)
        note = saved.get("note") or ""
        saved_split_assignments = saved.get("manual_split_assignments") or []
        if not isinstance(saved_split_assignments, list):
            saved_split_assignments = []
        saved_split_group_labels = saved.get("manual_split_group_labels") or {}
        if not isinstance(saved_split_group_labels, dict):
            saved_split_group_labels = {}

        split_by_exact: dict[tuple[str, str], str] = {}
        split_by_event: dict[str, str] = {}
        split_by_observation: dict[str, str] = {}
        for assignment in saved_split_assignments:
            if not isinstance(assignment, dict):
                continue
            split_group = str(assignment.get("split_group") or "unassigned")
            if split_group not in _MANUAL_OUTFIT_GROUPS:
                split_group = "unassigned"
            event_id = str(assignment.get("event_id") or "")
            observation_id = str(assignment.get("observation_id") or "")
            if event_id and observation_id:
                split_by_exact[(event_id, observation_id)] = split_group
            if event_id:
                split_by_event[event_id] = split_group
            if observation_id:
                split_by_observation[observation_id] = split_group

        face_id = person.get("representative_face_id")
        face_html = (
            f'<img class="person-face" src="/api/v1/media/face/{_h(face_id)}" alt="{_h(face_id)}">'
            if face_id
            else '<div class="person-face placeholder"></div>'
        )
        samples = _person_outfit_group_samples(current_person_id, sample_count)
        sample_total += len(samples)

        sample_tiles = []
        for sample in samples:
            sample_event_id = str(sample.get("event_id") or "")
            sample_observation_id = str(sample.get("observation_id") or "")
            split_group = (
                split_by_exact.get((sample_event_id, sample_observation_id))
                or split_by_event.get(sample_event_id)
                or split_by_observation.get(sample_observation_id)
                or "unassigned"
            )
            face = (
                f'<img class="sample-face" src="{_h(sample.get("face_url"))}" alt="">'
                if sample.get("face_url")
                else ""
            )
            sample_tiles.append(
                f"""
                <article class="sample"
                    data-event-id="{_h(sample_event_id)}"
                    data-observation-id="{_h(sample_observation_id)}">
                    <a href="{_h(sample.get("frame_url"))}" target="_blank" rel="noopener">
                        <img class="sample-body" src="{_h(sample.get("image_url"))}" alt="{_h(sample_event_id)}">
                    </a>
                    {face}
                    <div class="sample-meta">
                        <strong>{_h(sample.get("camera_id"))}</strong>
                        <span>{_h(sample.get("time_label"))}</span>
                    </div>
                    <label class="split-control">
                        <span>人工装束组</span>
                        <select class="split-group">{_manual_group_options(split_group)}</select>
                    </label>
                </article>
                """
            )

        split_label_rows = []
        for split_group_key in _OUTFIT_SPLIT_GROUPS:
            if split_group_key == "exclude":
                continue
            saved_group_label = saved_split_group_labels.get(split_group_key) or {}
            if not isinstance(saved_group_label, dict):
                saved_group_label = {}
            split_upper_color = saved_group_label.get("upper_color") or "unknown"
            split_upper_visible = saved_group_label.get("upper_visible", split_upper_color != "unknown")
            split_label_rows.append(
                f"""
                <div class="split-color-row" data-split-group="{_h(split_group_key)}">
                    <div class="split-color-head">
                        <strong>装束 {_h(split_group_key)}</strong>
                        <span class="split-count">0 样本</span>
                    </div>
                    <label class="toggle">
                        <input type="checkbox" class="split-upper-visible"{_visibility_checked(split_upper_visible)}>
                        上装可见
                    </label>
                    <label>
                        上装颜色
                        <select class="split-upper-color">{_color_options(split_upper_color)}</select>
                    </label>
                </div>
                """
            )

        person_cards.append(
            f"""
            <section class="person-group-card"
                data-person-id="{_h(current_person_id)}"
                data-label-id="{_h(label_id)}">
                <header class="person-header">
                    {face_html}
                    <div>
                        <h2 title="{_h(current_person_id)}">{_h(current_person_id)}</h2>
                        <div class="person-stats">
                            <span>{int(person.get("face_count") or 0)} faces</span>
                            <span>{len(samples)} samples</span>
                        </div>
                    </div>
                    <div class="save-box">
                        <span class="state">{_h("已保存" if saved else "未保存")}</span>
                        <button type="button" class="save-one">保存此人</button>
                    </div>
                </header>
                <div class="samples">
                    {"".join(sample_tiles) or '<p class="empty">No samples</p>'}
                </div>
                <div class="split-label-panel">
                    <div class="split-label-title">人工装束颜色</div>
                    <div class="split-label-grid">
                        {"".join(split_label_rows)}
                    </div>
                </div>
                <div class="label-form">
                    <label class="toggle">
                        <input type="checkbox" class="identity-valid"{_visibility_checked(identity_valid)}>
                        人物正确
                    </label>
                    <label>
                        审核状态
                        <select class="review-status">{_review_status_options(review_status)}</select>
                    </label>
                    <label class="note-label">
                        备注
                        <input type="text" class="note" value="{_h(note)}" placeholder="可空">
                    </label>
                </div>
            </section>
            """
        )

    body = "\n".join(person_cards) or '<p class="empty">No persons</p>'
    scope_tabs = _person_scope_tabs(
        "/api/v1/outfit-labels/review",
        include_candidates,
        mode="manual",
        person_id=person_id,
        sample_count=sample_count,
        unsaved_only=unsaved_only,
        status=status,
        limit=limit,
    )
    scope_label = "全部人物" if include_candidates else "只看稳定人物"
    return HTMLResponse(
        f"""
        <!doctype html>
        <html lang="zh-CN">
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>人工装束分组审核</title>
            <style>
                * {{ box-sizing: border-box; }}
                body {{ margin: 0; font-family: Arial, sans-serif; background: #f4f6f8; color: #20242a; }}
                main {{ max-width: 1500px; margin: 0 auto; padding: 18px; }}
                .toolbar {{ position: sticky; top: 0; z-index: 8; display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 12px 0; background: #f4f6f8; border-bottom: 1px solid #d8dee7; }}
                h1 {{ margin: 0; font-size: 22px; }}
                h2 {{ margin: 0; font-size: 15px; word-break: break-all; }}
                .summary, .person-stats, .state {{ color: #5d6875; font-size: 12px; }}
                .actions, .save-box {{ display: flex; align-items: center; gap: 10px; }}
                .scope-tabs {{ display: inline-flex; align-items: center; height: 34px; padding: 3px; border: 1px solid #cdd4df; border-radius: 7px; background: #fff; }}
                .scope-tab {{ display: inline-flex; align-items: center; height: 26px; padding: 0 10px; border-radius: 5px; color: #5d6875; text-decoration: none; font-size: 13px; }}
                .scope-tab.active {{ background: #20242a; color: #fff; }}
                button {{ height: 34px; border: 1px solid #bac3cf; border-radius: 6px; background: #fff; color: #20242a; cursor: pointer; padding: 0 12px; font-weight: 600; }}
                button.primary {{ background: #1f5f9f; border-color: #1f5f9f; color: #fff; }}
                button:disabled {{ opacity: .55; cursor: default; }}
                .status {{ min-width: 180px; color: #5d6875; font-size: 13px; text-align: right; }}
                .person-group-card {{ margin-top: 14px; border: 1px solid #d8dee7; border-radius: 8px; background: #fff; overflow: hidden; }}
                .person-header {{ display: grid; grid-template-columns: 58px 1fr auto; gap: 12px; align-items: center; padding: 12px; border-bottom: 1px solid #e5eaf1; background: #fbfcfd; }}
                .person-face {{ width: 58px; height: 58px; object-fit: cover; border-radius: 6px; background: #e8ecf1; }}
                .person-stats {{ display: flex; flex-wrap: wrap; gap: 7px; margin-top: 6px; }}
                .samples {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(138px, 1fr)); gap: 8px; padding: 10px; }}
                .sample {{ position: relative; min-width: 0; border: 1px solid #e4e9f0; border-radius: 6px; overflow: hidden; background: #fbfcfd; }}
                .sample-body {{ display: block; width: 100%; height: 180px; object-fit: cover; background: #e8ecf1; }}
                .sample-face {{ position: absolute; top: 6px; right: 6px; width: 34px; height: 34px; object-fit: cover; border-radius: 5px; border: 1px solid #fff; background: #e8ecf1; }}
                .sample-meta {{ display: grid; gap: 3px; padding: 7px; }}
                .sample-meta strong, .sample-meta span {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
                .sample-meta strong {{ font-size: 12px; }}
                .sample-meta span {{ color: #5d6875; font-size: 12px; }}
                .split-control {{ display: grid; gap: 4px; padding: 0 7px 7px; }}
                .split-control span {{ color: #5d6875; font-size: 12px; }}
                .split-control select {{ width: 100%; height: 30px; font-size: 12px; }}
                .split-label-panel {{ padding: 10px; border-top: 1px solid #eadbc7; background: #fffaf3; }}
                .split-label-title {{ margin-bottom: 8px; color: #7a4e12; font-size: 13px; font-weight: 700; }}
                .split-label-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 8px; }}
                .split-color-row {{ display: grid; gap: 7px; padding: 8px; border: 1px solid #eadbc7; border-radius: 6px; background: #fff; opacity: .45; }}
                .split-color-row.active {{ opacity: 1; border-color: #c98a2c; }}
                .split-color-row select {{ width: 100%; }}
                .split-color-head {{ display: flex; justify-content: space-between; align-items: center; gap: 8px; }}
                .split-color-head strong {{ font-size: 13px; }}
                .split-count {{ color: #7a4e12; font-size: 12px; }}
                .label-form {{ display: grid; grid-template-columns: 92px minmax(120px, 160px) 1fr; gap: 9px; align-items: end; padding: 10px; border-top: 1px solid #e7ecf2; }}
                label {{ display: grid; gap: 5px; font-size: 12px; color: #5d6875; }}
                .toggle {{ display: flex; align-items: center; gap: 6px; height: 34px; color: #20242a; }}
                select, input[type="text"] {{ height: 34px; border: 1px solid #c8d0da; border-radius: 6px; background: #fff; padding: 0 8px; color: #20242a; min-width: 0; }}
                .note-label {{ min-width: 180px; }}
                .empty {{ margin: 0; padding: 14px; color: #5d6875; }}
                .placeholder {{ background: repeating-linear-gradient(45deg, #e8ecf1, #e8ecf1 7px, #dde3ea 7px, #dde3ea 14px); }}
                @media (max-width: 940px) {{
                    main {{ padding: 10px; }}
                    .toolbar, .person-header {{ grid-template-columns: 1fr; display: grid; align-items: start; }}
                    .label-form {{ grid-template-columns: 1fr 1fr; }}
                    .note-label {{ grid-column: 1 / -1; }}
                    .status {{ text-align: left; }}
                }}
            </style>
        </head>
        <body>
            <main>
                <div class="toolbar">
                    <div>
                        <h1>人工装束分组审核</h1>
                        <div class="summary">{_h(scope_label)} · {len(persons)} persons · {sample_total} samples · saved {saved_count} · file: {_h(str(_MANUAL_OUTFIT_LABEL_PATH))}</div>
                    </div>
                    <div class="actions">
                        {scope_tabs}
                        <button type="button" id="saveAll" class="primary">保存全部</button>
                        <span id="status" class="status">等待审核</span>
                    </div>
                </div>
                {body}
            </main>
            <script>
                const endpoint = "/api/v1/outfit-labels/person-groups";
                function collectCard(card) {{
                    const samples = Array.from(card.querySelectorAll(".sample"));
                    const splitGroupLabels = Array.from(card.querySelectorAll(".split-color-row")).map(row => ({{
                        split_group: row.dataset.splitGroup,
                        upper_visible: row.querySelector(".split-upper-visible").checked,
                        upper_color: row.querySelector(".split-upper-color").value,
                        sample_count: Number(row.dataset.sampleCount || "0"),
                    }})).filter(item => item.sample_count > 0);
                    return {{
                        person_id: card.dataset.personId,
                        identity_valid: card.querySelector(".identity-valid").checked,
                        review_status: card.querySelector(".review-status").value,
                        note: card.querySelector(".note").value,
                        sample_event_ids: samples.map(item => item.dataset.eventId).filter(Boolean),
                        sample_observation_ids: samples.map(item => item.dataset.observationId).filter(Boolean),
                        split_assignments: samples.map(item => ({{
                            event_id: item.dataset.eventId || "",
                            observation_id: item.dataset.observationId || "",
                            split_group: item.querySelector(".split-group").value || "unassigned",
                        }})).filter(item => item.event_id || item.observation_id),
                        split_group_labels: splitGroupLabels,
                    }};
                }}
                function syncGroupState(card) {{
                    const counts = {{}};
                    card.querySelectorAll(".sample").forEach(sample => {{
                        const splitGroup = sample.querySelector(".split-group").value || "unassigned";
                        if (!splitGroup || splitGroup === "unassigned" || splitGroup === "exclude") return;
                        counts[splitGroup] = (counts[splitGroup] || 0) + 1;
                    }});
                    card.querySelectorAll(".split-color-row").forEach(row => {{
                        const count = counts[row.dataset.splitGroup] || 0;
                        row.dataset.sampleCount = String(count);
                        const countLabel = row.querySelector(".split-count");
                        if (countLabel) countLabel.textContent = `${{count}} 样本`;
                        row.classList.toggle("active", count > 0);
                    }});
                }}
                async function saveLabels(cards) {{
                    const status = document.getElementById("status");
                    status.textContent = "保存中...";
                    const labels = cards.map(collectCard);
                    const response = await fetch(endpoint, {{
                        method: "POST",
                        headers: {{ "Content-Type": "application/json" }},
                        body: JSON.stringify({{ labels }}),
                    }});
                    const body = await response.json();
                    if (!response.ok) {{
                        throw new Error(body.detail || "保存失败");
                    }}
                    cards.forEach(card => {{
                        const state = card.querySelector(".state");
                        if (state) state.textContent = "已保存";
                    }});
                    status.textContent = `已保存 ${{body.saved}} 人`;
                }}
                document.querySelectorAll(".person-group-card").forEach(card => {{
                    syncGroupState(card);
                    card.querySelectorAll(".split-group").forEach(select => {{
                        select.addEventListener("change", () => syncGroupState(card));
                    }});
                }});
                document.getElementById("saveAll").addEventListener("click", async () => {{
                    const button = document.getElementById("saveAll");
                    button.disabled = true;
                    try {{
                        await saveLabels(Array.from(document.querySelectorAll(".person-group-card")));
                    }} catch (error) {{
                        document.getElementById("status").textContent = error.message;
                    }} finally {{
                        button.disabled = false;
                    }}
                }});
                document.querySelectorAll(".save-one").forEach(button => {{
                    button.addEventListener("click", async () => {{
                        button.disabled = true;
                        try {{
                            await saveLabels([button.closest(".person-group-card")]);
                        }} catch (error) {{
                            document.getElementById("status").textContent = error.message;
                        }} finally {{
                            button.disabled = false;
                        }}
                    }});
                }});
            </script>
        </body>
        </html>
        """
    )


@router.get("/event-outfit-groups/review", response_class=HTMLResponse)
def manual_event_outfit_group_review(
    person_id: Optional[str] = None,
    unsaved_only: bool = False,
    status: Optional[str] = None,
    limit: int = 1000,
    event_limit: int = 10000,
    include_candidates: bool = True,
):
    saved_data = _load_manual_event_outfit_groups()
    saved_labels = saved_data.get("labels", {})
    persons = _scoped_persons(person_id, include_candidates)[: max(1, min(int(limit), 3000))]

    if unsaved_only:
        persons = [
            person
            for person in persons
            if _manual_event_outfit_group_label_id(person["person_id"]) not in saved_labels
        ]
    if status:
        persons = [
            person
            for person in persons
            if (
                saved_labels.get(_manual_event_outfit_group_label_id(person["person_id"]), {}).get("review_status")
                or "unreviewed"
            )
            == status
        ]

    saved_count = 0
    total_event_count = 0
    person_cards = []
    max_events = max(1, min(int(event_limit), 10000))

    for person in persons:
        current_person_id = person["person_id"]
        label_id = _manual_event_outfit_group_label_id(current_person_id)
        saved = saved_labels.get(label_id, {})
        if saved:
            saved_count += 1

        review_status = saved.get("review_status") or "unreviewed"
        identity_valid = saved.get("identity_valid", True)
        note = saved.get("note") or ""
        saved_assignments = saved.get("manual_assignments") or []
        if not isinstance(saved_assignments, list):
            saved_assignments = []
        saved_by_event = {}
        for assignment in saved_assignments:
            if not isinstance(assignment, dict):
                continue
            event_id = str(assignment.get("event_id") or "")
            manual_group = str(assignment.get("manual_group") or "unassigned")
            if event_id and manual_group in _MANUAL_OUTFIT_GROUPS:
                saved_by_event[event_id] = manual_group

        saved_group_labels = saved.get("manual_groups") or {}
        if not isinstance(saved_group_labels, dict):
            saved_group_labels = {}

        face_id = person.get("representative_face_id")
        face_html = (
            f'<img class="person-face" src="/api/v1/media/face/{_h(face_id)}" alt="{_h(face_id)}">'
            if face_id
            else '<div class="person-face placeholder"></div>'
        )

        events = sorted(
            db.list_events(person_id=current_person_id, identified=True, limit=max_events),
            key=lambda event: (
                event.get("start_time") or "",
                float(event.get("start_timestamp_sec") or 0.0),
                event.get("event_id") or "",
            ),
        )
        total_event_count += len(events)
        event_tiles = []
        for event in events:
            event_id = str(event.get("event_id") or "")
            observation_id = str(event.get("representative_observation_id") or "")
            group_value = saved_by_event.get(event_id, "unassigned")
            if group_value not in _MANUAL_OUTFIT_GROUPS:
                group_value = "unassigned"
            image_url = (
                event.get("representative_body_crop_url")
                or f"/api/v1/media/event/body/{_h(event_id)}"
            )
            frame_url = (
                event.get("representative_frame_url")
                or f"/api/v1/media/event/frame/{_h(event_id)}"
            )
            event_face_id = event.get("representative_face_id")
            face_url = (
                event.get("representative_face_crop_url")
                or (f"/api/v1/media/face/{_h(event_face_id)}" if event_face_id else "")
            )
            session_id = str(event.get("appearance_session_id") or "")
            upper_color = (
                event.get("normalized_upper_color")
                or event.get("upper_color")
                or "unknown"
            )
            upper_confidence = (
                event.get("normalized_upper_color_confidence")
                or event.get("upper_color_confidence")
            )
            face_thumb = (
                f'<img class="event-face" src="{_h(face_url)}" alt="">'
                if face_url
                else ""
            )
            event_tiles.append(
                f"""
                <article class="event-card"
                    data-event-id="{_h(event_id)}"
                    data-observation-id="{_h(observation_id)}"
                    data-group="{_h(group_value)}">
                    <a class="event-image-link" href="{_h(frame_url)}" target="_blank" rel="noopener">
                        <img class="event-body" src="{_h(image_url)}" alt="{_h(event_id)}">
                    </a>
                    {face_thumb}
                    <div class="event-meta">
                        <strong title="{_h(event_id)}">event:{_h(_short_id(event_id))}</strong>
                        <span title="{_h(event.get("camera_id"))}">{_h(event.get("camera_id"))}</span>
                        <span>{_h(_event_time_label(event))}</span>
                        <span title="{_h(session_id)}">session:{_h(_short_id(session_id) or "-")}</span>
                        {_color_chip(upper_color, upper_confidence)}
                    </div>
                    <label class="group-control">
                        <span>装束组</span>
                        <select class="manual-group">{_manual_group_options(group_value)}</select>
                    </label>
                </article>
                """
            )

        group_label_rows = []
        for group_key in _OUTFIT_SPLIT_GROUPS:
            if group_key == "exclude":
                continue
            saved_group_label = saved_group_labels.get(group_key) or {}
            if not isinstance(saved_group_label, dict):
                saved_group_label = {}
            group_upper_color = saved_group_label.get("upper_color") or "unknown"
            group_upper_visible = saved_group_label.get("upper_visible", group_upper_color != "unknown")
            group_note = saved_group_label.get("note") or ""
            group_label_rows.append(
                f"""
                <div class="group-label-row" data-manual-group="{_h(group_key)}">
                    <div class="group-label-head">
                        <strong>装束 {_h(group_key)}</strong>
                        <span class="group-count">0 events</span>
                    </div>
                    <label class="toggle">
                        <input type="checkbox" class="group-upper-visible"{_visibility_checked(group_upper_visible)}>
                        上装可见
                    </label>
                    <label>
                        上装颜色
                        <select class="group-upper-color">{_color_options(group_upper_color)}</select>
                    </label>
                    <label>
                        备注
                        <input type="text" class="group-note" value="{_h(group_note)}" placeholder="可空">
                    </label>
                </div>
                """
            )

        person_cards.append(
            f"""
            <section class="person-event-card"
                data-person-id="{_h(current_person_id)}"
                data-label-id="{_h(label_id)}">
                <header class="person-header">
                    {face_html}
                    <div class="person-title">
                        <h2 title="{_h(current_person_id)}">{_h(current_person_id)}</h2>
                        <div class="person-stats">
                            <span>{int(person.get("face_count") or 0)} faces</span>
                            <span>{len(events)} events</span>
                            <span class="card-group-summary">0 groups</span>
                        </div>
                    </div>
                    <div class="save-box">
                        <span class="state">{_h("已保存" if saved else "未保存")}</span>
                        <button type="button" class="save-one">保存此人</button>
                    </div>
                </header>
                <div class="events-grid">
                    {"".join(event_tiles) or '<p class="empty">No events</p>'}
                </div>
                <div class="group-label-panel">
                    <div class="group-label-grid">
                        {"".join(group_label_rows)}
                    </div>
                </div>
                <div class="label-form">
                    <label class="toggle">
                        <input type="checkbox" class="identity-valid"{_visibility_checked(identity_valid)}>
                        人物正确
                    </label>
                    <label>
                        审核状态
                        <select class="review-status">{_review_status_options(review_status)}</select>
                    </label>
                    <label class="note-label">
                        备注
                        <input type="text" class="note" value="{_h(note)}" placeholder="可空">
                    </label>
                </div>
            </section>
            """
        )

    body = "\n".join(person_cards) or '<p class="empty">No persons</p>'
    scope_tabs = _person_scope_tabs(
        "/api/v1/event-outfit-groups/review",
        include_candidates,
        person_id=person_id,
        unsaved_only=unsaved_only,
        status=status,
        limit=limit,
        event_limit=event_limit,
    )
    scope_label = "全部人物" if include_candidates else "只看稳定人物"
    return HTMLResponse(
        f"""
        <!doctype html>
        <html lang="zh-CN">
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>人物内事件装束分组评估</title>
            <style>
                * {{ box-sizing: border-box; }}
                body {{ margin: 0; font-family: Arial, sans-serif; background: #f4f6f8; color: #20242a; }}
                main {{ max-width: 1560px; margin: 0 auto; padding: 18px; }}
                .toolbar {{ position: sticky; top: 0; z-index: 10; display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 12px 0; background: #f4f6f8; border-bottom: 1px solid #d8dee7; }}
                h1 {{ margin: 0; font-size: 22px; }}
                h2 {{ margin: 0; font-size: 15px; word-break: break-all; }}
                .summary, .person-stats, .state {{ color: #5d6875; font-size: 12px; }}
                .actions, .save-box, .person-stats {{ display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }}
                .scope-tabs {{ display: inline-flex; align-items: center; height: 34px; padding: 3px; border: 1px solid #cdd4df; border-radius: 7px; background: #fff; }}
                .scope-tab {{ display: inline-flex; align-items: center; height: 26px; padding: 0 10px; border-radius: 5px; color: #5d6875; text-decoration: none; font-size: 13px; }}
                .scope-tab.active {{ background: #20242a; color: #fff; }}
                button {{ height: 34px; border: 1px solid #bac3cf; border-radius: 6px; background: #fff; color: #20242a; cursor: pointer; padding: 0 12px; font-weight: 600; }}
                button.primary {{ background: #1f5f9f; border-color: #1f5f9f; color: #fff; }}
                button:disabled {{ opacity: .55; cursor: default; }}
                .status {{ min-width: 180px; color: #5d6875; font-size: 13px; text-align: right; }}
                .person-event-card {{ margin-top: 14px; border: 1px solid #d8dee7; border-radius: 8px; background: #fff; overflow: hidden; }}
                .person-header {{ display: grid; grid-template-columns: 58px 1fr auto; gap: 12px; align-items: center; padding: 12px; border-bottom: 1px solid #e5eaf1; background: #fbfcfd; }}
                .person-face {{ width: 58px; height: 58px; object-fit: cover; border-radius: 6px; background: #e8ecf1; }}
                .events-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(156px, 1fr)); gap: 8px; padding: 10px; }}
                .event-card {{ position: relative; min-width: 0; border: 1px solid #e1e7ef; border-left-width: 4px; border-radius: 6px; overflow: hidden; background: #fbfcfd; }}
                .event-card[data-group="A"] {{ border-left-color: #1f77b4; }}
                .event-card[data-group="B"] {{ border-left-color: #2f855a; }}
                .event-card[data-group="C"] {{ border-left-color: #c2410c; }}
                .event-card[data-group="D"] {{ border-left-color: #7c3aed; }}
                .event-card[data-group="E"] {{ border-left-color: #a16207; }}
                .event-card[data-group="F"] {{ border-left-color: #be185d; }}
                .event-card[data-group="exclude"] {{ border-left-color: #6b7280; opacity: .72; }}
                .event-card[data-group="unassigned"] {{ border-left-color: #d6dde6; }}
                .event-image-link {{ display: block; }}
                .event-body {{ display: block; width: 100%; height: 178px; object-fit: cover; background: #e8ecf1; }}
                .event-face {{ position: absolute; top: 6px; right: 6px; width: 34px; height: 34px; object-fit: cover; border-radius: 5px; border: 1px solid #fff; background: #e8ecf1; }}
                .event-meta {{ display: grid; gap: 4px; padding: 7px; }}
                .event-meta strong, .event-meta span {{ min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
                .event-meta strong {{ font-size: 12px; }}
                .event-meta span {{ color: #5d6875; font-size: 12px; }}
                .color-chip {{ min-width: 0; display: inline-flex; align-items: center; gap: 6px; color: #20242a; font-size: 12px; }}
                .swatch {{ flex: 0 0 auto; width: 14px; height: 14px; border-radius: 3px; border: 1px solid #aeb6c2; }}
                .chip-meta {{ color: #707b87; }}
                .group-control {{ display: grid; gap: 4px; padding: 0 7px 7px; }}
                .group-control span {{ color: #5d6875; font-size: 12px; }}
                .group-control select {{ width: 100%; height: 30px; font-size: 12px; }}
                .group-label-panel {{ padding: 10px; border-top: 1px solid #eadbc7; background: #fffaf3; }}
                .group-label-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(185px, 1fr)); gap: 8px; }}
                .group-label-row {{ display: grid; gap: 7px; padding: 8px; border: 1px solid #eadbc7; border-radius: 6px; background: #fff; opacity: .45; }}
                .group-label-row.active {{ opacity: 1; border-color: #c98a2c; }}
                .group-label-row select {{ width: 100%; }}
                .group-label-head {{ display: flex; justify-content: space-between; align-items: center; gap: 8px; }}
                .group-label-head strong {{ font-size: 13px; }}
                .group-count {{ color: #7a4e12; font-size: 12px; }}
                .label-form {{ display: grid; grid-template-columns: 92px minmax(120px, 160px) 1fr; gap: 9px; align-items: end; padding: 10px; border-top: 1px solid #e7ecf2; }}
                label {{ display: grid; gap: 5px; font-size: 12px; color: #5d6875; }}
                .toggle {{ display: flex; align-items: center; gap: 6px; height: 34px; color: #20242a; }}
                select, input[type="text"] {{ height: 34px; border: 1px solid #c8d0da; border-radius: 6px; background: #fff; padding: 0 8px; color: #20242a; min-width: 0; }}
                .note-label {{ min-width: 180px; }}
                .empty {{ margin: 0; padding: 14px; color: #5d6875; }}
                .placeholder {{ background: repeating-linear-gradient(45deg, #e8ecf1, #e8ecf1 7px, #dde3ea 7px, #dde3ea 14px); }}
                @media (max-width: 940px) {{
                    main {{ padding: 10px; }}
                    .toolbar, .person-header {{ grid-template-columns: 1fr; display: grid; align-items: start; }}
                    .label-form {{ grid-template-columns: 1fr 1fr; }}
                    .note-label {{ grid-column: 1 / -1; }}
                    .status {{ text-align: left; }}
                }}
            </style>
        </head>
        <body>
            <main>
                <div class="toolbar">
                    <div>
                        <h1>人物内事件装束分组评估</h1>
                        <div class="summary">{_h(scope_label)} · {len(persons)} persons · {total_event_count} events · saved {saved_count} · eval-only · file: {_h(str(_MANUAL_EVENT_OUTFIT_GROUP_PATH))}</div>
                    </div>
                    <div class="actions">
                        {scope_tabs}
                        <button type="button" id="saveAll" class="primary">保存全部</button>
                        <span id="status" class="status">等待审核</span>
                    </div>
                </div>
                {body}
            </main>
            <script>
                const endpoint = "/api/v1/event-outfit-groups";
                function collectCard(card) {{
                    const events = Array.from(card.querySelectorAll(".event-card"));
                    const groupLabels = Array.from(card.querySelectorAll(".group-label-row")).map(row => ({{
                        manual_group: row.dataset.manualGroup,
                        upper_visible: row.querySelector(".group-upper-visible").checked,
                        upper_color: row.querySelector(".group-upper-color").value,
                        note: row.querySelector(".group-note").value,
                        event_count: Number(row.dataset.eventCount || "0"),
                    }})).filter(item => item.event_count > 0);
                    return {{
                        person_id: card.dataset.personId,
                        identity_valid: card.querySelector(".identity-valid").checked,
                        review_status: card.querySelector(".review-status").value,
                        note: card.querySelector(".note").value,
                        assignments: events.map(item => ({{
                            event_id: item.dataset.eventId || "",
                            observation_id: item.dataset.observationId || "",
                            manual_group: item.querySelector(".manual-group").value || "unassigned",
                        }})).filter(item => item.event_id),
                        group_labels: groupLabels,
                    }};
                }}
                function syncCard(card) {{
                    const counts = {{}};
                    card.querySelectorAll(".event-card").forEach(eventCard => {{
                        const manualGroup = eventCard.querySelector(".manual-group").value || "unassigned";
                        eventCard.dataset.group = manualGroup;
                        counts[manualGroup] = (counts[manualGroup] || 0) + 1;
                    }});
                    let activeGroupCount = 0;
                    card.querySelectorAll(".group-label-row").forEach(row => {{
                        const count = counts[row.dataset.manualGroup] || 0;
                        row.dataset.eventCount = String(count);
                        row.classList.toggle("active", count > 0);
                        const countLabel = row.querySelector(".group-count");
                        if (countLabel) countLabel.textContent = `${{count}} events`;
                        if (count > 0) activeGroupCount += 1;
                    }});
                    const summary = card.querySelector(".card-group-summary");
                    if (summary) summary.textContent = `${{activeGroupCount}} groups`;
                }}
                async function saveLabels(cards) {{
                    const status = document.getElementById("status");
                    status.textContent = "保存中...";
                    const response = await fetch(endpoint, {{
                        method: "POST",
                        headers: {{ "Content-Type": "application/json" }},
                        body: JSON.stringify({{ labels: cards.map(collectCard) }}),
                    }});
                    const body = await response.json();
                    if (!response.ok) {{
                        throw new Error(body.detail || "保存失败");
                    }}
                    cards.forEach(card => {{
                        const state = card.querySelector(".state");
                        if (state) state.textContent = "已保存";
                    }});
                    status.textContent = `已保存 ${{body.saved}} 人`;
                }}
                document.querySelectorAll(".person-event-card").forEach(card => {{
                    syncCard(card);
                    card.querySelectorAll(".manual-group").forEach(select => {{
                        select.addEventListener("change", () => syncCard(card));
                    }});
                }});
                document.getElementById("saveAll").addEventListener("click", async () => {{
                    const button = document.getElementById("saveAll");
                    button.disabled = true;
                    try {{
                        await saveLabels(Array.from(document.querySelectorAll(".person-event-card")));
                    }} catch (error) {{
                        document.getElementById("status").textContent = error.message;
                    }} finally {{
                        button.disabled = false;
                    }}
                }});
                document.querySelectorAll(".save-one").forEach(button => {{
                    button.addEventListener("click", async () => {{
                        button.disabled = true;
                        try {{
                            await saveLabels([button.closest(".person-event-card")]);
                        }} catch (error) {{
                            document.getElementById("status").textContent = error.message;
                        }} finally {{
                            button.disabled = false;
                        }}
                    }});
                }});
            </script>
        </body>
        </html>
        """
    )


@router.get("/outfit-labels/review", response_class=HTMLResponse)
def manual_outfit_label_review(
    person_id: Optional[str] = None,
    sample_count: int = 24,
    distance_threshold: float = 0.42,
    unsaved_only: bool = False,
    status: Optional[str] = None,
    limit: int = 1000,
    mode: str = "manual",
    include_candidates: bool = True,
):
    if mode != "auto":
        return _manual_person_outfit_group_review(
            person_id=person_id,
            sample_count=sample_count,
            unsaved_only=unsaved_only,
            status=status,
            limit=limit,
            include_candidates=include_candidates,
        )

    saved_data = _load_manual_outfit_labels()
    saved_labels = saved_data.get("labels", {})
    scoped_persons = _scoped_persons(person_id, include_candidates)
    scoped_person_ids = {person["person_id"] for person in scoped_persons}
    groups = outfit_service.build_outfit_groups(
        person_id=person_id,
        distance_threshold=max(0.1, min(float(distance_threshold), 0.9)),
    )
    groups = [
        group
        for group in groups
        if group.get("person_id") in scoped_person_ids
    ]
    groups = groups[: max(1, min(int(limit), 3000))]

    if unsaved_only:
        groups = [group for group in groups if group["outfit_id"] not in saved_labels]
    if status:
        groups = [
            group
            for group in groups
            if (saved_labels.get(group["outfit_id"], {}).get("review_status") or "unreviewed") == status
        ]

    session_group_counts: Counter[str] = Counter()
    for group in groups:
        for session_id in group.get("source_session_ids") or []:
            session_group_counts[session_id] += 1

    persons = {person["person_id"]: person for person in scoped_persons}
    groups_by_person: dict[str, list[dict]] = defaultdict(list)
    for group in groups:
        groups_by_person[group["person_id"]].append(group)

    person_blocks = []
    saved_count = 0
    sample_total = 0
    split_group_count = 0
    for current_person_id in sorted(groups_by_person):
        person = persons.get(current_person_id, {})
        face_id = person.get("representative_face_id")
        face_html = (
            f'<img class="person-face" src="/api/v1/media/face/{_h(face_id)}" alt="{_h(face_id)}">'
            if face_id
            else '<div class="person-face placeholder"></div>'
        )
        outfit_cards = []
        for group in sorted(groups_by_person[current_person_id], key=lambda item: (item["group_index"], item["outfit_id"])):
            outfit_id = group["outfit_id"]
            saved = saved_labels.get(outfit_id, {})
            if saved:
                saved_count += 1

            split_from_session = any(
                session_group_counts[session_id] > 1
                for session_id in group.get("source_session_ids") or []
            )
            if split_from_session:
                split_group_count += 1

            model_upper = group.get("model_upper_color") or "unknown"
            upper_color = saved.get("upper_color") or model_upper
            upper_visible = saved.get("upper_visible", model_upper != "unknown")
            review_status = saved.get("review_status") or "unreviewed"
            identity_valid = saved.get("identity_valid", True)
            manual_split_required = bool(saved.get("manual_split_required")) or int(
                saved.get("manual_split_group_count") or 0
            ) > 1
            outfit_valid = bool(saved.get("outfit_valid", True)) and not manual_split_required
            note = saved.get("note") or ""
            split_assignments = saved.get("manual_split_assignments") or []
            if not isinstance(split_assignments, list):
                split_assignments = []
            saved_split_group_labels = saved.get("manual_split_group_labels") or saved.get("split_group_labels") or {}
            if not isinstance(saved_split_group_labels, dict):
                saved_split_group_labels = {}
            split_by_exact: dict[tuple[str, str], str] = {}
            split_by_event: dict[str, str] = {}
            split_by_observation: dict[str, str] = {}
            for assignment in split_assignments:
                if not isinstance(assignment, dict):
                    continue
                split_group = str(assignment.get("split_group") or "A")
                if split_group not in _OUTFIT_SPLIT_GROUPS:
                    split_group = "A"
                event_id = str(assignment.get("event_id") or "")
                observation_id = str(assignment.get("observation_id") or "")
                if event_id and observation_id:
                    split_by_exact[(event_id, observation_id)] = split_group
                if event_id:
                    split_by_event[event_id] = split_group
                if observation_id:
                    split_by_observation[observation_id] = split_group
            samples = _sample_evenly(group.get("samples") or [], max(1, min(int(sample_count), 12)))
            sample_total += len(samples)

            chips = "".join(
                f'<span class="mini-chip">{_h(_color_label(color))}: {int(count)}</span>'
                for color, count in (group.get("model_upper_color_counts") or {}).items()
            )
            source_sessions = ", ".join(f"session:{_short_id(session_id)}" for session_id in group.get("source_session_ids") or [])
            split_badge = '<span class="split-badge">已从 session 内拆分</span>' if split_from_session else ""
            sample_tiles = []
            for sample in samples:
                sample_event_id = str(sample.get("event_id") or "")
                sample_observation_id = str(sample.get("observation_id") or "")
                split_group = (
                    split_by_exact.get((sample_event_id, sample_observation_id))
                    or split_by_event.get(sample_event_id)
                    or split_by_observation.get(sample_observation_id)
                    or "A"
                )
                conf = sample.get("model_upper_confidence")
                conf_text = f" · {float(conf):.2f}" if conf is not None else ""
                face = (
                    f'<img class="sample-face" src="{_h(sample.get("face_url"))}" alt="">'
                    if sample.get("face_url")
                    else ""
                )
                sample_tiles.append(
                    f"""
                    <article class="sample"
                        data-event-id="{_h(sample_event_id)}"
                        data-observation-id="{_h(sample_observation_id)}">
                        <a href="{_h(sample.get("frame_url"))}" target="_blank" rel="noopener">
                            <img class="sample-body" src="{_h(sample.get("image_url"))}" alt="{_h(sample_event_id)}">
                        </a>
                        {face}
                        <div class="sample-meta">
                            <strong>{_h(sample.get("camera_id"))}</strong>
                            <span>{_h(sample.get("time_label"))}</span>
                            <span>model 上装 {_h(_color_label(sample.get("model_upper_color")))}{_h(conf_text)}</span>
                            <span>{_h("session:" + _short_id(sample.get("session_id")) if sample.get("session_id") else "")}</span>
                        </div>
                        <label class="split-control">
                            <span>人工子组</span>
                            <select class="split-group">{_split_group_options(split_group)}</select>
                        </label>
                    </article>
                    """
                )

            split_label_rows = []
            for split_group_key in _OUTFIT_SPLIT_GROUPS:
                if split_group_key == "exclude":
                    continue
                saved_group_label = saved_split_group_labels.get(split_group_key) or {}
                if not isinstance(saved_group_label, dict):
                    saved_group_label = {}
                split_upper_color = saved_group_label.get("upper_color") or upper_color
                split_upper_visible = saved_group_label.get("upper_visible", upper_visible)
                split_label_rows.append(
                    f"""
                    <div class="split-color-row" data-split-group="{_h(split_group_key)}">
                        <div class="split-color-head">
                            <strong>子组 {_h(split_group_key)}</strong>
                            <span class="split-count">0 样本</span>
                        </div>
                        <label class="toggle">
                            <input type="checkbox" class="split-upper-visible"{_visibility_checked(split_upper_visible)}>
                            上装可见
                        </label>
                        <label>
                            上装颜色
                            <select class="split-upper-color">{_color_options(split_upper_color)}</select>
                        </label>
                    </div>
                    """
                )

            state_text = "已保存" if saved else "未保存"
            outfit_cards.append(
                f"""
                <section class="outfit-card"
                    data-outfit-id="{_h(outfit_id)}"
                    data-person-id="{_h(current_person_id)}"
                    data-model-upper="{_h(model_upper)}"
                    data-distance-threshold="{float(distance_threshold):.4f}">
                    <header class="outfit-head">
                        <div>
                            <h3 title="{_h(outfit_id)}">装束 {int(group.get("group_index") or 0)}</h3>
                            <div class="meta-line">
                                <span>{int(group.get("event_count") or 0)} events</span>
                                <span>{int(group.get("session_count") or 0)} sessions</span>
                                <span>{_h(_session_time_label(group))}</span>
                                {split_badge}
                            </div>
                            <div class="source-line" title="{_h(source_sessions)}">{_h(source_sessions)}</div>
                        </div>
                        <div class="model-chip">
                            <span>自动装束判断</span>
                            {_color_chip(model_upper, group.get("model_upper_color_confidence"))}
                            <div class="chip-row">{chips}</div>
                        </div>
                        <div class="save-box">
                            <span class="state">{_h(state_text)}</span>
                            <button type="button" class="save-one">保存此装束</button>
                        </div>
                    </header>
                    <div class="samples">
                        {"".join(sample_tiles) or '<p class="empty">No samples</p>'}
                    </div>
                    <div class="split-label-panel">
                        <div class="split-label-title">拆分后上装颜色</div>
                        <div class="split-label-grid">
                            {"".join(split_label_rows)}
                        </div>
                    </div>
                    <div class="label-form">
                        <label class="toggle">
                            <input type="checkbox" class="identity-valid"{_visibility_checked(identity_valid)}>
                            人物正确
                        </label>
                        <label class="toggle">
                            <input type="checkbox" class="outfit-valid"{_visibility_checked(outfit_valid)}>
                            同一装束
                        </label>
                        <label class="toggle split-toggle">
                            <input type="checkbox" class="manual-split-required"{_visibility_checked(manual_split_required)}>
                            需要拆分
                        </label>
                        <label class="toggle">
                            <input type="checkbox" class="upper-visible"{_visibility_checked(upper_visible)}>
                            上装可见
                        </label>
                        <label>
                            整组上装颜色
                            <select class="upper-color">{_color_options(upper_color)}</select>
                        </label>
                        <label>
                            审核状态
                            <select class="review-status">{_review_status_options(review_status)}</select>
                        </label>
                        <label class="note-label">
                            备注
                            <input type="text" class="note" value="{_h(note)}" placeholder="可空">
                        </label>
                    </div>
                </section>
                """
            )

        person_blocks.append(
            f"""
            <section class="person-block">
                <header class="person-header">
                    {face_html}
                    <div>
                        <h2 title="{_h(current_person_id)}">{_h(current_person_id)}</h2>
                        <div class="person-stats">
                            <span>{int(person.get("face_count") or 0)} faces</span>
                            <span>{len(groups_by_person[current_person_id])} outfit groups</span>
                        </div>
                    </div>
                </header>
                <div class="outfit-grid">
                    {"".join(outfit_cards)}
                </div>
            </section>
            """
        )
        cards.append(
            f"""
            <article class="person-card">
                <img class="hero-face" src="{escape(_face_crop_data_url(person.get('representative_face_id')))}" alt="representative face">
                <div class="person-meta">
                    <h2>{escape(person['person_id'])}</h2>
                    <dl>
                        <div><dt>face_count</dt><dd>{int(person.get('face_count') or 0)}</dd></div>
                        <div><dt>representative_face_id</dt><dd>{escape(str(person.get('representative_face_id') or ''))}</dd></div>
                        <div><dt>first_seen_at</dt><dd>{escape(str(person.get('first_seen_at') or ''))}</dd></div>
                        <div><dt>last_seen_at</dt><dd>{escape(str(person.get('last_seen_at') or ''))}</dd></div>
                    </dl>
                </div>
                <div class="samples">{samples}</div>
            </article>
            """
        )

    body = "\n".join(cards) or '<p class="empty">No persons indexed yet.</p>'
    return HTMLResponse(
        f"""
        <!doctype html>
        <html lang="zh-CN">
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>CampusVision 人物库</title>
            <style>
                body {{ margin: 0; font-family: Arial, sans-serif; background: #f6f7f9; color: #20242a; }}
                main {{ max-width: 1180px; margin: 0 auto; padding: 24px; }}
                header {{ display: flex; justify-content: space-between; align-items: baseline; gap: 16px; margin-bottom: 18px; }}
                h1 {{ font-size: 24px; margin: 0; }}
                .count {{ color: #69717d; }}
                .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; }}
                .person-card {{ display: grid; grid-template-columns: 128px 1fr; gap: 14px; padding: 14px; background: #fff; border: 1px solid #dde1e7; border-radius: 8px; }}
                .hero-face {{ width: 128px; height: 128px; object-fit: cover; background: #e9edf2; border-radius: 6px; }}
                h2 {{ font-size: 16px; margin: 0 0 10px; word-break: break-all; }}
                dl {{ margin: 0; display: grid; gap: 6px; }}
                dl div {{ display: grid; grid-template-columns: 128px 1fr; gap: 8px; }}
                dt {{ color: #69717d; }}
                dd {{ margin: 0; word-break: break-all; }}
                .samples {{ grid-column: 1 / -1; display: flex; gap: 8px; overflow-x: auto; padding-top: 4px; }}
                .samples img {{ width: 54px; height: 54px; object-fit: cover; border-radius: 5px; background: #e9edf2; }}
                .empty {{ color: #69717d; }}
            </style>
        </head>
        <body>
            <main>
                <header><h1>CampusVision 人物库</h1><span class="count">{len(persons)} persons</span></header>
                <section class="grid">{body}</section>
            </main>
        </body>
        </html>
        """
    )

    body = "\n".join(person_blocks) or '<p class="empty">No outfit groups</p>'
    scope_tabs = _person_scope_tabs(
        "/api/v1/outfit-labels/review",
        include_candidates,
        mode="auto",
        person_id=person_id,
        sample_count=sample_count,
        distance_threshold=distance_threshold,
        unsaved_only=unsaved_only,
        status=status,
        limit=limit,
    )
    scope_label = "全部人物" if include_candidates else "只看稳定人物"
    return HTMLResponse(
        f"""
        <!doctype html>
        <html lang="zh-CN">
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>装束分组审核</title>
            <style>
                * {{ box-sizing: border-box; }}
                body {{ margin: 0; font-family: Arial, sans-serif; background: #f4f6f8; color: #20242a; }}
                main {{ max-width: 1500px; margin: 0 auto; padding: 18px; }}
                .toolbar {{ position: sticky; top: 0; z-index: 8; display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 12px 0; background: #f4f6f8; border-bottom: 1px solid #d8dee7; }}
                h1 {{ margin: 0; font-size: 22px; }}
                h2 {{ margin: 0; font-size: 15px; word-break: break-all; }}
                h3 {{ margin: 0; font-size: 14px; }}
                .summary, .meta-line, .person-stats, .state, .source-line {{ color: #5d6875; font-size: 12px; }}
                .actions {{ display: flex; align-items: center; gap: 10px; }}
                .scope-tabs {{ display: inline-flex; align-items: center; height: 34px; padding: 3px; border: 1px solid #cdd4df; border-radius: 7px; background: #fff; }}
                .scope-tab {{ display: inline-flex; align-items: center; height: 26px; padding: 0 10px; border-radius: 5px; color: #5d6875; text-decoration: none; font-size: 13px; }}
                .scope-tab.active {{ background: #20242a; color: #fff; }}
                button {{ height: 34px; border: 1px solid #bac3cf; border-radius: 6px; background: #fff; color: #20242a; cursor: pointer; padding: 0 12px; font-weight: 600; }}
                button.primary {{ background: #1f5f9f; border-color: #1f5f9f; color: #fff; }}
                button:disabled {{ opacity: .55; cursor: default; }}
                .status {{ min-width: 180px; color: #5d6875; font-size: 13px; text-align: right; }}
                .person-block {{ margin-top: 14px; border: 1px solid #d8dee7; border-radius: 8px; background: #fff; overflow: hidden; }}
                .person-header {{ display: grid; grid-template-columns: 58px 1fr; gap: 12px; align-items: center; padding: 12px; border-bottom: 1px solid #e5eaf1; background: #fbfcfd; }}
                .person-face {{ width: 58px; height: 58px; object-fit: cover; border-radius: 6px; background: #e8ecf1; }}
                .person-stats, .meta-line, .chip-row {{ display: flex; flex-wrap: wrap; gap: 7px; margin-top: 6px; }}
                .source-line {{ margin-top: 6px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
                .outfit-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(540px, 1fr)); gap: 12px; padding: 12px; }}
                .outfit-card {{ min-width: 0; border: 1px solid #dfe5ed; border-radius: 8px; overflow: hidden; background: #fff; }}
                .outfit-card.needs-split {{ border-color: #c98a2c; box-shadow: inset 0 0 0 1px #c98a2c; }}
                .outfit-head {{ display: grid; grid-template-columns: 1fr minmax(180px, auto) auto; gap: 12px; align-items: center; padding: 10px; border-bottom: 1px solid #e7ecf2; background: #fbfcfd; }}
                .model-chip {{ display: grid; gap: 4px; justify-items: start; color: #5d6875; font-size: 12px; }}
                .mini-chip, .split-badge {{ display: inline-flex; align-items: center; min-height: 22px; padding: 0 7px; border: 1px solid #d6dde7; border-radius: 6px; background: #fff; color: #5d6875; }}
                .split-badge {{ border-color: #b7cbe8; color: #174a86; background: #f7fbff; }}
                .save-box {{ display: flex; align-items: center; gap: 8px; justify-content: end; }}
                .samples {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(138px, 1fr)); gap: 8px; padding: 10px; }}
                .sample {{ position: relative; min-width: 0; border: 1px solid #e4e9f0; border-radius: 6px; overflow: hidden; background: #fbfcfd; }}
                .sample-body {{ display: block; width: 100%; height: 180px; object-fit: cover; background: #e8ecf1; }}
                .sample-face {{ position: absolute; top: 6px; right: 6px; width: 34px; height: 34px; object-fit: cover; border-radius: 5px; border: 1px solid #fff; background: #e8ecf1; }}
                .sample-meta {{ display: grid; gap: 3px; padding: 7px; }}
                .sample-meta strong, .sample-meta span {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
                .sample-meta strong {{ font-size: 12px; }}
                .sample-meta span {{ color: #5d6875; font-size: 12px; }}
                .split-control {{ display: grid; gap: 4px; padding: 0 7px 7px; }}
                .split-control span {{ color: #5d6875; font-size: 12px; }}
                .split-control select {{ width: 100%; height: 30px; font-size: 12px; }}
                .split-label-panel {{ display: none; padding: 10px; border-top: 1px solid #eadbc7; background: #fffaf3; }}
                .outfit-card.needs-split .split-label-panel {{ display: block; }}
                .split-label-title {{ margin-bottom: 8px; color: #7a4e12; font-size: 13px; font-weight: 700; }}
                .split-label-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 8px; }}
                .split-color-row {{ display: grid; gap: 7px; padding: 8px; border: 1px solid #eadbc7; border-radius: 6px; background: #fff; opacity: .45; }}
                .split-color-row.active {{ opacity: 1; border-color: #c98a2c; }}
                .split-color-row select {{ width: 100%; }}
                .split-color-head {{ display: flex; justify-content: space-between; align-items: center; gap: 8px; }}
                .split-color-head strong {{ font-size: 13px; }}
                .split-count {{ color: #7a4e12; font-size: 12px; }}
                .label-form {{ display: grid; grid-template-columns: 92px 92px 92px 92px minmax(120px, 160px) minmax(120px, 160px) 1fr; gap: 9px; align-items: end; padding: 10px; border-top: 1px solid #e7ecf2; }}
                label {{ display: grid; gap: 5px; font-size: 12px; color: #5d6875; }}
                .toggle {{ display: flex; align-items: center; gap: 6px; height: 34px; color: #20242a; }}
                .split-toggle {{ color: #7a4e12; }}
                select, input[type="text"] {{ height: 34px; border: 1px solid #c8d0da; border-radius: 6px; background: #fff; padding: 0 8px; color: #20242a; min-width: 0; }}
                .note-label {{ min-width: 180px; }}
                .color-chip {{ min-width: 0; display: inline-flex; align-items: center; gap: 6px; color: #20242a; font-size: 12px; }}
                .swatch {{ flex: 0 0 auto; width: 14px; height: 14px; border-radius: 3px; border: 1px solid #aeb6c2; }}
                .chip-meta {{ color: #707b87; }}
                .empty {{ margin: 0; padding: 14px; color: #5d6875; }}
                .placeholder {{ background: repeating-linear-gradient(45deg, #e8ecf1, #e8ecf1 7px, #dde3ea 7px, #dde3ea 14px); }}
                @media (max-width: 940px) {{
                    main {{ padding: 10px; }}
                    .toolbar, .outfit-head {{ grid-template-columns: 1fr; align-items: start; }}
                    .outfit-grid {{ grid-template-columns: 1fr; padding: 8px; }}
                    .label-form {{ grid-template-columns: 1fr 1fr; }}
                    .note-label {{ grid-column: 1 / -1; }}
                    .status {{ text-align: left; }}
                }}
            </style>
        </head>
        <body>
            <main>
                <div class="toolbar">
                    <div>
                        <h1>装束分组审核</h1>
                        <div class="summary">{_h(scope_label)} · {len(groups)} outfit groups · {sample_total} samples · saved {saved_count} · split groups {split_group_count} · file: {_h(str(_MANUAL_OUTFIT_LABEL_PATH))}</div>
                    </div>
                    <div class="actions">
                        {scope_tabs}
                        <button type="button" id="saveAll" class="primary">保存全部</button>
                        <span id="status" class="status">等待审核</span>
                    </div>
                </div>
                {body}
            </main>
            <script>
                const endpoint = "/api/v1/outfit-labels";
                function collectCard(card) {{
                    const samples = Array.from(card.querySelectorAll(".sample"));
                    const manualSplitRequired = card.querySelector(".manual-split-required").checked;
                    const splitGroupLabels = Array.from(card.querySelectorAll(".split-color-row")).map(row => ({{
                        split_group: row.dataset.splitGroup,
                        upper_visible: row.querySelector(".split-upper-visible").checked,
                        upper_color: row.querySelector(".split-upper-color").value,
                        sample_count: Number(row.dataset.sampleCount || "0"),
                    }})).filter(item => item.sample_count > 0);
                    return {{
                        outfit_id: card.dataset.outfitId,
                        person_id: card.dataset.personId,
                        distance_threshold: Number(card.dataset.distanceThreshold || "0.42"),
                        identity_valid: card.querySelector(".identity-valid").checked,
                        outfit_valid: !manualSplitRequired && card.querySelector(".outfit-valid").checked,
                        manual_split_required: manualSplitRequired,
                        upper_visible: card.querySelector(".upper-visible").checked,
                        upper_color: card.querySelector(".upper-color").value,
                        review_status: card.querySelector(".review-status").value,
                        note: card.querySelector(".note").value,
                        sample_event_ids: samples.map(item => item.dataset.eventId).filter(Boolean),
                        sample_observation_ids: samples.map(item => item.dataset.observationId).filter(Boolean),
                        split_assignments: samples.map(item => ({{
                            event_id: item.dataset.eventId || "",
                            observation_id: item.dataset.observationId || "",
                            split_group: item.querySelector(".split-group").value || "A",
                        }})).filter(item => item.event_id || item.observation_id),
                        split_group_labels: splitGroupLabels,
                    }};
                }}
                function syncSplitState(card) {{
                    const splitToggle = card.querySelector(".manual-split-required");
                    const outfitValid = card.querySelector(".outfit-valid");
                    const required = splitToggle.checked;
                    const counts = {{}};
                    card.querySelectorAll(".sample").forEach(sample => {{
                        const splitGroup = sample.querySelector(".split-group").value || "A";
                        if (!splitGroup || splitGroup === "exclude") return;
                        counts[splitGroup] = (counts[splitGroup] || 0) + 1;
                    }});
                    card.querySelectorAll(".split-color-row").forEach(row => {{
                        const count = counts[row.dataset.splitGroup] || 0;
                        row.dataset.sampleCount = String(count);
                        const countLabel = row.querySelector(".split-count");
                        if (countLabel) countLabel.textContent = `${{count}} 样本`;
                        row.classList.toggle("active", count > 0);
                    }});
                    if (required) {{
                        outfitValid.checked = false;
                    }}
                    outfitValid.disabled = required;
                    card.classList.toggle("needs-split", required);
                }}
                function updateReviewStatus(card) {{
                    const color = card.querySelector(".upper-color").value;
                    const status = card.querySelector(".review-status");
                    if (["uncertain", "ignore"].includes(status.value)) return;
                    status.value = color === card.dataset.modelUpper ? "confirmed" : "corrected";
                }}
                async function saveLabels(cards) {{
                    const status = document.getElementById("status");
                    status.textContent = "保存中...";
                    const labels = cards.map(collectCard);
                    const response = await fetch(endpoint, {{
                        method: "POST",
                        headers: {{ "Content-Type": "application/json" }},
                        body: JSON.stringify({{ labels }}),
                    }});
                    const body = await response.json();
                    if (!response.ok) {{
                        throw new Error(body.detail || "保存失败");
                    }}
                    cards.forEach(card => {{
                        const state = card.querySelector(".state");
                        if (state) state.textContent = "已保存";
                    }});
                    status.textContent = `已保存 ${{body.saved}} 套`;
                }}
                document.querySelectorAll(".outfit-card").forEach(card => {{
                    syncSplitState(card);
                    card.querySelector(".upper-color").addEventListener("change", () => updateReviewStatus(card));
                    card.querySelector(".manual-split-required").addEventListener("change", () => syncSplitState(card));
                    card.querySelectorAll(".split-group").forEach(select => {{
                        select.addEventListener("change", () => {{
                            const groups = new Set(Array.from(card.querySelectorAll(".split-group"))
                                .map(item => item.value)
                                .filter(value => value && value !== "exclude"));
                            if (groups.size > 1) {{
                                card.querySelector(".manual-split-required").checked = true;
                            }}
                            syncSplitState(card);
                        }});
                    }});
                }});
                document.getElementById("saveAll").addEventListener("click", async () => {{
                    const button = document.getElementById("saveAll");
                    button.disabled = true;
                    try {{
                        await saveLabels(Array.from(document.querySelectorAll(".outfit-card")));
                    }} catch (error) {{
                        document.getElementById("status").textContent = error.message;
                    }} finally {{
                        button.disabled = false;
                    }}
                }});
                document.querySelectorAll(".save-one").forEach(button => {{
                    button.addEventListener("click", async () => {{
                        button.disabled = true;
                        try {{
                            await saveLabels([button.closest(".outfit-card")]);
                        }} catch (error) {{
                            document.getElementById("status").textContent = error.message;
                        }} finally {{
                            button.disabled = false;
                        }}
                    }});
                }});
            </script>
        </body>
        </html>
        """
    )


@router.post("/appearance-session-labels")
async def save_manual_appearance_session_labels(request: Request):
    payload = await request.json()
    labels = payload.get("labels") if isinstance(payload, dict) else None
    if not isinstance(labels, list):
        raise HTTPException(status_code=400, detail="labels must be a list")

    allowed_colors = set(settings.clothing_color_labels)
    allowed_statuses = set(_SESSION_REVIEW_STATUS_LABELS)
    session_lookup = {
        session["session_id"]: session
        for session in event_service.list_appearance_sessions()
    }
    now = _utc_now()
    data = _load_manual_appearance_session_labels()
    saved = 0

    for label in labels:
        if not isinstance(label, dict):
            continue
        session_id = str(label.get("session_id") or "")
        session = session_lookup.get(session_id)
        if not session:
            raise HTTPException(status_code=400, detail=f"unknown session_id: {session_id}")

        upper_color = str(label.get("upper_color") or "unknown")
        if upper_color not in allowed_colors:
            raise HTTPException(status_code=400, detail=f"unsupported color for session_id: {session_id}")

        review_status = str(label.get("review_status") or "unreviewed")
        if review_status not in allowed_statuses:
            raise HTTPException(status_code=400, detail=f"unsupported review_status for session_id: {session_id}")

        sample_event_ids = [
            str(item)
            for item in label.get("sample_event_ids", [])
            if isinstance(item, str) and item
        ]
        sample_observation_ids = [
            str(item)
            for item in label.get("sample_observation_ids", [])
            if isinstance(item, str) and item
        ]
        snapshot_refs = _manual_sample_refs(
            sample_event_ids=sample_event_ids,
            sample_observation_ids=sample_observation_ids,
        )
        sample_snapshots = _snapshot_manual_samples("manual_appearance_session_labels", session_id, snapshot_refs)

        data["labels"][session_id] = {
            "session_id": session_id,
            "person_id": session.get("person_id"),
            "identity_valid": bool(label.get("identity_valid", True)),
            "session_valid": bool(label.get("session_valid", True)),
            "upper_visible": bool(label.get("upper_visible")),
            "upper_color": upper_color,
            "review_status": review_status,
            "note": str(label.get("note") or "").strip(),
            "model_upper_color": session.get("upper_color") or "unknown",
            "model_upper_color_confidence": session.get("upper_color_confidence"),
            "model_upper_color_support": session.get("upper_color_support"),
            "event_count": int(session.get("event_count") or 0),
            "sample_event_ids": sample_event_ids,
            "sample_observation_ids": sample_observation_ids,
            "sample_snapshot_version": _MANUAL_SAMPLE_SNAPSHOT_VERSION,
            "sample_snapshot_count": _snapshot_count(sample_snapshots),
            "sample_snapshots": sample_snapshots,
            "source": "manual_appearance_session_review",
            "saved_at": now,
        }
        saved += 1

    data["updated_at"] = now
    _save_manual_appearance_session_labels(data)
    return {
        "saved": saved,
        "updated_at": now,
        "path": str(_MANUAL_SESSION_LABEL_PATH),
    }


@router.get("/appearance-session-labels/review", response_class=HTMLResponse)
def manual_appearance_session_label_review(
    person_id: Optional[str] = None,
    sample_count: int = 6,
    unsaved_only: bool = False,
    status: Optional[str] = None,
    limit: int = 500,
):
    saved_data = _load_manual_appearance_session_labels()
    saved_labels = saved_data.get("labels", {})
    sessions = event_service.list_appearance_sessions(person_id=person_id)
    sessions = sessions[: max(1, min(int(limit), 2000))]
    events = db.list_events(person_id=person_id, identified=True, limit=5000)

    events_by_session: dict[str, list[dict]] = defaultdict(list)
    for event in events:
        session_id = event.get("appearance_session_id")
        if session_id:
            events_by_session[session_id].append(event)

    if unsaved_only:
        sessions = [session for session in sessions if session["session_id"] not in saved_labels]
    if status:
        sessions = [
            session
            for session in sessions
            if (saved_labels.get(session["session_id"], {}).get("review_status") or "unreviewed") == status
        ]

    persons = {
        person["person_id"]: person
        for person in db.list_persons()
        if not person_id or person["person_id"] == person_id
    }
    sessions_by_person: dict[str, list[dict]] = defaultdict(list)
    for session in sessions:
        sessions_by_person[session["person_id"]].append(session)

    person_blocks = []
    sample_total = 0
    saved_count = 0
    for current_person_id in sorted(sessions_by_person):
        person = persons.get(current_person_id, {})
        face_id = person.get("representative_face_id")
        face_html = (
            f'<img class="person-face" src="/api/v1/media/face/{_h(face_id)}" alt="{_h(face_id)}">'
            if face_id
            else '<div class="person-face placeholder"></div>'
        )
        session_cards = []
        for session in sorted(
            sessions_by_person[current_person_id],
            key=lambda item: (
                item.get("start_time") or "",
                float(item.get("start_timestamp_sec") or 0.0),
                item.get("session_id") or "",
            ),
        ):
            session_id = session["session_id"]
            saved = saved_labels.get(session_id, {})
            if saved:
                saved_count += 1

            model_upper = session.get("upper_color") or "unknown"
            model_confidence = session.get("upper_color_confidence")
            model_support = session.get("upper_color_support")
            upper_color = saved.get("upper_color") or model_upper
            upper_visible = saved.get("upper_visible", bool(session.get("upper_visible")) and model_upper != "unknown")
            review_status = saved.get("review_status") or "unreviewed"
            identity_valid = saved.get("identity_valid", True)
            session_valid = saved.get("session_valid", True)
            note = saved.get("note") or ""
            samples = _appearance_session_samples(
                events_by_session.get(session_id, []),
                sample_count,
            )
            sample_total += len(samples)

            sample_tiles = []
            for sample in samples:
                conf = sample.get("model_upper_confidence")
                conf_text = f" · {float(conf):.2f}" if conf is not None else ""
                face = (
                    f'<img class="sample-face" src="{_h(sample.get("face_url"))}" alt="">'
                    if sample.get("face_url")
                    else ""
                )
                sample_tiles.append(
                    f"""
                    <article class="sample"
                        data-event-id="{_h(sample.get("event_id"))}"
                        data-observation-id="{_h(sample.get("observation_id"))}">
                        <a href="{_h(sample.get("frame_url"))}" target="_blank" rel="noopener">
                            <img class="sample-body" src="{_h(sample.get("image_url"))}" alt="{_h(sample.get("event_id"))}">
                        </a>
                        {face}
                        <div class="sample-meta">
                            <strong>{_h(sample.get("camera_id"))}</strong>
                            <span>{_h(sample.get("time_label"))}</span>
                            <span>model 上装 {_h(sample.get("model_upper_color"))}{_h(conf_text)}</span>
                        </div>
                    </article>
                    """
                )

            state_text = "已保存" if saved else "未保存"
            session_cards.append(
                f"""
                <section class="session-card"
                    data-session-id="{_h(session_id)}"
                    data-person-id="{_h(current_person_id)}"
                    data-model-upper="{_h(model_upper)}">
                    <header class="session-head">
                        <div>
                            <h3 title="{_h(session_id)}">session:{_h(_short_id(session_id))}</h3>
                            <div class="meta-line">
                                <span>{int(session.get("event_count") or 0)} events</span>
                                <span>{_h(_session_time_label(session))}</span>
                            </div>
                        </div>
                        <div class="model-chip">
                            <span>模型上装</span>
                            {_color_chip(model_upper, model_confidence, model_support)}
                        </div>
                        <div class="save-box">
                            <span class="state">{_h(state_text)}</span>
                            <button type="button" class="save-one">保存此套</button>
                        </div>
                    </header>
                    <div class="samples">
                        {"".join(sample_tiles) or '<p class="empty">No samples</p>'}
                    </div>
                    <div class="label-form">
                        <label class="toggle">
                            <input type="checkbox" class="identity-valid"{_visibility_checked(identity_valid)}>
                            人物正确
                        </label>
                        <label class="toggle">
                            <input type="checkbox" class="session-valid"{_visibility_checked(session_valid)}>
                            单套装束
                        </label>
                        <label class="toggle">
                            <input type="checkbox" class="upper-visible"{_visibility_checked(upper_visible)}>
                            上装可见
                        </label>
                        <label>
                            上装颜色
                            <select class="upper-color">{_color_options(upper_color)}</select>
                        </label>
                        <label>
                            审核状态
                            <select class="review-status">{_review_status_options(review_status)}</select>
                        </label>
                        <label class="note-label">
                            备注
                            <input type="text" class="note" value="{_h(note)}" placeholder="可空">
                        </label>
                    </div>
                </section>
                """
            )

        person_blocks.append(
            f"""
            <section class="person-block">
                <header class="person-header">
                    {face_html}
                    <div>
                        <h2 title="{_h(current_person_id)}">{_h(current_person_id)}</h2>
                        <div class="person-stats">
                            <span>{int(person.get("face_count") or 0)} faces</span>
                            <span>{len(sessions_by_person[current_person_id])} sessions</span>
                        </div>
                    </div>
                </header>
                <div class="session-grid">
                    {"".join(session_cards)}
                </div>
            </section>
            """
        )

    body = "\n".join(person_blocks) or '<p class="empty">No appearance sessions</p>'
    return HTMLResponse(
        f"""
        <!doctype html>
        <html lang="zh-CN">
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>装束人工审核</title>
            <style>
                * {{ box-sizing: border-box; }}
                body {{ margin: 0; font-family: Arial, sans-serif; background: #f4f6f8; color: #20242a; }}
                main {{ max-width: 1480px; margin: 0 auto; padding: 18px; }}
                .toolbar {{ position: sticky; top: 0; z-index: 8; display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 12px 0; background: #f4f6f8; border-bottom: 1px solid #d8dee7; }}
                h1 {{ margin: 0; font-size: 22px; }}
                h2 {{ margin: 0; font-size: 15px; word-break: break-all; }}
                h3 {{ margin: 0; font-size: 14px; word-break: break-all; }}
                .summary, .meta-line, .person-stats, .state {{ color: #5d6875; font-size: 12px; }}
                .actions {{ display: flex; align-items: center; gap: 10px; }}
                button {{ height: 34px; border: 1px solid #bac3cf; border-radius: 6px; background: #fff; color: #20242a; cursor: pointer; padding: 0 12px; font-weight: 600; }}
                button.primary {{ background: #1f5f9f; border-color: #1f5f9f; color: #fff; }}
                button:disabled {{ opacity: .55; cursor: default; }}
                .status {{ min-width: 180px; color: #5d6875; font-size: 13px; text-align: right; }}
                .person-block {{ margin-top: 14px; border: 1px solid #d8dee7; border-radius: 8px; background: #fff; overflow: hidden; }}
                .person-header {{ display: grid; grid-template-columns: 58px 1fr; gap: 12px; align-items: center; padding: 12px; border-bottom: 1px solid #e5eaf1; background: #fbfcfd; }}
                .person-face {{ width: 58px; height: 58px; object-fit: cover; border-radius: 6px; background: #e8ecf1; }}
                .person-stats, .meta-line {{ display: flex; flex-wrap: wrap; gap: 7px; margin-top: 6px; }}
                .person-stats span, .meta-line span {{ min-width: 0; }}
                .session-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(520px, 1fr)); gap: 12px; padding: 12px; }}
                .session-card {{ min-width: 0; border: 1px solid #dfe5ed; border-radius: 8px; overflow: hidden; background: #fff; }}
                .session-head {{ display: grid; grid-template-columns: 1fr minmax(170px, auto) auto; gap: 12px; align-items: center; padding: 10px; border-bottom: 1px solid #e7ecf2; background: #fbfcfd; }}
                .model-chip {{ display: grid; gap: 4px; justify-items: start; color: #5d6875; font-size: 12px; }}
                .save-box {{ display: flex; align-items: center; gap: 8px; justify-content: end; }}
                .samples {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(138px, 1fr)); gap: 8px; padding: 10px; }}
                .sample {{ position: relative; min-width: 0; border: 1px solid #e4e9f0; border-radius: 6px; overflow: hidden; background: #fbfcfd; }}
                .sample-body {{ display: block; width: 100%; height: 180px; object-fit: cover; background: #e8ecf1; }}
                .sample-face {{ position: absolute; top: 6px; right: 6px; width: 34px; height: 34px; object-fit: cover; border-radius: 5px; border: 1px solid #fff; background: #e8ecf1; }}
                .sample-meta {{ display: grid; gap: 3px; padding: 7px; }}
                .sample-meta strong, .sample-meta span {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
                .sample-meta strong {{ font-size: 12px; }}
                .sample-meta span {{ color: #5d6875; font-size: 12px; }}
                .label-form {{ display: grid; grid-template-columns: 92px 92px 92px minmax(120px, 160px) minmax(120px, 160px) 1fr; gap: 9px; align-items: end; padding: 10px; border-top: 1px solid #e7ecf2; }}
                label {{ display: grid; gap: 5px; font-size: 12px; color: #5d6875; }}
                .toggle {{ display: flex; align-items: center; gap: 6px; height: 34px; color: #20242a; }}
                select, input[type="text"] {{ height: 34px; border: 1px solid #c8d0da; border-radius: 6px; background: #fff; padding: 0 8px; color: #20242a; min-width: 0; }}
                .note-label {{ min-width: 180px; }}
                .color-chip {{ min-width: 0; display: inline-flex; align-items: center; gap: 6px; color: #20242a; font-size: 12px; }}
                .swatch {{ flex: 0 0 auto; width: 14px; height: 14px; border-radius: 3px; border: 1px solid #aeb6c2; }}
                .chip-meta {{ color: #707b87; }}
                .empty {{ margin: 0; padding: 14px; color: #5d6875; }}
                .placeholder {{ background: repeating-linear-gradient(45deg, #e8ecf1, #e8ecf1 7px, #dde3ea 7px, #dde3ea 14px); }}
                @media (max-width: 940px) {{
                    main {{ padding: 10px; }}
                    .toolbar, .session-head {{ grid-template-columns: 1fr; align-items: start; }}
                    .session-grid {{ grid-template-columns: 1fr; padding: 8px; }}
                    .label-form {{ grid-template-columns: 1fr 1fr; }}
                    .note-label {{ grid-column: 1 / -1; }}
                    .status {{ text-align: left; }}
                }}
            </style>
        </head>
        <body>
            <main>
                <div class="toolbar">
                    <div>
                        <h1>装束人工审核</h1>
                        <div class="summary">{len(sessions)} sessions · {sample_total} samples · saved {saved_count} · file: {_h(str(_MANUAL_SESSION_LABEL_PATH))}</div>
                    </div>
                    <div class="actions">
                        <button type="button" id="saveAll" class="primary">保存全部</button>
                        <span id="status" class="status">等待审核</span>
                    </div>
                </div>
                {body}
            </main>
            <script>
                const endpoint = "/api/v1/appearance-session-labels";
                function collectCard(card) {{
                    const samples = Array.from(card.querySelectorAll(".sample"));
                    return {{
                        session_id: card.dataset.sessionId,
                        person_id: card.dataset.personId,
                        identity_valid: card.querySelector(".identity-valid").checked,
                        session_valid: card.querySelector(".session-valid").checked,
                        upper_visible: card.querySelector(".upper-visible").checked,
                        upper_color: card.querySelector(".upper-color").value,
                        review_status: card.querySelector(".review-status").value,
                        note: card.querySelector(".note").value,
                        sample_event_ids: samples.map(item => item.dataset.eventId).filter(Boolean),
                        sample_observation_ids: samples.map(item => item.dataset.observationId).filter(Boolean),
                    }};
                }}
                function updateReviewStatus(card) {{
                    const color = card.querySelector(".upper-color").value;
                    const status = card.querySelector(".review-status");
                    if (["uncertain", "ignore"].includes(status.value)) return;
                    status.value = color === card.dataset.modelUpper ? "confirmed" : "corrected";
                }}
                async function saveLabels(cards) {{
                    const status = document.getElementById("status");
                    status.textContent = "保存中...";
                    const labels = cards.map(collectCard);
                    const response = await fetch(endpoint, {{
                        method: "POST",
                        headers: {{ "Content-Type": "application/json" }},
                        body: JSON.stringify({{ labels }}),
                    }});
                    const body = await response.json();
                    if (!response.ok) {{
                        throw new Error(body.detail || "保存失败");
                    }}
                    cards.forEach(card => {{
                        const state = card.querySelector(".state");
                        if (state) state.textContent = "已保存";
                    }});
                    status.textContent = `已保存 ${{body.saved}} 套`;
                }}
                document.querySelectorAll(".session-card").forEach(card => {{
                    card.querySelector(".upper-color").addEventListener("change", () => updateReviewStatus(card));
                }});
                document.getElementById("saveAll").addEventListener("click", async () => {{
                    const button = document.getElementById("saveAll");
                    button.disabled = true;
                    try {{
                        await saveLabels(Array.from(document.querySelectorAll(".session-card")));
                    }} catch (error) {{
                        document.getElementById("status").textContent = error.message;
                    }} finally {{
                        button.disabled = false;
                    }}
                }});
                document.querySelectorAll(".save-one").forEach(button => {{
                    button.addEventListener("click", async () => {{
                        button.disabled = true;
                        try {{
                            await saveLabels([button.closest(".session-card")]);
                        }} catch (error) {{
                            document.getElementById("status").textContent = error.message;
                        }} finally {{
                            button.disabled = false;
                        }}
                    }});
                }});
            </script>
        </body>
        </html>
        """
    )


@router.post("/person-clothing-labels")
async def save_manual_person_clothing_labels(request: Request):
    payload = await request.json()
    labels = payload.get("labels") if isinstance(payload, dict) else None
    if not isinstance(labels, list):
        raise HTTPException(status_code=400, detail="labels must be a list")

    allowed = set(settings.clothing_color_labels)
    existing_person_ids = {person["person_id"] for person in db.list_persons()}
    now = _utc_now()
    data = _load_manual_clothing_labels()
    saved = 0
    for label in labels:
        if not isinstance(label, dict):
            continue
        person_id = str(label.get("person_id") or "")
        if person_id not in existing_person_ids:
            raise HTTPException(status_code=400, detail=f"unknown person_id: {person_id}")
        upper_color = str(label.get("upper_color") or "unknown")
        if upper_color not in allowed:
            raise HTTPException(status_code=400, detail=f"unsupported color for person_id: {person_id}")
        sample_event_ids = [
            str(item)
            for item in label.get("sample_event_ids", [])
            if isinstance(item, str) and item
        ]
        sample_observation_ids = [
            str(item)
            for item in label.get("sample_observation_ids", [])
            if isinstance(item, str) and item
        ]
        snapshot_refs = _manual_sample_refs(
            sample_event_ids=sample_event_ids,
            sample_observation_ids=sample_observation_ids,
        )
        sample_snapshots = _snapshot_manual_samples("manual_person_clothing_labels", person_id, snapshot_refs)
        data["labels"][person_id] = {
            "person_id": person_id,
            "upper_visible": bool(label.get("upper_visible")),
            "upper_color": upper_color,
            "lower_visible": False,
            "lower_color": "unknown",
            "note": str(label.get("note") or "").strip(),
            "sample_event_ids": sample_event_ids,
            "sample_observation_ids": sample_observation_ids,
            "sample_snapshot_version": _MANUAL_SAMPLE_SNAPSHOT_VERSION,
            "sample_snapshot_count": _snapshot_count(sample_snapshots),
            "sample_snapshots": sample_snapshots,
            "source": "manual_person_clothing_review",
            "saved_at": now,
        }
        saved += 1

    data["updated_at"] = now
    _save_manual_clothing_labels(data)
    return {
        "saved": saved,
        "updated_at": now,
        "path": str(_MANUAL_LABEL_PATH),
    }


@router.post("/gender-presentation-labels")
async def save_manual_gender_presentation_labels(request: Request):
    payload = await request.json()
    labels = payload.get("labels") if isinstance(payload, dict) else None
    if not isinstance(labels, list):
        raise HTTPException(status_code=400, detail="labels must be a list")

    current_person_ids = {
        person["person_id"]
        for person in person_service.list_persons(include_candidates=True)
    }
    allowed_presentations = set(_GENDER_PRESENTATION_OPTIONS)
    allowed_quality = set(_GENDER_EVIDENCE_QUALITY_OPTIONS)
    allowed_statuses = set(_SESSION_REVIEW_STATUS_LABELS)
    now = _utc_now()
    data = _load_manual_gender_presentation_labels()
    saved = 0

    for label in labels:
        if not isinstance(label, dict):
            continue
        person_id = str(label.get("person_id") or "")
        if person_id not in current_person_ids:
            raise HTTPException(status_code=400, detail=f"unknown person_id: {person_id}")

        presentation = str(label.get("gender_presentation") or "unknown")
        if presentation not in allowed_presentations:
            raise HTTPException(status_code=400, detail=f"unsupported gender_presentation: {presentation}")

        evidence_quality = str(label.get("evidence_quality") or "partial")
        if evidence_quality not in allowed_quality:
            raise HTTPException(status_code=400, detail=f"unsupported evidence_quality: {evidence_quality}")

        review_status = str(label.get("review_status") or "unreviewed")
        if review_status not in allowed_statuses:
            raise HTTPException(status_code=400, detail=f"unsupported review_status: {review_status}")

        sample_event_ids = [
            str(item)
            for item in label.get("sample_event_ids", [])
            if isinstance(item, str) and item
        ]
        sample_observation_ids = [
            str(item)
            for item in label.get("sample_observation_ids", [])
            if isinstance(item, str) and item
        ]
        snapshot_refs = _manual_sample_refs(
            sample_event_ids=sample_event_ids,
            sample_observation_ids=sample_observation_ids,
        )
        sample_snapshots = _snapshot_manual_samples("manual_gender_presentation_labels", person_id, snapshot_refs)

        data["labels"][person_id] = {
            "person_id": person_id,
            "gender_presentation": presentation,
            "gender_presentation_label": _GENDER_PRESENTATION_OPTIONS[presentation],
            "evidence_quality": evidence_quality,
            "evidence_quality_label": _GENDER_EVIDENCE_QUALITY_OPTIONS[evidence_quality],
            "review_status": review_status,
            "note": str(label.get("note") or "").strip(),
            "sample_event_ids": sample_event_ids,
            "sample_observation_ids": sample_observation_ids,
            "sample_snapshot_version": _MANUAL_SAMPLE_SNAPSHOT_VERSION,
            "sample_snapshot_count": _snapshot_count(sample_snapshots),
            "sample_snapshots": sample_snapshots,
            "source": "manual_gender_presentation_review_eval",
            "eval_only": True,
            "saved_at": now,
        }
        saved += 1

    data["updated_at"] = now
    _save_manual_gender_presentation_labels(data)
    return {
        "saved": saved,
        "updated_at": now,
        "path": str(_MANUAL_GENDER_PRESENTATION_LABEL_PATH),
    }


@router.post("/person-glasses-labels")
async def save_manual_person_glasses_labels(request: Request):
    payload = await request.json()
    labels = payload.get("labels") if isinstance(payload, dict) else None
    if not isinstance(labels, list):
        raise HTTPException(status_code=400, detail="labels must be a list")

    current_person_ids = {
        person["person_id"]
        for person in person_service.list_persons(include_candidates=True)
    }
    allowed_statuses = set(_GLASSES_STATUS_OPTIONS)
    allowed_quality = set(_GLASSES_EVIDENCE_QUALITY_OPTIONS)
    allowed_review_statuses = set(_SESSION_REVIEW_STATUS_LABELS)
    now = _utc_now()
    data = _load_manual_person_glasses_labels()
    saved = 0
    propagated_events = 0

    for label in labels:
        if not isinstance(label, dict):
            continue
        person_id = str(label.get("person_id") or "")
        if person_id not in current_person_ids:
            raise HTTPException(status_code=400, detail=f"unknown person_id: {person_id}")

        glasses_status = str(label.get("glasses_status") or "unknown")
        if glasses_status not in allowed_statuses:
            raise HTTPException(status_code=400, detail=f"unsupported glasses_status: {glasses_status}")

        evidence_quality = str(label.get("evidence_quality") or "partial")
        if evidence_quality not in allowed_quality:
            raise HTTPException(status_code=400, detail=f"unsupported evidence_quality: {evidence_quality}")

        review_status = str(label.get("review_status") or "unreviewed")
        if review_status not in allowed_review_statuses:
            raise HTTPException(status_code=400, detail=f"unsupported review_status: {review_status}")

        sample_event_ids = [
            str(item)
            for item in label.get("sample_event_ids", [])
            if isinstance(item, str) and item
        ]
        sample_observation_ids = [
            str(item)
            for item in label.get("sample_observation_ids", [])
            if isinstance(item, str) and item
        ]
        snapshot_refs = _manual_sample_refs(
            sample_event_ids=sample_event_ids,
            sample_observation_ids=sample_observation_ids,
        )
        sample_snapshots = _snapshot_manual_samples("manual_person_glasses_labels", person_id, snapshot_refs)
        event_labels = _person_event_glasses_labels(person_id, glasses_status, evidence_quality)
        propagated_events += len(event_labels)

        data["labels"][person_id] = {
            "person_id": person_id,
            "glasses_status": glasses_status,
            "glasses_status_label": _GLASSES_STATUS_OPTIONS[glasses_status],
            "evidence_quality": evidence_quality,
            "evidence_quality_label": _GLASSES_EVIDENCE_QUALITY_OPTIONS[evidence_quality],
            "review_status": review_status,
            "note": str(label.get("note") or "").strip(),
            "sample_event_ids": sample_event_ids,
            "sample_observation_ids": sample_observation_ids,
            "sample_snapshot_version": _MANUAL_SAMPLE_SNAPSHOT_VERSION,
            "sample_snapshot_count": _snapshot_count(sample_snapshots),
            "sample_snapshots": sample_snapshots,
            "event_count": len(event_labels),
            "event_glasses_labels": event_labels,
            "propagation_source": "manual_person_level",
            "source": "manual_person_glasses_review",
            "saved_at": now,
        }
        saved += 1

    data["updated_at"] = now
    _save_manual_person_glasses_labels(data)
    return {
        "saved": saved,
        "propagated_events": propagated_events,
        "updated_at": now,
        "path": str(_MANUAL_PERSON_GLASSES_LABEL_PATH),
    }


@router.get("/person-glasses-labels/review", response_class=HTMLResponse)
def manual_person_glasses_label_review(
    sample_count: int = 8,
    unsaved_only: bool = False,
    include_candidates: bool = True,
):
    saved_data = _load_manual_person_glasses_labels()
    saved_labels = saved_data.get("labels", {})
    persons = person_service.list_persons(include_candidates=include_candidates)
    if unsaved_only:
        persons = [person for person in persons if person["person_id"] not in saved_labels]

    cards = []
    total_samples = 0
    saved_count = 0
    total_events = 0
    for person in persons:
        person_id = person["person_id"]
        samples = _person_face_samples(person_id, sample_count)
        total_samples += len(samples)
        event_count = int(person.get("event_count") or 0)
        total_events += event_count
        saved = saved_labels.get(person_id, {})
        if saved:
            saved_count += 1
        glasses_status = saved.get("glasses_status") or "unknown"
        evidence_quality = saved.get("evidence_quality") or "partial"
        review_status = saved.get("review_status") or "unreviewed"
        note = saved.get("note") or ""
        face_id = person.get("representative_face_id")
        face_html = (
            f'<img class="face" src="/api/v1/media/face/{_h(face_id)}" alt="{_h(face_id)}">'
            if face_id
            else '<div class="face placeholder"></div>'
        )

        sample_tiles = []
        for sample in samples:
            context_url = sample.get("body_crop_url") or sample.get("frame_url") or ""
            context_html = (
                f'<a href="{_h(sample.get("frame_url"))}" target="_blank" rel="noopener">'
                f'<img class="context-shot" src="{_h(context_url)}" alt=""></a>'
                if context_url
                else ""
            )
            face_url = sample.get("face_crop_url") or ""
            sample_tiles.append(
                f"""
                <article class="sample"
                    data-event-id="{_h(sample.get("event_id"))}"
                    data-observation-id="{_h(sample.get("observation_id"))}">
                    <a href="{_h(sample.get("frame_url"))}" target="_blank" rel="noopener">
                        <img class="sample-face-large" src="{_h(face_url)}" alt="{_h(sample.get("event_id"))}">
                    </a>
                    {context_html}
                    <div class="sample-meta">
                        <strong>{_h(sample.get("camera_id"))}</strong>
                        <span>{_h(sample.get("time_label"))}</span>
                        <span>{int(sample.get("face_count") or 0)} faces</span>
                    </div>
                </article>
                """
            )

        cards.append(
            f"""
            <section class="person-card" data-person-id="{_h(person_id)}">
                <header class="person-head">
                    {face_html}
                    <div class="person-title">
                        <h2 title="{_h(person_id)}">{_h(person_id)}</h2>
                        <span>{_h(person.get("identity_status") or "")} · {len(samples)} samples · {int(person.get("face_count") or 0)} faces · {event_count} events</span>
                    </div>
                    <div class="person-actions">
                        <span class="state">{_h("已保存" if person_id in saved_labels else "未保存")}</span>
                        <button type="button" class="save-one">保存此人</button>
                    </div>
                </header>
                <div class="samples">
                    {"".join(sample_tiles) or '<p class="empty">No face samples</p>'}
                </div>
                <div class="label-form">
                    <label>
                        眼镜
                        <select class="glasses-status">{_glasses_status_options(glasses_status)}</select>
                    </label>
                    <label>
                        证据质量
                        <select class="evidence-quality">{_glasses_evidence_quality_options(evidence_quality)}</select>
                    </label>
                    <label>
                        审核状态
                        <select class="review-status">{_review_status_options(review_status)}</select>
                    </label>
                    <label class="note-label">
                        备注
                        <input type="text" class="note" value="{_h(note)}" placeholder="可空">
                    </label>
                </div>
            </section>
            """
        )

    scope_label = "全部人物含候选" if include_candidates else "仅稳定身份"
    clipped_sample_count = max(1, min(int(sample_count), 12))
    unsaved_href = (
        f"/api/v1/person-glasses-labels/review?include_candidates={str(include_candidates).lower()}"
        f"&unsaved_only={str(not unsaved_only).lower()}&sample_count={clipped_sample_count}"
    )
    unsaved_text = "查看全部" if unsaved_only else "只看未保存"
    scope_href = (
        f"/api/v1/person-glasses-labels/review?include_candidates={str(not include_candidates).lower()}"
        f"&unsaved_only={str(unsaved_only).lower()}&sample_count={clipped_sample_count}"
    )
    scope_text = "只看稳定身份" if include_candidates else "查看候选碎片"
    return HTMLResponse(
        f"""
        <!doctype html>
        <html lang="zh-CN">
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>眼镜状态人工审核</title>
            <style>
                * {{ box-sizing: border-box; }}
                body {{ margin: 0; font-family: Arial, sans-serif; background: #f5f7f9; color: #20242a; }}
                main {{ max-width: 1480px; margin: 0 auto; padding: 18px; }}
                .toolbar {{ position: sticky; top: 0; z-index: 6; display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 12px 0; background: #f5f7f9; border-bottom: 1px solid #d8dee7; }}
                h1 {{ margin: 0; font-size: 22px; }}
                h2 {{ margin: 0; font-size: 14px; word-break: break-all; }}
                .summary, .person-title span, .sample-meta span, .state {{ color: #5d6875; font-size: 12px; }}
                .mode-link {{ color: #5d6875; font-size: 13px; text-decoration: none; border-bottom: 1px solid #aeb6c2; }}
                .actions {{ display: flex; align-items: center; gap: 10px; }}
                button {{ height: 34px; border: 1px solid #bac3cf; border-radius: 6px; background: #fff; color: #20242a; cursor: pointer; padding: 0 12px; font-weight: 600; }}
                button.primary {{ background: #1f5f9f; border-color: #1f5f9f; color: #fff; }}
                button:disabled {{ opacity: .55; cursor: default; }}
                .status {{ min-width: 180px; color: #5d6875; font-size: 13px; text-align: right; }}
                .person-card {{ margin-top: 14px; border: 1px solid #d8dee7; border-radius: 8px; background: #fff; overflow: hidden; }}
                .person-head {{ display: grid; grid-template-columns: 64px 1fr auto; gap: 12px; align-items: center; padding: 12px; border-bottom: 1px solid #e5eaf1; background: #fbfcfd; }}
                .face {{ width: 64px; height: 64px; object-fit: cover; border-radius: 6px; background: #e8ecf1; }}
                .person-actions {{ display: flex; align-items: center; gap: 8px; }}
                .state {{ min-width: 44px; text-align: right; }}
                .samples {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); gap: 10px; padding: 12px; }}
                .sample {{ min-width: 0; border: 1px solid #e3e8ef; border-radius: 6px; overflow: hidden; background: #fbfcfd; }}
                .sample-face-large {{ display: block; width: 100%; height: 150px; object-fit: contain; background: #e8ecf1; }}
                .context-shot {{ display: block; width: 100%; height: 86px; object-fit: cover; border-top: 1px solid #e3e8ef; background: #e8ecf1; }}
                .sample-meta {{ display: grid; gap: 3px; padding: 7px; }}
                .sample-meta strong, .sample-meta span {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
                .sample-meta strong {{ font-size: 12px; }}
                .label-form {{ display: grid; grid-template-columns: minmax(130px, 180px) minmax(120px, 160px) minmax(130px, 170px) 1fr; gap: 10px; align-items: end; padding: 12px; border-top: 1px solid #e5eaf1; }}
                label {{ display: grid; gap: 5px; font-size: 12px; color: #5d6875; }}
                select, input[type="text"] {{ height: 34px; border: 1px solid #c8d0da; border-radius: 6px; background: #fff; padding: 0 8px; color: #20242a; min-width: 0; }}
                .note-label {{ min-width: 180px; }}
                .empty {{ margin: 0; padding: 14px; color: #5d6875; }}
                .placeholder {{ background: repeating-linear-gradient(45deg, #e8ecf1, #e8ecf1 7px, #dde3ea 7px, #dde3ea 14px); }}
                @media (max-width: 880px) {{
                    main {{ padding: 10px; }}
                    .toolbar, .person-head {{ display: grid; grid-template-columns: 1fr; align-items: start; }}
                    .label-form {{ grid-template-columns: 1fr 1fr; }}
                    .note-label {{ grid-column: 1 / -1; }}
                    .status {{ text-align: left; }}
                }}
            </style>
        </head>
        <body>
            <main>
                <div class="toolbar">
                    <div>
                        <h1>眼镜状态人工审核</h1>
                        <div class="summary">{len(persons)} persons · {scope_label} · {total_samples} samples · {total_events} propagated events · saved {saved_count} · file: {_h(str(_MANUAL_PERSON_GLASSES_LABEL_PATH))}</div>
                    </div>
                    <div class="actions">
                        <a class="mode-link" href="{_h(scope_href)}">{_h(scope_text)}</a>
                        <a class="mode-link" href="{_h(unsaved_href)}">{_h(unsaved_text)}</a>
                        <button type="button" id="saveAll" class="primary">保存全部</button>
                        <span id="status" class="status">等待审核</span>
                    </div>
                </div>
                {"".join(cards) or '<p class="empty">No persons to review.</p>'}
            </main>
            <script>
                const endpoint = "/api/v1/person-glasses-labels";
                function collectCard(card) {{
                    const samples = Array.from(card.querySelectorAll(".sample"));
                    return {{
                        person_id: card.dataset.personId,
                        glasses_status: card.querySelector(".glasses-status").value,
                        evidence_quality: card.querySelector(".evidence-quality").value,
                        review_status: card.querySelector(".review-status").value,
                        note: card.querySelector(".note").value,
                        sample_event_ids: samples.map(item => item.dataset.eventId).filter(Boolean),
                        sample_observation_ids: samples.map(item => item.dataset.observationId).filter(Boolean),
                    }};
                }}
                async function saveLabels(cards) {{
                    const status = document.getElementById("status");
                    status.textContent = "保存中...";
                    const labels = cards.map(collectCard);
                    const response = await fetch(endpoint, {{
                        method: "POST",
                        headers: {{ "Content-Type": "application/json" }},
                        body: JSON.stringify({{ labels }}),
                    }});
                    const body = await response.json();
                    if (!response.ok) {{
                        throw new Error(body.detail || "保存失败");
                    }}
                    cards.forEach(card => {{
                        const state = card.querySelector(".state");
                        if (state) state.textContent = "已保存";
                    }});
                    status.textContent = `已保存 ${{body.saved}} 人，传播 ${{body.propagated_events}} 个事件`;
                }}
                document.getElementById("saveAll").addEventListener("click", async event => {{
                    const button = event.currentTarget;
                    button.disabled = true;
                    try {{
                        await saveLabels(Array.from(document.querySelectorAll(".person-card")));
                    }} catch (error) {{
                        document.getElementById("status").textContent = error.message;
                    }} finally {{
                        button.disabled = false;
                    }}
                }});
                document.querySelectorAll(".save-one").forEach(button => {{
                    button.addEventListener("click", async event => {{
                        const current = event.currentTarget;
                        current.disabled = true;
                        try {{
                            await saveLabels([current.closest(".person-card")]);
                        }} catch (error) {{
                            document.getElementById("status").textContent = error.message;
                        }} finally {{
                            current.disabled = false;
                        }}
                    }});
                }});
            </script>
        </body>
        </html>
        """
    )


@router.get("/gender-presentation-labels/review", response_class=HTMLResponse)
def manual_gender_presentation_label_review(
    sample_count: int = 8,
    unsaved_only: bool = False,
    include_candidates: bool = True,
):
    saved_data = _load_manual_gender_presentation_labels()
    saved_labels = saved_data.get("labels", {})
    persons = person_service.list_persons(include_candidates=include_candidates)
    if unsaved_only:
        persons = [person for person in persons if person["person_id"] not in saved_labels]

    cards = []
    total_samples = 0
    saved_count = 0
    for person in persons:
        person_id = person["person_id"]
        samples = _person_body_samples(person_id, sample_count)
        total_samples += len(samples)
        saved = saved_labels.get(person_id, {})
        if saved:
            saved_count += 1
        presentation = saved.get("gender_presentation") or "unknown"
        evidence_quality = saved.get("evidence_quality") or "partial"
        review_status = saved.get("review_status") or "unreviewed"
        note = saved.get("note") or ""
        face_id = person.get("representative_face_id")
        face_html = (
            f'<img class="face" src="/api/v1/media/face/{_h(face_id)}" alt="{_h(face_id)}">'
            if face_id
            else '<div class="face placeholder"></div>'
        )

        sample_tiles = []
        for sample in samples:
            face = (
                f'<img class="sample-face" src="{_h(sample.get("face_crop_url"))}" alt="">'
                if sample.get("face_crop_url")
                else ""
            )
            sample_tiles.append(
                f"""
                <article class="sample"
                    data-event-id="{_h(sample.get("event_id"))}"
                    data-observation-id="{_h(sample.get("observation_id"))}">
                    <a href="{_h(sample.get("frame_url"))}" target="_blank" rel="noopener">
                        <img class="sample-body" src="{_h(sample.get("body_crop_url"))}" alt="{_h(sample.get("event_id"))}">
                    </a>
                    {face}
                    <div class="sample-meta">
                        <strong>{_h(sample.get("camera_id"))}</strong>
                        <span>{_h(sample.get("time_label"))}</span>
                        <span>上装 {_h(sample.get("model_upper_color") or "unknown")}</span>
                    </div>
                </article>
                """
            )

        cards.append(
            f"""
            <section class="person-card" data-person-id="{_h(person_id)}">
                <header class="person-head">
                    {face_html}
                    <div class="person-title">
                        <h2 title="{_h(person_id)}">{_h(person_id)}</h2>
                        <span>{_h(person.get("identity_status") or "")} · {len(samples)} samples · {int(person.get("face_count") or 0)} faces · {int(person.get("event_count") or 0)} events</span>
                    </div>
                    <div class="person-actions">
                        <span class="state">{_h("已保存" if person_id in saved_labels else "未保存")}</span>
                        <button type="button" class="save-one">保存此人</button>
                    </div>
                </header>
                <div class="samples">
                    {"".join(sample_tiles) or '<p class="empty">No body samples</p>'}
                </div>
                <div class="label-form">
                    <label>
                        外观倾向
                        <select class="gender-presentation">{_gender_presentation_options(presentation)}</select>
                    </label>
                    <label>
                        证据质量
                        <select class="evidence-quality">{_gender_evidence_quality_options(evidence_quality)}</select>
                    </label>
                    <label>
                        审核状态
                        <select class="review-status">{_review_status_options(review_status)}</select>
                    </label>
                    <label class="note-label">
                        备注
                        <input type="text" class="note" value="{_h(note)}" placeholder="可空">
                    </label>
                </div>
            </section>
            """
        )

    scope_label = "全部人物含候选" if include_candidates else "仅稳定身份"
    unsaved_href = (
        f"/api/v1/gender-presentation-labels/review?include_candidates={str(include_candidates).lower()}"
        f"&unsaved_only={str(not unsaved_only).lower()}&sample_count={max(1, min(int(sample_count), 12))}"
    )
    unsaved_text = "查看全部" if unsaved_only else "只看未保存"
    scope_href = (
        f"/api/v1/gender-presentation-labels/review?include_candidates={str(not include_candidates).lower()}"
        f"&unsaved_only={str(unsaved_only).lower()}&sample_count={max(1, min(int(sample_count), 12))}"
    )
    scope_text = "只看稳定身份" if include_candidates else "查看候选碎片"
    return HTMLResponse(
        f"""
        <!doctype html>
        <html lang="zh-CN">
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>外观倾向人工审核</title>
            <style>
                * {{ box-sizing: border-box; }}
                body {{ margin: 0; font-family: Arial, sans-serif; background: #f4f6f8; color: #20242a; }}
                main {{ max-width: 1480px; margin: 0 auto; padding: 18px; }}
                .toolbar {{ position: sticky; top: 0; z-index: 6; display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 12px 0; background: #f4f6f8; border-bottom: 1px solid #d8dee7; }}
                h1 {{ margin: 0; font-size: 22px; }}
                h2 {{ margin: 0; font-size: 14px; word-break: break-all; }}
                .summary, .person-title span, .sample-meta span, .state {{ color: #5d6875; font-size: 12px; }}
                .mode-link {{ color: #5d6875; font-size: 13px; text-decoration: none; border-bottom: 1px solid #aeb6c2; }}
                .actions {{ display: flex; align-items: center; gap: 10px; }}
                button {{ height: 34px; border: 1px solid #bac3cf; border-radius: 6px; background: #fff; color: #20242a; cursor: pointer; padding: 0 12px; font-weight: 600; }}
                button.primary {{ background: #1f5f9f; border-color: #1f5f9f; color: #fff; }}
                button:disabled {{ opacity: .55; cursor: default; }}
                .status {{ min-width: 180px; color: #5d6875; font-size: 13px; text-align: right; }}
                .person-card {{ margin-top: 14px; border: 1px solid #d8dee7; border-radius: 8px; background: #fff; overflow: hidden; }}
                .person-head {{ display: grid; grid-template-columns: 64px 1fr auto; gap: 12px; align-items: center; padding: 12px; border-bottom: 1px solid #e5eaf1; background: #fbfcfd; }}
                .face {{ width: 64px; height: 64px; object-fit: cover; border-radius: 6px; background: #e8ecf1; }}
                .person-actions {{ display: flex; align-items: center; gap: 8px; }}
                .state {{ min-width: 44px; text-align: right; }}
                .samples {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; padding: 12px; }}
                .sample {{ position: relative; min-width: 0; border: 1px solid #e3e8ef; border-radius: 6px; overflow: hidden; background: #fbfcfd; }}
                .sample-body {{ display: block; width: 100%; height: 200px; object-fit: cover; background: #e8ecf1; }}
                .sample-face {{ position: absolute; top: 6px; right: 6px; width: 38px; height: 38px; object-fit: cover; border-radius: 5px; border: 1px solid #fff; background: #e8ecf1; }}
                .sample-meta {{ display: grid; gap: 3px; padding: 7px; }}
                .sample-meta strong, .sample-meta span {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
                .sample-meta strong {{ font-size: 12px; }}
                .label-form {{ display: grid; grid-template-columns: minmax(130px, 180px) minmax(120px, 160px) minmax(130px, 170px) 1fr; gap: 10px; align-items: end; padding: 12px; border-top: 1px solid #e5eaf1; }}
                label {{ display: grid; gap: 5px; font-size: 12px; color: #5d6875; }}
                select, input[type="text"] {{ height: 34px; border: 1px solid #c8d0da; border-radius: 6px; background: #fff; padding: 0 8px; color: #20242a; min-width: 0; }}
                .note-label {{ min-width: 180px; }}
                .empty {{ margin: 0; padding: 14px; color: #5d6875; }}
                .placeholder {{ background: repeating-linear-gradient(45deg, #e8ecf1, #e8ecf1 7px, #dde3ea 7px, #dde3ea 14px); }}
                @media (max-width: 880px) {{
                    main {{ padding: 10px; }}
                    .toolbar, .person-head {{ display: grid; grid-template-columns: 1fr; align-items: start; }}
                    .label-form {{ grid-template-columns: 1fr 1fr; }}
                    .note-label {{ grid-column: 1 / -1; }}
                    .status {{ text-align: left; }}
                }}
            </style>
        </head>
        <body>
            <main>
                <div class="toolbar">
                    <div>
                        <h1>外观倾向人工审核</h1>
                        <div class="summary">{len(persons)} persons · {scope_label} · {total_samples} samples · saved {saved_count} · file: {_h(str(_MANUAL_GENDER_PRESENTATION_LABEL_PATH))}</div>
                    </div>
                    <div class="actions">
                        <a class="mode-link" href="{_h(scope_href)}">{_h(scope_text)}</a>
                        <a class="mode-link" href="{_h(unsaved_href)}">{_h(unsaved_text)}</a>
                        <button type="button" id="saveAll" class="primary">保存全部</button>
                        <span id="status" class="status">等待审核</span>
                    </div>
                </div>
                {"".join(cards) or '<p class="empty">No persons to review.</p>'}
            </main>
            <script>
                const endpoint = "/api/v1/gender-presentation-labels";
                function collectCard(card) {{
                    const samples = Array.from(card.querySelectorAll(".sample"));
                    return {{
                        person_id: card.dataset.personId,
                        gender_presentation: card.querySelector(".gender-presentation").value,
                        evidence_quality: card.querySelector(".evidence-quality").value,
                        review_status: card.querySelector(".review-status").value,
                        note: card.querySelector(".note").value,
                        sample_event_ids: samples.map(item => item.dataset.eventId).filter(Boolean),
                        sample_observation_ids: samples.map(item => item.dataset.observationId).filter(Boolean),
                    }};
                }}
                async function saveLabels(cards) {{
                    const status = document.getElementById("status");
                    status.textContent = "保存中...";
                    const labels = cards.map(collectCard);
                    const response = await fetch(endpoint, {{
                        method: "POST",
                        headers: {{ "Content-Type": "application/json" }},
                        body: JSON.stringify({{ labels }}),
                    }});
                    const body = await response.json();
                    if (!response.ok) {{
                        throw new Error(body.detail || "保存失败");
                    }}
                    cards.forEach(card => {{
                        const state = card.querySelector(".state");
                        if (state) state.textContent = "已保存";
                    }});
                    status.textContent = `已保存 ${{body.saved}} 人`;
                }}
                document.getElementById("saveAll").addEventListener("click", async () => {{
                    const button = document.getElementById("saveAll");
                    button.disabled = true;
                    try {{
                        await saveLabels(Array.from(document.querySelectorAll(".person-card")));
                    }} catch (error) {{
                        document.getElementById("status").textContent = error.message;
                    }} finally {{
                        button.disabled = false;
                    }}
                }});
                document.querySelectorAll(".save-one").forEach(button => {{
                    button.addEventListener("click", async () => {{
                        button.disabled = true;
                        try {{
                            await saveLabels([button.closest(".person-card")]);
                        }} catch (error) {{
                            document.getElementById("status").textContent = error.message;
                        }} finally {{
                            button.disabled = false;
                        }}
                    }});
                }});
            </script>
        </body>
        </html>
        """
    )


@router.get("/person-clothing-labels/review", response_class=HTMLResponse)
def manual_person_clothing_label_review(sample_count: int = 5):
    saved_data = _load_manual_clothing_labels()
    saved_labels = saved_data.get("labels", {})
    persons = db.list_persons()
    cards = []
    total_samples = 0
    for person in persons:
        person_id = person["person_id"]
        samples = _person_body_samples(person_id, sample_count)
        total_samples += len(samples)
        saved = saved_labels.get(person_id, {})
        upper_color = saved.get("upper_color") or "unknown"
        upper_visible = saved.get("upper_visible", upper_color != "unknown")
        note = saved.get("note") or ""
        face_id = person.get("representative_face_id")
        face_html = (
            f'<img class="face" src="/api/v1/media/face/{_h(face_id)}" alt="{_h(face_id)}">'
            if face_id
            else '<div class="face placeholder"></div>'
        )
        sample_tiles = []
        for sample in samples:
            model_upper = sample.get("model_upper_color") or "unknown"
            sample_tiles.append(
                f"""
                <article class="sample"
                    data-event-id="{_h(sample.get("event_id"))}"
                    data-observation-id="{_h(sample.get("observation_id"))}">
                    <a href="{_h(sample.get("frame_url"))}" target="_blank" rel="noopener">
                        <img src="{_h(sample.get("body_crop_url"))}" alt="{_h(sample.get("event_id"))}">
                    </a>
                    <div class="sample-meta">
                        <strong>{_h(sample.get("camera_id"))}</strong>
                        <span>{_h(sample.get("time_label"))}</span>
                        <span>model 上装 {model_upper}</span>
                    </div>
                </article>
                """
            )

        cards.append(
            f"""
            <section class="person-card" data-person-id="{_h(person_id)}">
                <header class="person-head">
                    {face_html}
                    <div class="person-title">
                        <h2>{_h(person_id)}</h2>
                        <span>{len(samples)} samples · {int(person.get("face_count") or 0)} faces</span>
                    </div>
                    <div class="person-actions">
                        <span class="state">{_h("已保存" if person_id in saved_labels else "未保存")}</span>
                        <button type="button" class="save-one">保存此人</button>
                    </div>
                </header>
                <div class="samples">
                    {"".join(sample_tiles) or '<p class="empty">No body samples</p>'}
                </div>
                <div class="label-form">
                    <label class="visible-toggle">
                        <input type="checkbox" class="upper-visible"{_visibility_checked(upper_visible)}>
                        上装可见
                    </label>
                    <label>
                        上装颜色
                        <select class="upper-color">{_color_options(upper_color)}</select>
                    </label>
                    <label class="note-label">
                        备注
                        <input type="text" class="note" value="{_h(note)}" placeholder="可空">
                    </label>
                </div>
            </section>
            """
        )

    return HTMLResponse(
        f"""
        <!doctype html>
        <html lang="zh-CN">
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>人物衣着人工标注</title>
            <style>
                * {{ box-sizing: border-box; }}
                body {{ margin: 0; font-family: Arial, sans-serif; background: #f5f6f8; color: #20242a; }}
                main {{ max-width: 1480px; margin: 0 auto; padding: 18px; }}
                .toolbar {{ position: sticky; top: 0; z-index: 5; display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 12px 0; background: #f5f6f8; border-bottom: 1px solid #d9dee5; }}
                h1 {{ margin: 0; font-size: 22px; }}
                h2 {{ margin: 0; font-size: 14px; word-break: break-all; }}
                .summary {{ color: #5d6875; font-size: 13px; }}
                .actions {{ display: flex; align-items: center; gap: 10px; }}
                button {{ height: 34px; border: 1px solid #bac3cf; border-radius: 6px; background: #fff; color: #20242a; cursor: pointer; padding: 0 12px; font-weight: 600; }}
                button.primary {{ background: #1f5f9f; border-color: #1f5f9f; color: #fff; }}
                button:disabled {{ opacity: .55; cursor: default; }}
                .status {{ min-width: 180px; color: #5d6875; font-size: 13px; text-align: right; }}
                .person-card {{ margin-top: 14px; border: 1px solid #d9dee5; border-radius: 8px; background: #fff; overflow: hidden; }}
                .person-head {{ display: grid; grid-template-columns: 58px 1fr auto; gap: 12px; align-items: center; padding: 12px; border-bottom: 1px solid #e5e9ef; background: #fbfcfd; }}
                .face {{ width: 58px; height: 58px; object-fit: cover; border-radius: 6px; background: #e8ecf1; }}
                .person-title span, .sample-meta span, .state {{ color: #5d6875; font-size: 12px; }}
                .person-actions {{ display: flex; align-items: center; gap: 8px; }}
                .state {{ min-width: 44px; text-align: right; }}
                .samples {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; padding: 12px; }}
                .sample {{ min-width: 0; border: 1px solid #e3e8ef; border-radius: 6px; overflow: hidden; background: #fbfcfd; }}
                .sample img {{ display: block; width: 100%; height: 190px; object-fit: cover; background: #e8ecf1; }}
                .sample-meta {{ display: grid; gap: 3px; padding: 7px; }}
                .sample-meta strong, .sample-meta span {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
                .sample-meta strong {{ font-size: 12px; }}
                .label-form {{ display: grid; grid-template-columns: 104px minmax(130px, 180px) 1fr; gap: 10px; align-items: end; padding: 12px; border-top: 1px solid #e5e9ef; }}
                label {{ display: grid; gap: 5px; font-size: 12px; color: #5d6875; }}
                .visible-toggle {{ display: flex; align-items: center; gap: 7px; height: 34px; color: #20242a; }}
                select, input[type="text"] {{ height: 34px; border: 1px solid #c8d0da; border-radius: 6px; background: #fff; padding: 0 8px; color: #20242a; min-width: 0; }}
                .note-label {{ min-width: 180px; }}
                .empty {{ margin: 0; padding: 14px; color: #5d6875; }}
                .placeholder {{ background: repeating-linear-gradient(45deg, #e8ecf1, #e8ecf1 7px, #dde3ea 7px, #dde3ea 14px); }}
                @media (max-width: 820px) {{
                    main {{ padding: 10px; }}
                    .toolbar, .person-head {{ grid-template-columns: 1fr; display: grid; align-items: start; }}
                    .label-form {{ grid-template-columns: 1fr 1fr; }}
                    .note-label {{ grid-column: 1 / -1; }}
                    .status {{ text-align: left; }}
                }}
            </style>
        </head>
        <body>
            <main>
                <div class="toolbar">
                    <div>
                        <h1>人物衣着人工标注</h1>
                        <div class="summary">{len(persons)} persons · {total_samples} body samples · saved file: {_h(str(_MANUAL_LABEL_PATH))}</div>
                    </div>
                    <div class="actions">
                        <button type="button" id="saveAll" class="primary">保存全部</button>
                        <span id="status" class="status">等待标注</span>
                    </div>
                </div>
                {"".join(cards) or '<p class="empty">No persons indexed yet.</p>'}
            </main>
            <script>
                const endpoint = "/api/v1/person-clothing-labels";
                function collectCard(card) {{
                    const samples = Array.from(card.querySelectorAll(".sample"));
                    return {{
                        person_id: card.dataset.personId,
                        upper_visible: card.querySelector(".upper-visible").checked,
                        upper_color: card.querySelector(".upper-color").value,
                        note: card.querySelector(".note").value,
                        sample_event_ids: samples.map(item => item.dataset.eventId).filter(Boolean),
                        sample_observation_ids: samples.map(item => item.dataset.observationId).filter(Boolean),
                    }};
                }}
                async function saveLabels(cards) {{
                    const status = document.getElementById("status");
                    status.textContent = "保存中...";
                    const labels = cards.map(collectCard);
                    const response = await fetch(endpoint, {{
                        method: "POST",
                        headers: {{ "Content-Type": "application/json" }},
                        body: JSON.stringify({{ labels }}),
                    }});
                    const body = await response.json();
                    if (!response.ok) {{
                        throw new Error(body.detail || "保存失败");
                    }}
                    cards.forEach(card => {{
                        const state = card.querySelector(".state");
                        if (state) state.textContent = "已保存";
                    }});
                    status.textContent = `已保存 ${{body.saved}} 人`;
                }}
                document.getElementById("saveAll").addEventListener("click", async () => {{
                    const button = document.getElementById("saveAll");
                    button.disabled = true;
                    try {{
                        await saveLabels(Array.from(document.querySelectorAll(".person-card")));
                    }} catch (error) {{
                        document.getElementById("status").textContent = error.message;
                    }} finally {{
                        button.disabled = false;
                    }}
                }});
                document.querySelectorAll(".save-one").forEach(button => {{
                    button.addEventListener("click", async () => {{
                        button.disabled = true;
                        try {{
                            await saveLabels([button.closest(".person-card")]);
                        }} catch (error) {{
                            document.getElementById("status").textContent = error.message;
                        }} finally {{
                            button.disabled = false;
                        }}
                    }});
                }});
            </script>
        </body>
        </html>
        """
    )


@router.get("/persons/{person_id}/events", response_model=list[PersonEventOut])
def get_person_events(
    person_id: str,
    max_gap_sec: float = 10.0,
    limit: int = Query(100, ge=1, le=5000),
):
    if db.get_person(person_id) is None:
        raise HTTPException(status_code=404, detail="Person not found")
    persisted = event_service.list_events(person_id=person_id, limit=limit)
    if persisted:
        return [person_service._persisted_event_for_person(event, person_id) for event in persisted]
    return person_service.person_events(person_id, max_gap_sec=max_gap_sec)[:limit]


@router.get("/persons/{person_id}/appearance-sessions", response_model=list[AppearanceSessionOut])
def get_person_appearance_sessions(person_id: str):
    if db.get_person(person_id) is None:
        raise HTTPException(status_code=404, detail="Person not found")
    return event_service.list_appearance_sessions(person_id=person_id)


@router.post("/persons/{person_id}/appearance-sessions/rebuild")
def rebuild_person_appearance_sessions(person_id: str):
    if db.get_person(person_id) is None:
        raise HTTPException(status_code=404, detail="Person not found")
    return event_service.rebuild_appearance_sessions_for_person(person_id)


@router.post("/appearance-sessions/rebuild")
def rebuild_all_appearance_sessions():
    return event_service.rebuild_all_appearance_sessions()


@router.get("/events", response_model=list[EventOut])
def list_events(
    request: Request,
    person_id: Optional[str] = None,
    camera_id: Optional[str] = None,
    upper_color: Optional[str] = None,
    identified: Optional[bool] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
):
    if "lower_color" in request.query_params:
        raise HTTPException(status_code=400, detail="lower clothing is not a core searchable attribute")
    return event_service.list_events(
        person_id=person_id,
        camera_id=camera_id,
        upper_color=upper_color,
        lower_color=None,
        identified=identified,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
    )


@router.get("/events/{event_id}", response_model=EventOut)
def get_event(event_id: str):
    event = db.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="event_id not found")
    profile = glasses_status_service.profile_for_event(event_id)
    event["glasses_status"] = profile.get("glasses_status") if profile else None
    event["glasses_status_label"] = profile.get("glasses_status_label") if profile else None
    event["glasses_confidence"] = profile.get("glasses_confidence") if profile else None
    event["glasses_evidence_quality"] = profile.get("glasses_evidence_quality") if profile else None
    event["glasses_model_version"] = profile.get("glasses_model_version") if profile else None
    event["glasses_profile"] = profile
    return event


@router.get("/events/{event_id}/observations", response_model=list[PersonObservationOut])
def get_event_observations(event_id: str):
    if db.get_event(event_id) is None:
        raise HTTPException(status_code=404, detail="event_id not found")
    return db.list_person_observations(event_id=event_id)


@router.get("/search/by-clothes", response_model=list[EventOut])
def search_by_clothes(
    request: Request,
    upper_color: Optional[str] = None,
    camera_id: Optional[str] = None,
    identified_only: bool = False,
    unidentified_only: bool = False,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
):
    allowed = set(settings.clothing_color_labels)
    if upper_color and upper_color not in allowed:
        raise HTTPException(status_code=400, detail=f"unsupported color: {upper_color}")
    if "lower_color" in request.query_params:
        raise HTTPException(status_code=400, detail="lower clothing is not a core searchable attribute")
    identified = None
    if identified_only and unidentified_only:
        raise HTTPException(status_code=400, detail="identified_only and unidentified_only are mutually exclusive")
    if identified_only:
        identified = True
    if unidentified_only:
        identified = False
    return event_service.search_by_clothes(
        upper_color=upper_color,
        lower_color=None,
        camera_id=camera_id,
        identified=identified,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
    )


@router.post("/query/face-image")
async def query_face_image(
    files: list[UploadFile] = File(...),
    query_face_indices: Optional[str] = Form(None),
    query_face_index: Optional[int] = Form(None),
    top_k: int = Form(5),
    min_score: Optional[float] = Form(None),
    max_gap_sec: float = Form(3.0),
    include_candidates: bool = Form(False),
    event_limit_per_person: int = Form(20),
    match_limit_per_person: int = Form(10),
    include_events: bool = Form(True),
    include_matches: bool = Form(True),
    camera_id: Optional[str] = Form(None),
    start_time: Optional[str] = Form(None),
    end_time: Optional[str] = Form(None),
):
    import uuid

    temp_search_id = "face_query_" + uuid.uuid4().hex
    paths = []
    try:
        _validate_query_upload_count(files)
        for upload in files:
            if not upload.filename:
                continue
            paths.append(search_service.save_query_image(upload.file, upload.filename, temp_search_id))
    except search_service.QueryImageTooLarge as exc:
        _cleanup_query_uploads(paths, temp_search_id)
        raise HTTPException(status_code=413, detail=str(exc)) from exc

    if not paths:
        raise HTTPException(status_code=400, detail="No query image uploaded.")

    parsed_indices = _parse_query_face_indices(query_face_indices, fallback_index=query_face_index)
    try:
        return person_service.query_face_image_candidates(
            paths,
            query_face_indices=parsed_indices,
            top_k=max(1, min(int(top_k), 50)),
            min_score=min_score,
            max_gap_sec=max(0.0, float(max_gap_sec)),
            include_candidates=include_candidates,
            event_limit_per_person=max(0, min(int(event_limit_per_person), 200)),
            match_limit_per_person=max(0, min(int(match_limit_per_person), 200)),
            include_events=include_events,
            include_matches=include_matches,
            camera_id=camera_id,
            start_time=start_time,
            end_time=end_time,
        )
    except search_service.QueryImageTooLarge as exc:
        _cleanup_query_uploads(paths, temp_search_id)
        raise HTTPException(status_code=413, detail=str(exc)) from exc


@router.post("/query/person-attributes", response_model=PersonAttributeQueryResult)
def query_person_attributes(payload: PersonAttributeQueryRequest):
    data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    try:
        return person_attribute_query_service.query_person_attributes(data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/videos/{video_id}/index", response_model=IndexResult)
def index_video(
    video_id: str,
    frame_interval_sec: Optional[float] = None,
    _: None = Depends(require_c1_api_key),
):
    try:
        return video_service.index_video(video_id, frame_interval_sec=frame_interval_sec)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Indexing failed: {exc}") from exc


@router.post("/search/by-image")
async def search_by_image(
    _: None = Depends(require_c1_api_key),
    files: list[UploadFile] = File(...),
    top_k: int = Form(20),
    min_score: Optional[float] = Form(None),
    max_gap_sec: float = Form(3.0),
    camera_id: Optional[str] = Form(None),
    start_time: Optional[str] = Form(None),
    end_time: Optional[str] = Form(None),
):
    import uuid

    temp_search_id = "upload_" + uuid.uuid4().hex
    paths = []
    try:
        _validate_query_upload_count(files)
        for f in files:
            if not f.filename:
                continue
            paths.append(search_service.save_query_image(f.file, f.filename, temp_search_id))
    except search_service.QueryImageTooLarge as exc:
        _cleanup_query_uploads(paths, temp_search_id)
        raise HTTPException(status_code=413, detail=str(exc)) from exc

    if not paths:
        raise HTTPException(status_code=400, detail="No query image uploaded.")

    try:
        result = search_service.search_by_images(
            paths,
            top_k=top_k,
            min_score=min_score,
            max_gap_sec=max_gap_sec,
            camera_id=camera_id,
            start_time=start_time,
            end_time=end_time,
        )
    except search_service.QueryImageTooLarge as exc:
        _cleanup_query_uploads(paths, temp_search_id)
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    return result


@router.post("/search/query-faces")
async def detect_query_faces(
    files: list[UploadFile] = File(...),
    _: None = Depends(require_c1_api_key),
):
    import uuid

    temp_search_id = "detect_" + uuid.uuid4().hex
    paths = []
    try:
        _validate_query_upload_count(files)
        for f in files:
            if not f.filename:
                continue
            paths.append(search_service.save_query_image(f.file, f.filename, temp_search_id))
    except search_service.QueryImageTooLarge as exc:
        _cleanup_query_uploads(paths, temp_search_id)
        raise HTTPException(status_code=413, detail=str(exc)) from exc

    if not paths:
        raise HTTPException(status_code=400, detail="No query image uploaded.")

    try:
        return search_service.detect_query_faces(paths)
    except search_service.QueryImageTooLarge as exc:
        _cleanup_query_uploads(paths, temp_search_id)
        raise HTTPException(status_code=413, detail=str(exc)) from exc


@router.post("/search/person-by-image")
async def search_person_by_image(
    _: None = Depends(require_c1_api_key),
    files: list[UploadFile] = File(...),
    top_k: int = Form(5),
    min_score: Optional[float] = Form(None),
    max_gap_sec: float = Form(3.0),
    query_face_index: Optional[int] = Form(None),
):
    import uuid

    temp_search_id = "upload_" + uuid.uuid4().hex
    paths = []
    try:
        _validate_query_upload_count(files)
        for f in files:
            if not f.filename:
                continue
            paths.append(search_service.save_query_image(f.file, f.filename, temp_search_id))
    except search_service.QueryImageTooLarge as exc:
        _cleanup_query_uploads(paths, temp_search_id)
        raise HTTPException(status_code=413, detail=str(exc)) from exc

    if not paths:
        raise HTTPException(status_code=400, detail="No query image uploaded.")

    try:
        return person_service.search_persons_by_images(
            paths,
            top_k=top_k,
            min_score=min_score,
            max_gap_sec=max_gap_sec,
            query_face_index=query_face_index,
        )
    except search_service.QueryImageTooLarge as exc:
        _cleanup_query_uploads(paths, temp_search_id)
        raise HTTPException(status_code=413, detail=str(exc)) from exc


@router.get("/searches/{search_id}")
def get_search(search_id: str):
    result = db.get_search(search_id)
    if not result:
        raise HTTPException(status_code=404, detail="search_id not found")
    return result


def _bbox_jpeg_response(frame_path: str, bbox: dict, *, padding_ratio: float = 0.04) -> Response:
    import cv2

    from app.vision.person_analysis import clamp_bbox

    image = cv2.imread(frame_path)
    if image is None:
        raise HTTPException(status_code=404, detail="frame image not found")

    height, width = image.shape[:2]
    raw_w = max(1.0, float(bbox.get("x2", 0) - bbox.get("x1", 0)))
    raw_h = max(1.0, float(bbox.get("y2", 0) - bbox.get("y1", 0)))
    padded = {
        **bbox,
        "x1": float(bbox["x1"]) - raw_w * padding_ratio,
        "y1": float(bbox["y1"]) - raw_h * padding_ratio,
        "x2": float(bbox["x2"]) + raw_w * padding_ratio,
        "y2": float(bbox["y2"]) + raw_h * padding_ratio,
    }
    box = clamp_bbox(padded, width, height)
    crop = image[box["y1"] : box["y2"], box["x1"] : box["x2"]]
    ok, encoded = cv2.imencode(".jpg", crop)
    if not ok:
        raise HTTPException(status_code=500, detail="failed to encode crop")
    return Response(content=encoded.tobytes(), media_type="image/jpeg")


@router.get("/eval-sample-snapshots/{snapshot_path:path}")
def get_eval_sample_snapshot(snapshot_path: str):
    root = _MANUAL_SAMPLE_SNAPSHOT_DIR.resolve()
    target = (root / snapshot_path).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="snapshot not found") from exc
    if not target.is_file():
        raise HTTPException(status_code=404, detail="snapshot not found")
    return FileResponse(target, media_type="image/jpeg")


@router.get("/media/frame/{face_id}")
def get_frame(face_id: str):
    record = db.get_face_record(face_id)
    if not record:
        raise HTTPException(status_code=404, detail="face_id not found")

    return FileResponse(record["frame_path"], media_type="image/jpeg")


@router.get("/media/face/{face_id}")
def get_face_crop(face_id: str):
    return Response(content=_face_crop_jpeg(face_id), media_type="image/jpeg")


@router.get("/media/observation/frame/{observation_id}")
def get_observation_frame(observation_id: str):
    observation = db.get_person_observation(observation_id)
    if not observation:
        raise HTTPException(status_code=404, detail="observation_id not found")
    return FileResponse(observation["frame_path"], media_type="image/jpeg")


@router.get("/media/observation/body/{observation_id}")
def get_observation_body_crop(observation_id: str):
    observation = db.get_person_observation(observation_id)
    if not observation:
        raise HTTPException(status_code=404, detail="observation_id not found")
    if not observation.get("person_bbox"):
        raise HTTPException(status_code=404, detail="person body box not found")
    return _bbox_jpeg_response(observation["frame_path"], observation["person_bbox"])


@router.get("/media/event/frame/{event_id}")
def get_event_frame(event_id: str):
    event = db.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="event_id not found")
    if not event.get("representative_frame_path"):
        raise HTTPException(status_code=404, detail="representative frame not found")
    return FileResponse(event["representative_frame_path"], media_type="image/jpeg")


@router.get("/media/event/body/{event_id}")
def get_event_body_crop(event_id: str):
    event = db.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="event_id not found")
    observation_id = event.get("representative_observation_id")
    if not observation_id:
        raise HTTPException(status_code=404, detail="representative observation not found")
    observation = db.get_person_observation(observation_id)
    if not observation:
        raise HTTPException(status_code=404, detail="representative observation not found")
    if not observation.get("person_bbox"):
        raise HTTPException(status_code=404, detail="person body box not found")
    return _bbox_jpeg_response(observation["frame_path"], observation["person_bbox"])


@router.get("/records")
def list_records(
    camera_id: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
):
    records = db.list_face_records(camera_id=camera_id, start_time=start_time, end_time=end_time)
    for rec in records:
        rec.pop("embedding", None)
        rec["frame_url"] = f"/api/v1/media/frame/{rec['face_id']}"
    return records
