from __future__ import annotations

import base64
import sys
from collections import defaultdict
from html import escape
from pathlib import Path
from typing import Any

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import settings
from app.storage import db
from app.vision.person_analysis import clamp_bbox


OUT_DIR = settings.data_dir / "evals" / "appearance_sessions"
OUT_FILE = OUT_DIR / "appearance_sessions.html"

COLOR_HEX = {
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


def h(value: object) -> str:
    return escape(str(value or ""), quote=True)


def short_id(value: str | None, keep: int = 8) -> str:
    if not value:
        return ""
    return value if len(value) <= keep else value[-keep:]


def encode_crop(frame_path: str | None, bbox: dict[str, Any] | None, *, width: int = 128) -> str | None:
    if not frame_path or not bbox:
        return None
    image = cv2.imread(frame_path)
    if image is None:
        return None

    height, frame_width = image.shape[:2]
    raw_w = max(1.0, float(bbox.get("x2", 0) - bbox.get("x1", 0)))
    raw_h = max(1.0, float(bbox.get("y2", 0) - bbox.get("y1", 0)))
    padded = {
        **bbox,
        "x1": float(bbox["x1"]) - raw_w * 0.04,
        "y1": float(bbox["y1"]) - raw_h * 0.04,
        "x2": float(bbox["x2"]) + raw_w * 0.04,
        "y2": float(bbox["y2"]) + raw_h * 0.04,
    }
    box = clamp_bbox(padded, frame_width, height)
    crop = image[box["y1"] : box["y2"], box["x1"] : box["x2"]]
    if crop.size <= 0:
        return None
    scale = width / max(1, crop.shape[1])
    if scale < 1.0:
        crop = cv2.resize(crop, (width, max(1, int(round(crop.shape[0] * scale)))))
    ok, encoded = cv2.imencode(".jpg", crop, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
    if not ok:
        return None
    return "data:image/jpeg;base64," + base64.b64encode(encoded.tobytes()).decode("ascii")


def event_image(event: dict[str, Any]) -> str | None:
    observation_id = event.get("representative_observation_id")
    if observation_id:
        observation = db.get_person_observation(observation_id)
        if observation and observation.get("person_bbox"):
            encoded = encode_crop(observation.get("frame_path"), observation.get("person_bbox"), width=120)
            if encoded:
                return encoded
    if event.get("representative_frame_path"):
        image = cv2.imread(event["representative_frame_path"])
        if image is not None:
            scale = 160 / max(1, image.shape[1])
            if scale < 1.0:
                image = cv2.resize(image, (160, max(1, int(round(image.shape[0] * scale)))))
            ok, encoded = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 78])
            if ok:
                return "data:image/jpeg;base64," + base64.b64encode(encoded.tobytes()).decode("ascii")
    return None


def face_image(person: dict[str, Any]) -> str | None:
    face_id = person.get("representative_face_id")
    if not face_id:
        return None
    record = db.get_face_record(face_id)
    if not record:
        return None
    return encode_crop(record.get("frame_path"), record.get("bbox"), width=80)


def color_chip(color: str | None, confidence: float | None = None, support: int | None = None) -> str:
    label = color or "unknown"
    meta = []
    if confidence is not None:
        meta.append(f"{float(confidence):.2f}")
    if support is not None:
        meta.append(f"n={int(support)}")
    meta_html = f'<span class="chip-meta">{h(" / ".join(meta))}</span>' if meta else ""
    return (
        '<span class="color-chip">'
        f'<span class="swatch" style="background:{h(COLOR_HEX.get(label, COLOR_HEX["unknown"]))}"></span>'
        f"<span>{h(label)}</span>{meta_html}"
        "</span>"
    )


def part_changed(event: dict[str, Any], prefix: str) -> bool:
    raw_color = event.get(f"raw_{prefix}_color") or "unknown"
    normalized_color = event.get(f"normalized_{prefix}_color") or event.get(f"{prefix}_color") or "unknown"
    return (
        event.get(f"raw_{prefix}_visible") != event.get(f"normalized_{prefix}_visible")
        or raw_color != normalized_color
    )


def part_line(event: dict[str, Any], prefix: str, label: str) -> str:
    raw_color = event.get(f"raw_{prefix}_color") or "unknown"
    raw_conf = event.get(f"raw_{prefix}_color_confidence")
    raw_visible = event.get(f"raw_{prefix}_visible")
    normalized_color = event.get(f"normalized_{prefix}_color") or event.get(f"{prefix}_color") or "unknown"
    normalized_conf = event.get(f"normalized_{prefix}_color_confidence") or event.get(
        f"{prefix}_color_confidence"
    )
    normalized_visible = event.get(f"normalized_{prefix}_visible")
    if raw_visible is False and normalized_visible is False:
        return f'<span class="part-line"><b>{h(label)}</b><span class="muted">未见</span></span>'
    if part_changed(event, prefix):
        return (
            f'<span class="part-line changed"><b>{h(label)}</b>'
            f'{color_chip(raw_color, raw_conf)}<span class="arrow">-&gt;</span>'
            f"{color_chip(normalized_color, normalized_conf)}</span>"
        )
    return f'<span class="part-line"><b>{h(label)}</b>{color_chip(normalized_color, normalized_conf)}</span>'


