from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any

from app.core.config import settings


@contextmanager
def get_conn():
    settings.ensure_dirs()
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def init_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cameras (
                camera_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                location TEXT,
                lat REAL,
                lng REAL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS videos (
                video_id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                camera_id TEXT NOT NULL,
                recorded_at TEXT,
                path TEXT NOT NULL,
                status TEXT NOT NULL,
                frame_interval_sec REAL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS live_sources (
                source_id TEXT PRIMARY KEY,
                camera_id TEXT NOT NULL,
                name TEXT NOT NULL,
                source_type TEXT NOT NULL,
                url TEXT NOT NULL,
                enabled INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS face_records (
                face_id TEXT PRIMARY KEY,
                video_id TEXT NOT NULL,
                camera_id TEXT NOT NULL,
                frame_path TEXT NOT NULL,
                video_timestamp_sec REAL NOT NULL,
                captured_at TEXT,
                bbox_json TEXT NOT NULL,
                embedding_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS searches (
                search_id TEXT PRIMARY KEY,
                query_paths_json TEXT NOT NULL,
                params_json TEXT NOT NULL,
                result_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS persons (
                person_id TEXT PRIMARY KEY,
                display_name TEXT,
                representative_face_id TEXT,
                representative_frame_path TEXT,
                embedding_json TEXT NOT NULL,
                face_count INTEGER NOT NULL,
                first_seen_at TEXT,
                last_seen_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS person_faces (
                person_id TEXT NOT NULL,
                face_id TEXT PRIMARY KEY,
                score_to_person REAL,
                created_at TEXT NOT NULL
            )
            """
        )


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def upsert_camera(camera: dict[str, Any]) -> dict[str, Any]:
    ts = now_iso()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO cameras(camera_id, name, location, lat, lng, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(camera_id) DO UPDATE SET
                name=excluded.name,
                location=excluded.location,
                lat=excluded.lat,
                lng=excluded.lng,
                updated_at=excluded.updated_at
            """,
            (
                camera["camera_id"],
                camera["name"],
                camera.get("location"),
                camera.get("lat"),
                camera.get("lng"),
                ts,
                ts,
            ),
        )
    result = get_camera(camera["camera_id"])
    assert result is not None
    return result


def get_camera(camera_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM cameras WHERE camera_id = ?", (camera_id,)).fetchone()
    return row_to_dict(row)


def list_cameras() -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM cameras ORDER BY camera_id").fetchall()
    return [dict(r) for r in rows]


def add_video(video: dict[str, Any]) -> dict[str, Any]:
    ts = now_iso()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO videos(video_id, filename, camera_id, recorded_at, path, status, frame_interval_sec, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                video["video_id"],
                video["filename"],
                video["camera_id"],
                video.get("recorded_at"),
                video["path"],
                video.get("status", "uploaded"),
                video.get("frame_interval_sec"),
                ts,
                ts,
            ),
        )
    result = get_video(video["video_id"])
    assert result is not None
    return result


def get_video(video_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM videos WHERE video_id = ?", (video_id,)).fetchone()
    return row_to_dict(row)


def list_videos() -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM videos ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]


def upsert_live_source(source: dict[str, Any]) -> dict[str, Any]:
    ts = now_iso()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO live_sources(source_id, camera_id, name, source_type, url, enabled, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_id) DO UPDATE SET
                camera_id=excluded.camera_id,
                name=excluded.name,
                source_type=excluded.source_type,
                url=excluded.url,
                enabled=excluded.enabled,
                updated_at=excluded.updated_at
            """,
            (
                source["source_id"],
                source["camera_id"],
                source["name"],
                source.get("source_type", "rtsp"),
                source["url"],
                1 if source.get("enabled", True) else 0,
                ts,
                ts,
            ),
        )
    result = get_live_source(source["source_id"])
    assert result is not None
    return result


def _live_source_from_row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    data = dict(row)
    data["enabled"] = bool(data["enabled"])
    return data


def get_live_source(source_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM live_sources WHERE source_id = ?", (source_id,)).fetchone()
    return _live_source_from_row(row)


def list_live_sources() -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM live_sources ORDER BY source_id").fetchall()
    return [source for row in rows if (source := _live_source_from_row(row)) is not None]


def update_video_status(video_id: str, status: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE videos SET status = ?, updated_at = ? WHERE video_id = ?",
            (status, now_iso(), video_id),
        )


def purge_live_videos(camera_id: str, before_created_at: str) -> dict[str, Any]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT video_id, path
            FROM videos
            WHERE camera_id = ?
              AND video_id LIKE 'live_%'
              AND created_at < ?
              AND status != 'indexing'
            ORDER BY created_at ASC
            """,
            (camera_id, before_created_at),
        ).fetchall()
        videos = [dict(row) for row in rows]
        video_ids = [video["video_id"] for video in videos]

        if not video_ids:
            return {
                "deleted_videos": 0,
                "deleted_faces": 0,
                "deleted_person_faces": 0,
                "videos": [],
            }

        placeholders = ",".join("?" for _ in video_ids)
        conn.execute(
            f"""
            DELETE FROM person_faces
            WHERE face_id IN (
                SELECT face_id FROM face_records WHERE video_id IN ({placeholders})
            )
            """,
            video_ids,
        )
        deleted_person_faces = conn.execute("SELECT changes()").fetchone()[0]
        conn.execute(f"DELETE FROM face_records WHERE video_id IN ({placeholders})", video_ids)
        deleted_faces = conn.execute("SELECT changes()").fetchone()[0]
        conn.execute(f"DELETE FROM videos WHERE video_id IN ({placeholders})", video_ids)
        deleted_videos = conn.execute("SELECT changes()").fetchone()[0]

    return {
        "deleted_videos": deleted_videos,
        "deleted_faces": deleted_faces,
        "deleted_person_faces": deleted_person_faces,
        "videos": videos,
    }


def add_face_record(record: dict[str, Any]) -> dict[str, Any]:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO face_records(
                face_id, video_id, camera_id, frame_path, video_timestamp_sec,
                captured_at, bbox_json, embedding_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["face_id"],
                record["video_id"],
                record["camera_id"],
                record["frame_path"],
                float(record["video_timestamp_sec"]),
                record.get("captured_at"),
                json.dumps(record["bbox"], ensure_ascii=False),
                json.dumps(record["embedding"]),
                now_iso(),
            ),
        )
    result = get_face_record(record["face_id"])
    assert result is not None
    return result


def get_face_record(face_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM face_records WHERE face_id = ?", (face_id,)).fetchone()
    if row is None:
        return None
    data = dict(row)
    data["bbox"] = json.loads(data.pop("bbox_json"))
    data["embedding"] = json.loads(data.pop("embedding_json"))
    return data


def list_face_records(
    camera_id: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
) -> list[dict[str, Any]]:
    clauses = []
    params: list[Any] = []

    if camera_id:
        clauses.append("camera_id = ?")
        params.append(camera_id)
    if start_time:
        clauses.append("captured_at IS NOT NULL AND captured_at >= ?")
        params.append(start_time)
    if end_time:
        clauses.append("captured_at IS NOT NULL AND captured_at <= ?")
        params.append(end_time)

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"SELECT * FROM face_records {where} ORDER BY captured_at, video_timestamp_sec"

    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()

    out = []
    for row in rows:
        data = dict(row)
        data["bbox"] = json.loads(data.pop("bbox_json"))
        data["embedding"] = json.loads(data.pop("embedding_json"))
        out.append(data)
    return out


def add_search(search: dict[str, Any]) -> dict[str, Any]:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO searches(search_id, query_paths_json, params_json, result_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                search["search_id"],
                json.dumps(search["query_paths"], ensure_ascii=False),
                json.dumps(search["params"], ensure_ascii=False),
                json.dumps(search["result"], ensure_ascii=False),
                now_iso(),
            ),
        )
    result = get_search(search["search_id"])
    assert result is not None
    return result


def get_search(search_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM searches WHERE search_id = ?", (search_id,)).fetchone()
    if row is None:
        return None
    data = dict(row)
    data["query_paths"] = json.loads(data.pop("query_paths_json"))
    data["params"] = json.loads(data.pop("params_json"))
    data["result"] = json.loads(data.pop("result_json"))
    return data


def clear_person_index() -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM person_faces")
        conn.execute("DELETE FROM persons")


def add_person(person: dict[str, Any]) -> dict[str, Any]:
    ts = now_iso()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO persons(
                person_id, display_name, representative_face_id, representative_frame_path,
                embedding_json, face_count, first_seen_at, last_seen_at, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                person["person_id"],
                person.get("display_name"),
                person.get("representative_face_id"),
                person.get("representative_frame_path"),
                json.dumps(person["embedding"]),
                int(person.get("face_count", 0)),
                person.get("first_seen_at"),
                person.get("last_seen_at"),
                ts,
                ts,
            ),
        )
    result = get_person(person["person_id"])
    assert result is not None
    return result


def add_person_face(person_id: str, face_id: str, score_to_person: float | None = None) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO person_faces(person_id, face_id, score_to_person, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (person_id, face_id, score_to_person, now_iso()),
        )


def update_person(person_id: str, person: dict[str, Any]) -> dict[str, Any]:
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE persons SET
                display_name = ?,
                representative_face_id = ?,
                representative_frame_path = ?,
                embedding_json = ?,
                face_count = ?,
                first_seen_at = ?,
                last_seen_at = ?,
                updated_at = ?
            WHERE person_id = ?
            """,
            (
                person.get("display_name"),
                person.get("representative_face_id"),
                person.get("representative_frame_path"),
                json.dumps(person["embedding"]),
                int(person.get("face_count", 0)),
                person.get("first_seen_at"),
                person.get("last_seen_at"),
                now_iso(),
                person_id,
            ),
        )
    result = get_person(person_id)
    assert result is not None
    return result


def _person_from_row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    data = dict(row)
    data["embedding"] = json.loads(data.pop("embedding_json"))
    data["representative_frame_url"] = (
        f"/api/v1/media/frame/{data['representative_face_id']}"
        if data.get("representative_face_id")
        else None
    )
    return data


def get_person(person_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM persons WHERE person_id = ?", (person_id,)).fetchone()
    return _person_from_row(row)


def list_persons() -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM persons ORDER BY face_count DESC, created_at ASC"
        ).fetchall()
    return [p for row in rows if (p := _person_from_row(row)) is not None]


def list_face_records_for_person(person_id: str) -> list[dict[str, Any]]:
    sql = """
        SELECT fr.*
        FROM face_records fr
        JOIN person_faces pf ON pf.face_id = fr.face_id
        WHERE pf.person_id = ?
        ORDER BY fr.captured_at, fr.video_timestamp_sec
    """
    with get_conn() as conn:
        rows = conn.execute(sql, (person_id,)).fetchall()

    out = []
    for row in rows:
        data = dict(row)
        data["bbox"] = json.loads(data.pop("bbox_json"))
        data["embedding"] = json.loads(data.pop("embedding_json"))
        out.append(data)
    return out


def list_unassigned_face_records() -> list[dict[str, Any]]:
    sql = """
        SELECT fr.*
        FROM face_records fr
        LEFT JOIN person_faces pf ON pf.face_id = fr.face_id
        WHERE pf.face_id IS NULL
        ORDER BY fr.captured_at, fr.video_timestamp_sec
    """
    with get_conn() as conn:
        rows = conn.execute(sql).fetchall()

    out = []
    for row in rows:
        data = dict(row)
        data["bbox"] = json.loads(data.pop("bbox_json"))
        data["embedding"] = json.loads(data.pop("embedding_json"))
        out.append(data)
    return out
