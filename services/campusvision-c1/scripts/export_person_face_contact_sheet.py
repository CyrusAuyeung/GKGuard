from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import settings
from app.storage import db


OUT_DIR = settings.data_dir / "evals" / "person_face_contact_sheet"
OUT_FILE = OUT_DIR / "person_face_contact_sheet_all.jpg"
INDEX_FILE = OUT_DIR / "person_face_contact_sheet_all.json"

PAGE_BG = (248, 248, 246)
BLOCK_BG = (255, 255, 255)
TEXT = (27, 31, 36)
MUTED = (92, 99, 112)
LINE = (218, 222, 228)
REP_BORDER = (35, 100, 170)


def font(size: int, *, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


FONT_TITLE = font(22, bold=True)
FONT_BODY = font(15)
FONT_SMALL = font(12)
FONT_TINY = font(10)


def short_id(value: str | None, keep: int = 8) -> str:
    if not value:
        return ""
    return value if len(value) <= keep else value[-keep:]


def load_json(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def clamp(value: float, low: int, high: int) -> int:
    return max(low, min(high, int(round(value))))


def crop_box(
    frame_path: str,
    bbox: dict[str, Any],
    *,
    size: tuple[int, int],
    pad_x: float,
    pad_top: float,
    pad_bottom: float,
    bg: tuple[int, int, int] = (236, 238, 241),
) -> Image.Image | None:
    path = Path(frame_path)
    if not path.exists():
        return None
    try:
        image = Image.open(path).convert("RGB")
    except OSError:
        return None

    width, height = image.size
    x1 = float(bbox.get("x1", 0.0))
    y1 = float(bbox.get("y1", 0.0))
    x2 = float(bbox.get("x2", 0.0))
    y2 = float(bbox.get("y2", 0.0))
    if x2 <= x1 or y2 <= y1:
        return None

    box_w = x2 - x1
    box_h = y2 - y1
    padded = (
        clamp(x1 - box_w * pad_x, 0, width),
        clamp(y1 - box_h * pad_top, 0, height),
        clamp(x2 + box_w * pad_x, 0, width),
        clamp(y2 + box_h * pad_bottom, 0, height),
    )
    if padded[2] <= padded[0] or padded[3] <= padded[1]:
        return None

    crop = image.crop(padded)
    crop.thumbnail(size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", size, bg)
    x = (size[0] - crop.size[0]) // 2
    y = (size[1] - crop.size[1]) // 2
    canvas.paste(crop, (x, y))
    return canvas


def crop_face(frame_path: str, bbox: dict[str, Any], *, size: tuple[int, int]) -> Image.Image | None:
    return crop_box(
        frame_path,
        bbox,
        size=size,
        pad_x=0.22,
        pad_top=0.32,
        pad_bottom=0.20,
    )


def crop_body(frame_path: str, bbox: dict[str, Any], *, size: tuple[int, int]) -> Image.Image | None:
    return crop_box(
        frame_path,
        bbox,
        size=size,
        pad_x=0.06,
        pad_top=0.04,
        pad_bottom=0.03,
        bg=(232, 234, 237),
    )


def has_body(record: dict[str, Any]) -> bool:
    return bool(record.get("person_bbox_json") and record.get("body_frame_path"))


def sample_indices(total: int, count: int) -> list[int]:
    if total <= 0 or count <= 0:
        return []
    if total <= count:
        return list(range(total))
    if count == 1:
        return [total // 2]
    return sorted({round(i * (total - 1) / (count - 1)) for i in range(count)})


def choose_faces(records: list[dict[str, Any]], representative_face_id: str | None, max_faces: int) -> list[dict[str, Any]]:
    body_records = [record for record in records if has_body(record)]
    pool = body_records or records
    if len(pool) <= max_faces:
        return pool

    by_id = {record["face_id"]: record for record in pool}
    selected: list[dict[str, Any]] = []
    used: set[str] = set()
    if representative_face_id and representative_face_id in by_id:
        selected.append(by_id[representative_face_id])
        used.add(representative_face_id)

    by_camera: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in pool:
        by_camera[str(record.get("camera_id") or "")].append(record)

    for camera_records in by_camera.values():
        camera_records.sort(
            key=lambda row: (
                float(row.get("video_timestamp_sec") or 0.0),
                str(row.get("face_id") or ""),
            )
        )

    cameras = sorted(by_camera)
    per_camera = max(1, min(3, math.ceil(max_faces / max(1, len(cameras)))))
    for camera_id in cameras:
        for index in sample_indices(len(by_camera[camera_id]), per_camera):
            record = by_camera[camera_id][index]
            if record["face_id"] in used:
                continue
            selected.append(record)
            used.add(record["face_id"])
            if len(selected) >= max_faces:
                return selected

    ranked = sorted(
        pool,
        key=lambda row: (
            0 if has_body(row) else 1,
            -(float(row.get("score_to_person") or 0.0)),
            str(row.get("camera_id") or ""),
            float(row.get("video_timestamp_sec") or 0.0),
        ),
    )
    for record in ranked:
        if record["face_id"] in used:
            continue
        selected.append(record)
        used.add(record["face_id"])
        if len(selected) >= max_faces:
            break
    return selected


def read_people() -> list[dict[str, Any]]:
    with db.get_conn() as conn:
        people = [
            dict(row)
            for row in conn.execute(
                """
                SELECT
                    p.person_id,
                    p.representative_face_id,
                    p.face_count,
                    p.event_count,
                    p.observation_count,
                    p.first_seen_at,
                    p.last_seen_at,
                    COALESCE(COUNT(pf.face_id), 0) AS linked_face_count,
                    COALESCE(COUNT(DISTINCT fr.camera_id), 0) AS camera_count
                FROM persons p
                LEFT JOIN person_faces pf ON pf.person_id = p.person_id
                LEFT JOIN face_records fr ON fr.face_id = pf.face_id
                GROUP BY p.person_id
                ORDER BY
                    COALESCE(p.first_seen_at, p.created_at),
                    p.created_at,
                    p.person_id
                """
            )
        ]
        for person in people:
            person["faces"] = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT
                        fr.face_id,
                        fr.camera_id,
                        fr.frame_path,
                        fr.video_timestamp_sec,
                        fr.bbox_json,
                        po.frame_path AS body_frame_path,
                        po.person_bbox_json,
                        pf.score_to_person
                    FROM person_faces pf
                    JOIN face_records fr ON fr.face_id = pf.face_id
                    LEFT JOIN person_observations po ON po.observation_id = fr.observation_id
                    WHERE pf.person_id = ?
                    ORDER BY
                        CASE WHEN po.person_bbox_json IS NOT NULL THEN 0 ELSE 1 END,
                        fr.camera_id,
                        fr.video_timestamp_sec,
                        fr.face_id
                    """,
                    (person["person_id"],),
                )
            ]
    return people


def text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], value: str, fill: tuple[int, int, int], font_obj: ImageFont.ImageFont) -> None:
    draw.text(xy, value, fill=fill, font=font_obj)


def render(max_faces: int) -> tuple[Image.Image, list[dict[str, Any]]]:
    people = read_people()
    tile_w = 178
    body_size = (146, 210)
    face_size = (54, 64)
    left_w = 318
    gap = 10
    cols = max_faces
    width = left_w + cols * tile_w + (cols + 2) * gap
    header_h = 74
    block_h = 280
    height = header_h + len(people) * block_h + 28

    image = Image.new("RGB", (width, height), PAGE_BG)
    draw = ImageDraw.Draw(image)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total_faces = sum(int(person.get("linked_face_count") or 0) for person in people)
    title = "person_face_contact_sheet_all"
    subtitle = f"generated {generated_at} | persons {len(people)} | linked faces {total_faces} | body+face view | max {max_faces} samples/person"
    text(draw, (18, 14), title, TEXT, FONT_TITLE)
    text(draw, (18, 44), subtitle, MUTED, FONT_BODY)

    index_rows: list[dict[str, Any]] = []
    y = header_h
    for person_number, person in enumerate(people, start=1):
        draw.rectangle((12, y, width - 12, y + block_h - 10), fill=BLOCK_BG, outline=LINE)
        person_id = str(person["person_id"])
        display = f"#{person_number:02d}  {short_id(person_id)}"
        text(draw, (24, y + 14), display, TEXT, FONT_TITLE)
        text(draw, (24, y + 44), person_id, MUTED, FONT_SMALL)
        meta = (
            f"faces {person.get('linked_face_count') or 0} | events {person.get('event_count') or 0} | "
            f"obs {person.get('observation_count') or 0} | cams {person.get('camera_count') or 0}"
        )
        text(draw, (24, y + 66), meta, TEXT, FONT_SMALL)
        time_range = f"{person.get('first_seen_at') or ''} -> {person.get('last_seen_at') or ''}"
        text(draw, (24, y + 88), time_range[:48], MUTED, FONT_TINY)
        rep = f"rep {short_id(person.get('representative_face_id'))}"
        text(draw, (24, y + 108), rep, MUTED, FONT_TINY)

        selected = choose_faces(person["faces"], person.get("representative_face_id"), max_faces)
        x = left_w + gap
        for record in selected:
            bbox = load_json(record.get("bbox_json"))
            face_crop = crop_face(str(record.get("frame_path") or ""), bbox, size=face_size)
            body_bbox = load_json(record.get("person_bbox_json"))
            body_frame_path = str(record.get("body_frame_path") or record.get("frame_path") or "")
            body_crop = crop_body(body_frame_path, body_bbox, size=body_size) if body_bbox else None
            border = REP_BORDER if record.get("face_id") == person.get("representative_face_id") else LINE
            draw.rectangle((x, y + 14, x + tile_w - 8, y + block_h - 22), fill=(250, 250, 249), outline=border, width=2)
            body_x = x + 14
            body_y = y + 22
            if body_crop is not None:
                image.paste(body_crop, (body_x, body_y))
                text(draw, (x + 12, y + 238), "body+face", MUTED, FONT_TINY)
            else:
                draw.rectangle((body_x, body_y, body_x + body_size[0], body_y + body_size[1]), fill=(226, 229, 233), outline=LINE)
                if face_crop is not None:
                    face_large = crop_face(str(record.get("frame_path") or ""), bbox, size=(98, 122))
                    if face_large is not None:
                        image.paste(face_large, (body_x + 24, body_y + 34))
                text(draw, (x + 14, y + 100), "face only", MUTED, FONT_TINY)
                text(draw, (x + 12, y + 238), "no body bbox", MUTED, FONT_TINY)
            if face_crop is not None:
                inset_x = x + tile_w - face_size[0] - 16
                inset_y = y + 24
                draw.rectangle(
                    (inset_x - 3, inset_y - 3, inset_x + face_size[0] + 3, inset_y + face_size[1] + 3),
                    fill=(255, 255, 255),
                    outline=(33, 37, 41),
                )
                image.paste(face_crop, (inset_x, inset_y))
            camera = str(record.get("camera_id") or "")
            timestamp = float(record.get("video_timestamp_sec") or 0.0)
            score = record.get("score_to_person")
            score_text = f"{float(score):.2f}" if score is not None else "-"
            text(draw, (x + 12, y + 252), f"{camera[:14]}  {timestamp:.1f}s", TEXT, FONT_TINY)
            text(draw, (x + 100, y + 252), f"score {score_text}", MUTED, FONT_TINY)
            x += tile_w

        index_rows.append(
            {
                "number": person_number,
                "person_id": person_id,
                "short_id": short_id(person_id),
                "representative_face_id": person.get("representative_face_id"),
                "linked_face_count": person.get("linked_face_count"),
                "event_count": person.get("event_count"),
                "observation_count": person.get("observation_count"),
                "camera_count": person.get("camera_count"),
            }
        )
        y += block_h
    return image, index_rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Export one face contact sheet for all indexed persons.")
    parser.add_argument("--max-faces", type=int, default=8, help="Maximum body+face samples shown per person.")
    parser.add_argument("--output", type=Path, default=OUT_FILE, help="Output jpg path.")
    parser.add_argument("--index-output", type=Path, default=INDEX_FILE, help="Output JSON index path.")
    parser.add_argument("--backup", action="store_true", help="Keep timestamped backups before overwriting outputs.")
    args = parser.parse_args()

    db.init_db()
    output = args.output.resolve()
    index_output = args.index_output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if args.backup:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        for path in [output, index_output]:
            if path.exists():
                shutil.copy2(path, path.with_name(f"{path.stem}.before_{timestamp}{path.suffix}"))

    image, index_rows = render(max(1, args.max_faces))
    image.save(output, quality=90, optimize=True)
    index_output.write_text(
        json.dumps(
            {
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "output": str(output),
                "persons": index_rows,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {output}")
    print(f"wrote {index_output}")
    print(f"persons {len(index_rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
