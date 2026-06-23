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


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _bool_value(value: Any) -> bool:
    return bool(int(value or 0))


def _json_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def _loads_json_or_none(value: str | None) -> Any | None:
    if not value:
        return None
    return json.loads(value)


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
        _ensure_column(conn, "face_records", "observation_id", "TEXT")
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
            CREATE TABLE IF NOT EXISTS person_observations (
                observation_id TEXT PRIMARY KEY,
                camera_id TEXT NOT NULL,
                video_id TEXT,
                live_source_id TEXT,
                frame_index INTEGER,
                video_timestamp_sec REAL,
                captured_at TEXT,
                frame_path TEXT NOT NULL,
                track_id TEXT,
                observation_type TEXT NOT NULL,
                body_visibility TEXT NOT NULL,
                person_bbox_json TEXT,
                person_detection_confidence REAL,
                face_record_id TEXT,
                person_id TEXT,
                upper_color TEXT,
                upper_color_confidence REAL,
                upper_visible INTEGER NOT NULL DEFAULT 0,
                upper_valid_pixel_ratio REAL,
                lower_color TEXT,
                lower_color_confidence REAL,
                lower_visible INTEGER NOT NULL DEFAULT 0,
                lower_valid_pixel_ratio REAL,
                clothing_model_version TEXT,
                body_model_version TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        _ensure_column(conn, "person_observations", "upper_color_probs_json", "TEXT")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                camera_id TEXT NOT NULL,
                video_id TEXT,
                live_source_id TEXT,
                track_id TEXT,
                person_id TEXT,
                start_time TEXT,
                end_time TEXT,
                start_timestamp_sec REAL,
                end_timestamp_sec REAL,
                observation_count INTEGER NOT NULL,
                face_count INTEGER NOT NULL,
                representative_observation_id TEXT,
                representative_face_id TEXT,
                representative_frame_path TEXT,
                upper_color TEXT,
                upper_color_confidence REAL,
                upper_visible INTEGER,
                lower_color TEXT,
                lower_color_confidence REAL,
                lower_visible INTEGER,
                identity_confidence REAL,
                event_status TEXT,
                aggregation_version TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        _ensure_column(conn, "events", "raw_upper_color", "TEXT")
        _ensure_column(conn, "events", "upper_color_probs_json", "TEXT")
        _ensure_column(conn, "events", "raw_upper_color_confidence", "REAL")
        _ensure_column(conn, "events", "raw_upper_visible", "INTEGER")
        _ensure_column(conn, "events", "raw_upper_color_probs_json", "TEXT")
        _ensure_column(conn, "events", "raw_lower_color", "TEXT")
        _ensure_column(conn, "events", "raw_lower_color_confidence", "REAL")
        _ensure_column(conn, "events", "raw_lower_visible", "INTEGER")
        _ensure_column(conn, "events", "normalized_upper_color", "TEXT")
        _ensure_column(conn, "events", "normalized_upper_color_confidence", "REAL")
        _ensure_column(conn, "events", "normalized_upper_visible", "INTEGER")
        _ensure_column(conn, "events", "normalized_upper_color_probs_json", "TEXT")
        _ensure_column(conn, "events", "normalized_lower_color", "TEXT")
        _ensure_column(conn, "events", "normalized_lower_color_confidence", "REAL")
        _ensure_column(conn, "events", "normalized_lower_visible", "INTEGER")
        _ensure_column(conn, "events", "appearance_session_id", "TEXT")
        _ensure_column(conn, "events", "clothing_normalization_version", "TEXT")
        _ensure_column(conn, "events", "clothing_normalization_reason_json", "TEXT")
        conn.execute(
            """
            UPDATE events SET
                raw_upper_color = COALESCE(raw_upper_color, upper_color),
                raw_upper_color_confidence = COALESCE(raw_upper_color_confidence, upper_color_confidence),
                raw_upper_visible = COALESCE(raw_upper_visible, upper_visible),
                raw_upper_color_probs_json = COALESCE(raw_upper_color_probs_json, upper_color_probs_json),
                raw_lower_color = COALESCE(raw_lower_color, lower_color),
                raw_lower_color_confidence = COALESCE(raw_lower_color_confidence, lower_color_confidence),
                raw_lower_visible = COALESCE(raw_lower_visible, lower_visible),
                normalized_upper_color = COALESCE(normalized_upper_color, upper_color),
                normalized_upper_color_confidence = COALESCE(normalized_upper_color_confidence, upper_color_confidence),
                normalized_upper_visible = COALESCE(normalized_upper_visible, upper_visible),
                normalized_upper_color_probs_json = COALESCE(normalized_upper_color_probs_json, upper_color_probs_json),
                normalized_lower_color = COALESCE(normalized_lower_color, lower_color),
                normalized_lower_color_confidence = COALESCE(normalized_lower_color_confidence, lower_color_confidence),
                normalized_lower_visible = COALESCE(normalized_lower_visible, lower_visible),
                clothing_normalization_version = COALESCE(clothing_normalization_version, 'event_raw_v1')
            WHERE raw_upper_color IS NULL
               OR raw_lower_color IS NULL
               OR normalized_upper_color IS NULL
               OR normalized_lower_color IS NULL
               OR clothing_normalization_version IS NULL
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS appearance_sessions (
                session_id TEXT PRIMARY KEY,
                person_id TEXT NOT NULL,
                start_time TEXT,
                end_time TEXT,
                start_timestamp_sec REAL,
                end_timestamp_sec REAL,
                event_count INTEGER NOT NULL,
                upper_color TEXT,
                upper_color_confidence REAL,
                upper_color_support INTEGER NOT NULL DEFAULT 0,
                upper_visible INTEGER,
                lower_color TEXT,
                lower_color_confidence REAL,
                lower_color_support INTEGER NOT NULL DEFAULT 0,
                lower_visible INTEGER,
                profile_json TEXT NOT NULL,
                session_status TEXT NOT NULL,
                aggregation_version TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS event_observations (
                event_id TEXT NOT NULL,
                observation_id TEXT NOT NULL,
                sequence_index INTEGER,
                is_representative INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                PRIMARY KEY(event_id, observation_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL
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
        _ensure_column(conn, "persons", "event_count", "INTEGER")
        _ensure_column(conn, "persons", "observation_count", "INTEGER")
        _ensure_column(conn, "persons", "last_event_id", "TEXT")
        _ensure_column(conn, "persons", "last_seen_camera_id", "TEXT")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_observations_camera_time "
            "ON person_observations(camera_id, captured_at, video_timestamp_sec)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_observations_video_time "
            "ON person_observations(video_id, video_timestamp_sec)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_observations_person_time "
            "ON person_observations(person_id, captured_at, video_timestamp_sec)"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_observations_face ON person_observations(face_record_id)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_camera_time "
            "ON events(camera_id, start_time, start_timestamp_sec)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_person_time "
            "ON events(person_id, start_time, start_timestamp_sec)"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_track ON events(track_id)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_upper_color "
            "ON events(upper_color, start_time, start_timestamp_sec)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_lower_color "
            "ON events(lower_color, start_time, start_timestamp_sec)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_appearance_session "
            "ON events(appearance_session_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_appearance_sessions_person_time "
            "ON appearance_sessions(person_id, start_time, start_timestamp_sec)"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_event_observations_event ON event_observations(event_id)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_event_observations_observation ON event_observations(observation_id)"
        )
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            ("20260622_person_observations_events", now_iso()),
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
                "deleted_observations": 0,
                "deleted_events": 0,
                "deleted_event_observations": 0,
                "touched_person_ids": [],
                "videos": [],
            }

        placeholders = ",".join("?" for _ in video_ids)
        event_rows = conn.execute(
            f"SELECT event_id, person_id FROM events WHERE video_id IN ({placeholders})",
            video_ids,
        ).fetchall()
        event_ids = [row["event_id"] for row in event_rows]
        touched_person_ids = sorted(
            {row["person_id"] for row in event_rows if row["person_id"]}
        )
        session_ids: list[str] = []
        if event_ids:
            event_placeholders = ",".join("?" for _ in event_ids)
            session_rows = conn.execute(
                f"""
                SELECT DISTINCT appearance_session_id
                FROM events
                WHERE event_id IN ({event_placeholders})
                  AND appearance_session_id IS NOT NULL
                """,
                event_ids,
            ).fetchall()
            session_ids = [row["appearance_session_id"] for row in session_rows]
            conn.execute(f"DELETE FROM event_observations WHERE event_id IN ({event_placeholders})", event_ids)
            deleted_event_observations = conn.execute("SELECT changes()").fetchone()[0]
            conn.execute(f"DELETE FROM events WHERE event_id IN ({event_placeholders})", event_ids)
            deleted_events = conn.execute("SELECT changes()").fetchone()[0]
            if session_ids:
                session_placeholders = ",".join("?" for _ in session_ids)
                conn.execute(
                    f"DELETE FROM appearance_sessions WHERE session_id IN ({session_placeholders})",
                    session_ids,
                )
        else:
            deleted_event_observations = 0
            deleted_events = 0

        conn.execute(f"DELETE FROM person_observations WHERE video_id IN ({placeholders})", video_ids)
        deleted_observations = conn.execute("SELECT changes()").fetchone()[0]
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
        "deleted_observations": deleted_observations,
        "deleted_events": deleted_events,
        "deleted_event_observations": deleted_event_observations,
        "touched_person_ids": touched_person_ids,
        "videos": videos,
    }


def add_face_record(record: dict[str, Any]) -> dict[str, Any]:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO face_records(
                face_id, video_id, camera_id, frame_path, video_timestamp_sec,
                captured_at, bbox_json, embedding_json, observation_id, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                record.get("observation_id"),
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


def update_face_record_observation(face_id: str, observation_id: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE face_records SET observation_id = ? WHERE face_id = ?",
            (observation_id, face_id),
        )


def _observation_from_row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    data = dict(row)
    raw_bbox = data.pop("person_bbox_json", None)
    raw_upper_probs = data.pop("upper_color_probs_json", None)
    data["person_bbox"] = json.loads(raw_bbox) if raw_bbox else None
    data["upper_color_probs"] = _loads_json_or_none(raw_upper_probs)
    data["upper_visible"] = _bool_value(data.get("upper_visible"))
    data["lower_visible"] = _bool_value(data.get("lower_visible"))
    data["frame_url"] = f"/api/v1/media/observation/frame/{data['observation_id']}"
    data["body_crop_url"] = (
        f"/api/v1/media/observation/body/{data['observation_id']}"
        if data.get("person_bbox")
        else None
    )
    return data


def add_person_observation(observation: dict[str, Any]) -> dict[str, Any]:
    ts = now_iso()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO person_observations(
                observation_id, camera_id, video_id, live_source_id, frame_index,
                video_timestamp_sec, captured_at, frame_path, track_id,
                observation_type, body_visibility, person_bbox_json,
                person_detection_confidence, face_record_id, person_id,
                upper_color, upper_color_confidence, upper_visible, upper_valid_pixel_ratio,
                upper_color_probs_json,
                lower_color, lower_color_confidence, lower_visible, lower_valid_pixel_ratio,
                clothing_model_version, body_model_version, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                observation["observation_id"],
                observation["camera_id"],
                observation.get("video_id"),
                observation.get("live_source_id"),
                observation.get("frame_index"),
                observation.get("video_timestamp_sec"),
                observation.get("captured_at"),
                observation["frame_path"],
                observation.get("track_id"),
                observation["observation_type"],
                observation.get("body_visibility") or "unknown_body",
                json.dumps(observation.get("person_bbox"), ensure_ascii=False)
                if observation.get("person_bbox") is not None
                else None,
                observation.get("person_detection_confidence"),
                observation.get("face_record_id"),
                observation.get("person_id"),
                observation.get("upper_color"),
                observation.get("upper_color_confidence"),
                1 if observation.get("upper_visible") else 0,
                observation.get("upper_valid_pixel_ratio"),
                _json_or_none(observation.get("upper_color_probs")),
                observation.get("lower_color"),
                observation.get("lower_color_confidence"),
                1 if observation.get("lower_visible") else 0,
                observation.get("lower_valid_pixel_ratio"),
                observation.get("clothing_model_version"),
                observation.get("body_model_version"),
                observation.get("created_at") or ts,
                ts,
            ),
        )
    result = get_person_observation(observation["observation_id"])
    assert result is not None
    return result


def get_person_observation(observation_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM person_observations WHERE observation_id = ?",
            (observation_id,),
        ).fetchone()
    return _observation_from_row(row)


def list_person_observations(
    *,
    video_id: str | None = None,
    event_id: str | None = None,
    person_id: str | None = None,
) -> list[dict[str, Any]]:
    clauses = []
    params: list[Any] = []
    join = ""

    if event_id:
        join = "JOIN event_observations eo ON eo.observation_id = po.observation_id"
        clauses.append("eo.event_id = ?")
        params.append(event_id)
    if video_id:
        clauses.append("po.video_id = ?")
        params.append(video_id)
    if person_id:
        clauses.append("po.person_id = ?")
        params.append(person_id)

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"""
        SELECT po.*
        FROM person_observations po
        {join}
        {where}
        ORDER BY po.captured_at, po.video_timestamp_sec, po.created_at
    """
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [obs for row in rows if (obs := _observation_from_row(row)) is not None]


def delete_events_for_video(video_id: str) -> set[str]:
    with get_conn() as conn:
        event_rows = conn.execute("SELECT event_id FROM events WHERE video_id = ?", (video_id,)).fetchall()
        event_ids = [row["event_id"] for row in event_rows]
        person_rows = conn.execute(
            "SELECT DISTINCT person_id FROM events WHERE video_id = ? AND person_id IS NOT NULL",
            (video_id,),
        ).fetchall()
        person_ids = {row["person_id"] for row in person_rows}
        if not event_ids:
            return person_ids
        session_rows = conn.execute(
            f"""
            SELECT DISTINCT appearance_session_id
            FROM events
            WHERE event_id IN ({",".join("?" for _ in event_ids)})
              AND appearance_session_id IS NOT NULL
            """,
            event_ids,
        ).fetchall()
        session_ids = [row["appearance_session_id"] for row in session_rows]
        placeholders = ",".join("?" for _ in event_ids)
        conn.execute(f"DELETE FROM event_observations WHERE event_id IN ({placeholders})", event_ids)
        conn.execute(f"DELETE FROM events WHERE event_id IN ({placeholders})", event_ids)
        if session_ids:
            session_placeholders = ",".join("?" for _ in session_ids)
            conn.execute(f"DELETE FROM appearance_sessions WHERE session_id IN ({session_placeholders})", session_ids)
    return person_ids


def _event_from_row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    data = dict(row)
    for key in (
        "upper_visible",
        "lower_visible",
        "raw_upper_visible",
        "raw_lower_visible",
        "normalized_upper_visible",
        "normalized_lower_visible",
    ):
        data[key] = None if data.get(key) is None else _bool_value(data.get(key))
    for key in (
        "upper_color_probs_json",
        "raw_upper_color_probs_json",
        "normalized_upper_color_probs_json",
    ):
        raw_probs = data.pop(key, None)
        data[key.removesuffix("_json")] = _loads_json_or_none(raw_probs)
    raw_reason = data.pop("clothing_normalization_reason_json", None)
    data["clothing_normalization_reason"] = json.loads(raw_reason) if raw_reason else None
    data["representative_frame_url"] = (
        f"/api/v1/media/event/frame/{data['event_id']}"
        if data.get("representative_frame_path")
        else None
    )
    data["representative_face_crop_url"] = (
        f"/api/v1/media/face/{data['representative_face_id']}"
        if data.get("representative_face_id")
        else None
    )
    representative_observation = (
        get_person_observation(data["representative_observation_id"])
        if data.get("representative_observation_id")
        else None
    )
    data["body_visibility"] = (
        representative_observation.get("body_visibility") if representative_observation else None
    )
    data["representative_body_crop_url"] = (
        f"/api/v1/media/event/body/{data['event_id']}"
        if representative_observation and representative_observation.get("person_bbox")
        else None
    )
    return data


def add_event(event: dict[str, Any], observations: list[dict[str, Any]]) -> dict[str, Any]:
    ts = now_iso()
    raw_upper_color = event.get("raw_upper_color", event.get("upper_color"))
    raw_upper_confidence = event.get("raw_upper_color_confidence", event.get("upper_color_confidence"))
    raw_upper_visible = event.get("raw_upper_visible", event.get("upper_visible"))
    raw_upper_probs = event.get("raw_upper_color_probs", event.get("upper_color_probs"))
    raw_lower_color = event.get("raw_lower_color", event.get("lower_color"))
    raw_lower_confidence = event.get("raw_lower_color_confidence", event.get("lower_color_confidence"))
    raw_lower_visible = event.get("raw_lower_visible", event.get("lower_visible"))
    normalized_upper_color = event.get("normalized_upper_color", event.get("upper_color"))
    normalized_upper_confidence = event.get(
        "normalized_upper_color_confidence",
        event.get("upper_color_confidence"),
    )
    normalized_upper_visible = event.get("normalized_upper_visible", event.get("upper_visible"))
    normalized_upper_probs = event.get("normalized_upper_color_probs", event.get("upper_color_probs"))
    normalized_lower_color = event.get("normalized_lower_color", event.get("lower_color"))
    normalized_lower_confidence = event.get(
        "normalized_lower_color_confidence",
        event.get("lower_color_confidence"),
    )
    normalized_lower_visible = event.get("normalized_lower_visible", event.get("lower_visible"))
    with get_conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO events(
                event_id, camera_id, video_id, live_source_id, track_id, person_id,
                start_time, end_time, start_timestamp_sec, end_timestamp_sec,
                observation_count, face_count, representative_observation_id,
                representative_face_id, representative_frame_path,
                upper_color, upper_color_confidence, upper_visible, upper_color_probs_json,
                lower_color, lower_color_confidence, lower_visible,
                raw_upper_color, raw_upper_color_confidence, raw_upper_visible, raw_upper_color_probs_json,
                raw_lower_color, raw_lower_color_confidence, raw_lower_visible,
                normalized_upper_color, normalized_upper_color_confidence, normalized_upper_visible,
                normalized_upper_color_probs_json,
                normalized_lower_color, normalized_lower_color_confidence, normalized_lower_visible,
                appearance_session_id, clothing_normalization_version,
                clothing_normalization_reason_json,
                identity_confidence, event_status, aggregation_version, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event["event_id"],
                event["camera_id"],
                event.get("video_id"),
                event.get("live_source_id"),
                event.get("track_id"),
                event.get("person_id"),
                event.get("start_time"),
                event.get("end_time"),
                event.get("start_timestamp_sec"),
                event.get("end_timestamp_sec"),
                int(event.get("observation_count") or len(observations)),
                int(event.get("face_count") or 0),
                event.get("representative_observation_id"),
                event.get("representative_face_id"),
                event.get("representative_frame_path"),
                normalized_upper_color,
                normalized_upper_confidence,
                None if normalized_upper_visible is None else (1 if normalized_upper_visible else 0),
                _json_or_none(normalized_upper_probs),
                normalized_lower_color,
                normalized_lower_confidence,
                None if normalized_lower_visible is None else (1 if normalized_lower_visible else 0),
                raw_upper_color,
                raw_upper_confidence,
                None if raw_upper_visible is None else (1 if raw_upper_visible else 0),
                _json_or_none(raw_upper_probs),
                raw_lower_color,
                raw_lower_confidence,
                None if raw_lower_visible is None else (1 if raw_lower_visible else 0),
                normalized_upper_color,
                normalized_upper_confidence,
                None if normalized_upper_visible is None else (1 if normalized_upper_visible else 0),
                _json_or_none(normalized_upper_probs),
                normalized_lower_color,
                normalized_lower_confidence,
                None if normalized_lower_visible is None else (1 if normalized_lower_visible else 0),
                event.get("appearance_session_id"),
                event.get("clothing_normalization_version") or "event_raw_v1",
                json.dumps(event.get("clothing_normalization_reason"), ensure_ascii=False)
                if event.get("clothing_normalization_reason") is not None
                else None,
                event.get("identity_confidence"),
                event.get("event_status") or "closed",
                event.get("aggregation_version") or "event_window_v1",
                event.get("created_at") or ts,
                ts,
            ),
        )
        conn.execute("DELETE FROM event_observations WHERE event_id = ?", (event["event_id"],))
        representative_id = event.get("representative_observation_id")
        for index, observation in enumerate(observations):
            conn.execute(
                """
                INSERT INTO event_observations(event_id, observation_id, sequence_index, is_representative, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    event["event_id"],
                    observation["observation_id"],
                    index,
                    1 if observation["observation_id"] == representative_id else 0,
                    ts,
                ),
            )
    result = get_event(event["event_id"])
    assert result is not None
    return result


def get_event(event_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM events WHERE event_id = ?", (event_id,)).fetchone()
    return _event_from_row(row)


def list_events(
    *,
    person_id: str | None = None,
    camera_id: str | None = None,
    upper_color: str | None = None,
    lower_color: str | None = None,
    identified: bool | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    clauses = []
    params: list[Any] = []
    if person_id:
        clauses.append("person_id = ?")
        params.append(person_id)
    if camera_id:
        clauses.append("camera_id = ?")
        params.append(camera_id)
    if upper_color:
        clauses.append("upper_color = ?")
        params.append(upper_color)
    if lower_color:
        clauses.append("lower_color = ?")
        params.append(lower_color)
    if identified is True:
        clauses.append("person_id IS NOT NULL")
    elif identified is False:
        clauses.append("person_id IS NULL")
    if start_time:
        clauses.append("(end_time IS NULL OR end_time >= ?)")
        params.append(start_time)
    if end_time:
        clauses.append("(start_time IS NULL OR start_time <= ?)")
        params.append(end_time)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"""
        SELECT *
        FROM events
        {where}
        ORDER BY COALESCE(start_time, ''), start_timestamp_sec, created_at
        LIMIT ? OFFSET ?
    """
    params.extend([max(1, min(int(limit), 5000)), max(0, int(offset))])
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [event for row in rows if (event := _event_from_row(row)) is not None]


def _appearance_session_from_row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    data = dict(row)
    data["upper_visible"] = None if data.get("upper_visible") is None else _bool_value(data.get("upper_visible"))
    data["lower_visible"] = None if data.get("lower_visible") is None else _bool_value(data.get("lower_visible"))
    data["profile"] = json.loads(data.pop("profile_json") or "{}")
    return data


def delete_appearance_sessions_for_person(person_id: str) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE events SET
                appearance_session_id = NULL,
                upper_color = COALESCE(raw_upper_color, upper_color),
                upper_color_confidence = COALESCE(raw_upper_color_confidence, upper_color_confidence),
                upper_visible = COALESCE(raw_upper_visible, upper_visible),
                upper_color_probs_json = COALESCE(raw_upper_color_probs_json, upper_color_probs_json),
                lower_color = COALESCE(raw_lower_color, lower_color),
                lower_color_confidence = COALESCE(raw_lower_color_confidence, lower_color_confidence),
                lower_visible = COALESCE(raw_lower_visible, lower_visible),
                normalized_upper_color = COALESCE(raw_upper_color, upper_color),
                normalized_upper_color_confidence = COALESCE(raw_upper_color_confidence, upper_color_confidence),
                normalized_upper_visible = COALESCE(raw_upper_visible, upper_visible),
                normalized_upper_color_probs_json = COALESCE(raw_upper_color_probs_json, upper_color_probs_json),
                normalized_lower_color = COALESCE(raw_lower_color, lower_color),
                normalized_lower_color_confidence = COALESCE(raw_lower_color_confidence, lower_color_confidence),
                normalized_lower_visible = COALESCE(raw_lower_visible, lower_visible),
                clothing_normalization_version = 'event_raw_v1',
                clothing_normalization_reason_json = NULL,
                updated_at = ?
            WHERE person_id = ?
            """,
            (now_iso(), person_id),
        )
        conn.execute("DELETE FROM appearance_sessions WHERE person_id = ?", (person_id,))


def add_appearance_session(session: dict[str, Any]) -> dict[str, Any]:
    ts = now_iso()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO appearance_sessions(
                session_id, person_id, start_time, end_time,
                start_timestamp_sec, end_timestamp_sec, event_count,
                upper_color, upper_color_confidence, upper_color_support, upper_visible,
                lower_color, lower_color_confidence, lower_color_support, lower_visible,
                profile_json, session_status, aggregation_version, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session["session_id"],
                session["person_id"],
                session.get("start_time"),
                session.get("end_time"),
                session.get("start_timestamp_sec"),
                session.get("end_timestamp_sec"),
                int(session.get("event_count") or 0),
                session.get("upper_color"),
                session.get("upper_color_confidence"),
                int(session.get("upper_color_support") or 0),
                None if session.get("upper_visible") is None else (1 if session.get("upper_visible") else 0),
                session.get("lower_color"),
                session.get("lower_color_confidence"),
                int(session.get("lower_color_support") or 0),
                None if session.get("lower_visible") is None else (1 if session.get("lower_visible") else 0),
                json.dumps(session.get("profile") or {}, ensure_ascii=False),
                session.get("session_status") or "active",
                session.get("aggregation_version") or "appearance_session_v1",
                session.get("created_at") or ts,
                ts,
            ),
        )
    result = get_appearance_session(session["session_id"])
    assert result is not None
    return result


def get_appearance_session(session_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM appearance_sessions WHERE session_id = ?", (session_id,)).fetchone()
    return _appearance_session_from_row(row)


def list_appearance_sessions(person_id: str | None = None) -> list[dict[str, Any]]:
    params: list[Any] = []
    where = ""
    if person_id:
        where = "WHERE person_id = ?"
        params.append(person_id)
    with get_conn() as conn:
        rows = conn.execute(
            f"""
            SELECT *
            FROM appearance_sessions
            {where}
            ORDER BY person_id, COALESCE(start_time, ''), start_timestamp_sec, created_at
            """,
            params,
        ).fetchall()
    return [session for row in rows if (session := _appearance_session_from_row(row)) is not None]


def update_event_clothing_normalization(event_id: str, payload: dict[str, Any]) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE events SET
                appearance_session_id = ?,
                upper_color = ?,
                upper_color_confidence = ?,
                upper_visible = ?,
                upper_color_probs_json = ?,
                lower_color = ?,
                lower_color_confidence = ?,
                lower_visible = ?,
                normalized_upper_color = ?,
                normalized_upper_color_confidence = ?,
                normalized_upper_visible = ?,
                normalized_upper_color_probs_json = ?,
                normalized_lower_color = ?,
                normalized_lower_color_confidence = ?,
                normalized_lower_visible = ?,
                clothing_normalization_version = ?,
                clothing_normalization_reason_json = ?,
                updated_at = ?
            WHERE event_id = ?
            """,
            (
                payload.get("appearance_session_id"),
                payload.get("upper_color"),
                payload.get("upper_color_confidence"),
                None if payload.get("upper_visible") is None else (1 if payload.get("upper_visible") else 0),
                _json_or_none(payload.get("upper_color_probs")),
                payload.get("lower_color"),
                payload.get("lower_color_confidence"),
                None if payload.get("lower_visible") is None else (1 if payload.get("lower_visible") else 0),
                payload.get("normalized_upper_color"),
                payload.get("normalized_upper_color_confidence"),
                None
                if payload.get("normalized_upper_visible") is None
                else (1 if payload.get("normalized_upper_visible") else 0),
                _json_or_none(payload.get("normalized_upper_color_probs")),
                payload.get("normalized_lower_color"),
                payload.get("normalized_lower_color_confidence"),
                None
                if payload.get("normalized_lower_visible") is None
                else (1 if payload.get("normalized_lower_visible") else 0),
                payload.get("clothing_normalization_version") or "appearance_session_v1",
                json.dumps(payload.get("clothing_normalization_reason"), ensure_ascii=False)
                if payload.get("clothing_normalization_reason") is not None
                else None,
                now_iso(),
                event_id,
            ),
        )


def update_person_event_stats(person_id: str) -> None:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(DISTINCT e.event_id) AS event_count,
                COUNT(DISTINCT eo.observation_id) AS observation_count
            FROM events e
            LEFT JOIN event_observations eo ON eo.event_id = e.event_id
            WHERE e.person_id = ?
            """,
            (person_id,),
        ).fetchone()
        latest = conn.execute(
            """
            SELECT event_id, camera_id, end_time, start_time
            FROM events
            WHERE person_id = ?
            ORDER BY COALESCE(end_time, start_time, '') DESC, end_timestamp_sec DESC
            LIMIT 1
            """,
            (person_id,),
        ).fetchone()
        conn.execute(
            """
            UPDATE persons SET
                event_count = ?,
                observation_count = ?,
                last_event_id = ?,
                last_seen_camera_id = ?,
                updated_at = ?
            WHERE person_id = ?
            """,
            (
                int(row["event_count"] or 0) if row else 0,
                int(row["observation_count"] or 0) if row else 0,
                latest["event_id"] if latest else None,
                latest["camera_id"] if latest else None,
                now_iso(),
                person_id,
            ),
        )


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
        conn.execute("DELETE FROM appearance_sessions")
        conn.execute("DELETE FROM person_faces")
        conn.execute("DELETE FROM persons")
        conn.execute("UPDATE person_observations SET person_id = NULL, updated_at = ?", (now_iso(),))
        conn.execute(
            """
            UPDATE events SET
                person_id = NULL,
                identity_confidence = NULL,
                appearance_session_id = NULL,
                upper_color = COALESCE(raw_upper_color, upper_color),
                upper_color_confidence = COALESCE(raw_upper_color_confidence, upper_color_confidence),
                upper_visible = COALESCE(raw_upper_visible, upper_visible),
                upper_color_probs_json = COALESCE(raw_upper_color_probs_json, upper_color_probs_json),
                lower_color = COALESCE(raw_lower_color, lower_color),
                lower_color_confidence = COALESCE(raw_lower_color_confidence, lower_color_confidence),
                lower_visible = COALESCE(raw_lower_visible, lower_visible),
                normalized_upper_color = COALESCE(raw_upper_color, upper_color),
                normalized_upper_color_confidence = COALESCE(raw_upper_color_confidence, upper_color_confidence),
                normalized_upper_visible = COALESCE(raw_upper_visible, upper_visible),
                normalized_upper_color_probs_json = COALESCE(raw_upper_color_probs_json, upper_color_probs_json),
                normalized_lower_color = COALESCE(raw_lower_color, lower_color),
                normalized_lower_color_confidence = COALESCE(raw_lower_color_confidence, lower_color_confidence),
                normalized_lower_visible = COALESCE(raw_lower_visible, lower_visible),
                clothing_normalization_version = 'event_raw_v1',
                clothing_normalization_reason_json = NULL,
                updated_at = ?
            """,
            (now_iso(),),
        )


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
        conn.execute(
            """
            UPDATE person_observations
            SET person_id = ?, updated_at = ?
            WHERE face_record_id = ?
            """,
            (person_id, now_iso(), face_id),
        )


def update_person_face_score(person_id: str, face_id: str, score_to_person: float | None) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE person_faces
            SET score_to_person = ?
            WHERE person_id = ? AND face_id = ?
            """,
            (score_to_person, person_id, face_id),
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


def merge_person_into(source_person_id: str, target_person_id: str) -> dict[str, Any]:
    if source_person_id == target_person_id:
        raise ValueError("source_person_id and target_person_id must be different")

    ts = now_iso()
    with get_conn() as conn:
        source = conn.execute(
            "SELECT person_id FROM persons WHERE person_id = ?",
            (source_person_id,),
        ).fetchone()
        target = conn.execute(
            "SELECT person_id FROM persons WHERE person_id = ?",
            (target_person_id,),
        ).fetchone()
        if source is None:
            raise KeyError(f"source person not found: {source_person_id}")
        if target is None:
            raise KeyError(f"target person not found: {target_person_id}")

        source_face_rows = conn.execute(
            """
            SELECT fr.face_id, fr.video_id
            FROM face_records fr
            JOIN person_faces pf ON pf.face_id = fr.face_id
            WHERE pf.person_id = ?
            """,
            (source_person_id,),
        ).fetchall()
        source_face_ids = [row["face_id"] for row in source_face_rows]
        video_ids = sorted({row["video_id"] for row in source_face_rows if row["video_id"]})

        conn.execute(
            """
            UPDATE person_faces
            SET person_id = ?
            WHERE person_id = ?
            """,
            (target_person_id, source_person_id),
        )
        moved_faces = conn.execute("SELECT changes()").fetchone()[0]

        conn.execute(
            """
            UPDATE person_observations
            SET person_id = ?, updated_at = ?
            WHERE person_id = ?
            """,
            (target_person_id, ts, source_person_id),
        )
        moved_observations = conn.execute("SELECT changes()").fetchone()[0]

        conn.execute(
            """
            UPDATE events
            SET person_id = ?, appearance_session_id = NULL, updated_at = ?
            WHERE person_id = ?
            """,
            (target_person_id, ts, source_person_id),
        )
        moved_events = conn.execute("SELECT changes()").fetchone()[0]

        conn.execute("DELETE FROM appearance_sessions WHERE person_id = ?", (source_person_id,))
        deleted_sessions = conn.execute("SELECT changes()").fetchone()[0]
        conn.execute("DELETE FROM persons WHERE person_id = ?", (source_person_id,))

    return {
        "source_person_id": source_person_id,
        "target_person_id": target_person_id,
        "moved_faces": moved_faces,
        "moved_observations": moved_observations,
        "moved_events": moved_events,
        "deleted_sessions": deleted_sessions,
        "source_face_ids": source_face_ids,
        "video_ids": video_ids,
    }


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