def time_label(item: dict[str, Any]) -> str:
    if item.get("start_time") or item.get("end_time"):
        return f"{item.get('start_time') or ''} - {item.get('end_time') or ''}"
    start = item.get("start_timestamp_sec")
    end = item.get("end_timestamp_sec")
    if start is not None or end is not None:
        return f"{float(start or 0.0):.1f}s - {float(end or 0.0):.1f}s"
    return ""


def event_tile(event: dict[str, Any]) -> str:
    image = event_image(event)
    image_html = (
        f'<img class="event-img" src="{h(image)}" alt="{h(event.get("event_id"))}">'
        if image
        else '<div class="event-img placeholder"></div>'
    )
    changed_class = " changed-event" if part_changed(event, "upper") else ""
    return f"""
        <article class="event-tile{changed_class}">
            {image_html}
            <div class="event-copy">
                <strong>{h(event.get("camera_id"))}</strong>
                <span class="muted">{h(time_label(event))}</span>
                {part_line(event, "upper", "上装")}
            </div>
        </article>
    """


def render() -> str:
    db.init_db()
    sessions = db.list_appearance_sessions()
    events = db.list_events(identified=True, limit=5000)
    persons = {person["person_id"]: person for person in db.list_persons()}

    events_by_session: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        session_id = event.get("appearance_session_id")
        if session_id:
            events_by_session[session_id].append(event)

    sessions_by_person: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for session in sessions:
        sessions_by_person[session["person_id"]].append(session)

    changed_event_count = sum(
        1
        for event in events
        if event.get("appearance_session_id")
        and part_changed(event, "upper")
    )
    assigned_event_count = sum(1 for event in events if event.get("appearance_session_id"))

    person_blocks = []
    for person_id in sorted(sessions_by_person):
        person = persons.get(person_id, {})
        face = face_image(person)
        face_html = (
            f'<img class="person-face" src="{h(face)}" alt="{h(person.get("representative_face_id"))}">'
            if face
            else '<div class="person-face placeholder"></div>'
        )
        session_rows = []
        for session in sorted(
            sessions_by_person[person_id],
            key=lambda item: (
                item.get("start_time") or "",
                float(item.get("start_timestamp_sec") or 0.0),
                item.get("session_id") or "",
            ),
        ):
            session_events = sorted(
                events_by_session.get(session["session_id"], []),
                key=lambda item: (
                    item.get("start_time") or "",
                    float(item.get("start_timestamp_sec") or 0.0),
                    item.get("event_id") or "",
                ),
            )
            event_tiles = "".join(event_tile(event) for event in session_events)
            session_rows.append(
                f"""
                <section class="session-row">
                    <div class="session-meta">
                        <div class="session-head">
                            <strong title="{h(session.get("session_id"))}">session:{h(short_id(session.get("session_id")))}</strong>
                            <span>{int(session.get("event_count") or 0)} events</span>
                        </div>
                        <div class="session-time">{h(time_label(session))}</div>
                        <div class="session-colors">
                            <span class="label">上装</span>
                            {color_chip(session.get("upper_color"), session.get("upper_color_confidence"), session.get("upper_color_support"))}
                        </div>
                    </div>
                    <div class="event-strip">{event_tiles or '<p class="empty">No events</p>'}</div>
                </section>
                """
            )

        person_blocks.append(
            f"""
            <section class="person-block">
                <header class="person-header">
                    {face_html}
                    <div>
                        <h2 title="{h(person_id)}">{h(person_id)}</h2>
                        <div class="person-stats">
                            <span>{int(person.get("face_count") or 0)} faces</span>
                            <span>{len(sessions_by_person[person_id])} sessions</span>
                        </div>
                    </div>
                </header>
                <div class="session-list">{''.join(session_rows)}</div>
            </section>
            """
        )

    return f"""
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
.summary span, .person-stats span, .session-head span {{ display: inline-flex; align-items: center; height: 24px; padding: 0 8px; border: 1px solid #d9dee5; border-radius: 6px; background: #fff; }}
.person-block {{ margin-bottom: 18px; border: 1px solid #d9dee5; border-radius: 8px; background: #fff; overflow: hidden; }}
.person-header {{ display: flex; align-items: center; gap: 12px; padding: 12px 14px; border-bottom: 1px solid #e5e9ef; background: #fbfcfd; }}
.person-face {{ width: 54px; height: 54px; object-fit: cover; border-radius: 6px; background: #e8ecf1; }}
.person-stats {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 7px; font-size: 12px; color: #56606b; }}
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
.event-strip {{ min-width: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 8px; }}
.event-tile {{ min-width: 0; display: grid; grid-template-columns: 82px 1fr; gap: 8px; padding: 8px; border: 1px solid #e2e7ee; border-radius: 6px; background: #fbfcfd; }}
.changed-event {{ border-color: #b7cbe8; background: #f7fbff; }}
.event-img {{ width: 82px; height: 82px; object-fit: cover; border-radius: 5px; background: #e8ecf1; }}
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
    .session-colors {{ grid-template-columns: 38px 1fr; }}
}}
</style>
</head>
<body>
<main>
<div class="topbar">
    <h1>Appearance Sessions</h1>
    <div class="summary">
        <span>{len(sessions)} sessions</span>
        <span>{assigned_event_count} assigned events</span>
        <span>{changed_event_count} normalized changes</span>
    </div>
</div>
{''.join(person_blocks) or '<p class="empty">No appearance sessions</p>'}
</main>
</body>
</html>
"""


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(render(), encoding="utf-8")
    print(OUT_FILE)


if __name__ == "__main__":
    main()
