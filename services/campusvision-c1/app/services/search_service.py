from __future__ import annotations

import shutil
import uuid
from hashlib import sha1
from pathlib import Path
from typing import BinaryIO

import cv2

from app.core.config import settings
from app.storage import db
from app.vision.face_engine import default_similarity_threshold, get_face_engine
from app.vision.vector_math import cosine_similarity


def save_query_image(fileobj: BinaryIO, filename: str, search_id: str) -> str:
    settings.ensure_dirs()

    suffix = Path(filename).suffix.lower() or ".jpg"
    dest_dir = settings.query_uploads_dir / search_id
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest = dest_dir / f"{uuid.uuid4().hex}{suffix}"
    with dest.open("wb") as f:
        shutil.copyfileobj(fileobj, f)
    return str(dest)


def load_embeddings_from_images(paths: list[str]) -> list[list[float]]:
    engine = get_face_engine()
    embeddings: list[list[float]] = []

    for path in paths:
        image = cv2.imread(path)
        if image is None:
            continue

        boxes = engine.detect_faces(image)
        if not boxes:
            continue

        embeddings.extend(engine.embed_faces(image, boxes))

    return embeddings


def camera_lookup() -> dict[str, dict]:
    return {cam["camera_id"]: cam for cam in db.list_cameras()}


def build_match(record: dict, score: float, cameras: dict[str, dict]) -> dict:
    camera = cameras.get(record["camera_id"], {})
    return {
        "face_id": record["face_id"],
        "score": round(float(score), 6),
        "camera_id": record["camera_id"],
        "camera_name": camera.get("name"),
        "location": camera.get("location"),
        "lat": camera.get("lat"),
        "lng": camera.get("lng"),
        "video_id": record["video_id"],
        "video_timestamp_sec": float(record["video_timestamp_sec"]),
        "captured_at": record.get("captured_at"),
        "frame_url": f"/api/v1/media/frame/{record['face_id']}",
    }


def _time_display(seconds: float | int | None) -> str | None:
    if seconds is None:
        return None

    total_ms = int(round(float(seconds) * 1000))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def trajectory_from_matches(matches: list[dict]) -> list[dict]:
    def sort_key(m: dict):
        return (m.get("captured_at") or "", m.get("video_timestamp_sec") or 0)

    trajectory = []
    for m in sorted(matches, key=sort_key):
        trajectory.append(
            {
                "time": m.get("captured_at"),
                "video_timestamp_sec": m.get("video_timestamp_sec"),
                "captured_at": m.get("captured_at"),
                "time_display": _time_display(m.get("video_timestamp_sec")),
                "camera_id": m["camera_id"],
                "camera_name": m.get("camera_name"),
                "location": m.get("location"),
                "lat": m.get("lat"),
                "lng": m.get("lng"),
                "score": m["score"],
                "frame_url": m["frame_url"],
                "face_id": m["face_id"],
            }
        )
    return trajectory


def _appearance_id(event: dict) -> str:
    raw = "|".join(
        [
            str(event["video_id"]),
            str(event["camera_id"]),
            f"{event['start_sec']:.3f}",
            f"{event['end_sec']:.3f}",
            str(event["best_face_id"]),
        ]
    )
    return sha1(raw.encode("utf-8")).hexdigest()[:16]


def _event_from_group(group: list[dict]) -> dict:
    best = max(group, key=lambda m: m["score"])
    start_sec = min(float(m["video_timestamp_sec"]) for m in group)
    end_sec = max(float(m["video_timestamp_sec"]) for m in group)
    event = {
        "appearance_id": "",
        "video_id": best["video_id"],
        "camera_id": best["camera_id"],
        "camera_name": best.get("camera_name"),
        "location": best.get("location"),
        "lat": best.get("lat"),
        "lng": best.get("lng"),
        "start_sec": start_sec,
        "end_sec": end_sec,
        "duration_sec": round(end_sec - start_sec, 3),
        "start_time_display": _time_display(start_sec),
        "end_time_display": _time_display(end_sec),
        "hit_count": len(group),
        "best_score": best["score"],
        "best_face_id": best["face_id"],
        "best_frame_url": best["frame_url"],
        "match_face_ids": [m["face_id"] for m in group],
        "best_match": best,
    }
    event["appearance_id"] = _appearance_id(event)
    return event


def appearance_events_from_matches(matches: list[dict], max_gap_sec: float = 3.0) -> list[dict]:
    ordered = sorted(
        matches,
        key=lambda m: (
            m.get("video_id") or "",
            m.get("camera_id") or "",
            float(m.get("video_timestamp_sec") or 0),
        ),
    )

    events: list[dict] = []
    current_group: list[dict] = []
    gap = max(0.0, float(max_gap_sec))

    for match in ordered:
        if not current_group:
            current_group = [match]
            continue

        previous = current_group[-1]
        same_stream = (
            match.get("video_id") == previous.get("video_id")
            and match.get("camera_id") == previous.get("camera_id")
        )
        time_delta = float(match.get("video_timestamp_sec") or 0) - float(
            previous.get("video_timestamp_sec") or 0
        )

        if same_stream and time_delta <= gap:
            current_group.append(match)
        else:
            events.append(_event_from_group(current_group))
            current_group = [match]

    if current_group:
        events.append(_event_from_group(current_group))

    return sorted(events, key=lambda e: (e["start_sec"], e["video_id"], e["camera_id"]))


def search_by_images(
    query_paths: list[str],
    top_k: int = 20,
    min_score: float | None = None,
    max_gap_sec: float = 3.0,
    camera_id: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
) -> dict:
    search_id = uuid.uuid4().hex
    min_score = default_similarity_threshold() if min_score is None else float(min_score)
    query_embeddings = load_embeddings_from_images(query_paths)

    if not query_embeddings:
        result = {
            "search_id": search_id,
            "engine": get_face_engine().name,
            "matches": [],
            "trajectory": [],
            "appearance_events": [],
            "warning": "No face/target embedding extracted from query images.",
        }
        db.add_search(
            {
                "search_id": search_id,
                "query_paths": query_paths,
                "params": {
                    "top_k": top_k,
                    "min_score": min_score,
                    "max_gap_sec": max_gap_sec,
                    "camera_id": camera_id,
                    "start_time": start_time,
                    "end_time": end_time,
                },
                "result": result,
            }
        )
        return result

    records = db.list_face_records(camera_id=camera_id, start_time=start_time, end_time=end_time)
    cameras = camera_lookup()

    scored: list[dict] = []
    for rec in records:
        score = max(cosine_similarity(q, rec["embedding"]) for q in query_embeddings)
        if score >= min_score:
            scored.append(build_match(rec, score, cameras))

    scored.sort(key=lambda x: x["score"], reverse=True)
    matches = scored[: max(1, int(top_k))]
    trajectory = trajectory_from_matches(matches)
    appearance_events = appearance_events_from_matches(scored, max_gap_sec=max_gap_sec)

    result = {
        "search_id": search_id,
        "engine": get_face_engine().name,
        "matches": matches,
        "trajectory": trajectory,
        "appearance_events": appearance_events,
    }

    db.add_search(
        {
            "search_id": search_id,
            "query_paths": query_paths,
            "params": {
                "top_k": top_k,
                "min_score": min_score,
                "max_gap_sec": max_gap_sec,
                "camera_id": camera_id,
                "start_time": start_time,
                "end_time": end_time,
            },
            "result": result,
        }
    )
    return result
