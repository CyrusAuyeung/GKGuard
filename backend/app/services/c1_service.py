from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import httpx


C1_BASE_URL = os.getenv("C1_BASE_URL", "http://127.0.0.1:18000").rstrip("/")
REQUEST_TIMEOUT = float(os.getenv("C1_TIMEOUT_SEC", "30"))


class C1ServiceError(RuntimeError):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def _absolute_media_url(path: str | None) -> str | None:
    if not path:
        return None
    if path.startswith("http://") or path.startswith("https://"):
        return path
    if not path.startswith("/api/v1/media/"):
        return f"{C1_BASE_URL}{path if path.startswith('/') else '/' + path}"
    return "/c1/media/" + path.removeprefix("/api/v1/media/")


def _time_parts(value: str | None, fallback: str | None = None) -> tuple[str, str]:
    raw = value or fallback or ""
    if not raw:
        return "--:--:--", "未知时间"
    normalized = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
        return parsed.strftime("%H:%M:%S"), parsed.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        if "T" in raw:
            date, _, time = raw.partition("T")
            return time[:8] or raw, f"{date} {time[:8]}".strip()
        return raw[:8], raw


def _record_from_match(match: dict[str, Any], index: int) -> dict[str, Any]:
    time, full_time = _time_parts(match.get("captured_at"), match.get("time_display"))
    location = match.get("location") or match.get("camera_name") or match.get("camera_id") or "未知位置"
    camera_id = match.get("camera_id") or "C1"
    score = float(match.get("score") or match.get("best_score") or 0)
    frame_url = _absolute_media_url(match.get("frame_url") or match.get("best_frame_url"))
    face_id = match.get("face_id") or match.get("best_face_id") or f"c1-{index}"
    return {
        "id": index,
        "title": f"记录{index}",
        "time": time,
        "fullTime": full_time,
        "location": location,
        "camera": match.get("camera_name") or camera_id,
        "cameraId": camera_id,
        "similarity": score,
        "note": "来自 C1 CampusVision 的真实检索结果",
        "sceneClass": f"scene-{((index - 1) % 5) + 1}",
        "progress": min(92, max(8, 8 + index * 13)),
        "frameUrl": frame_url,
        "faceId": face_id,
        "videoId": match.get("video_id"),
        "videoTimestampSec": match.get("video_timestamp_sec"),
    }


def _route_point_from_item(item: dict[str, Any], index: int, total: int) -> dict[str, Any]:
    time, _ = _time_parts(item.get("time") or item.get("captured_at"), item.get("time_display"))
    x = 18 + ((index * 17) % 68)
    y = 76 - ((index * 11) % 52)
    point: dict[str, Any] = {
        "id": index,
        "time": time,
        "location": item.get("location") or item.get("camera_name") or item.get("camera_id") or "未知位置",
        "x": x,
        "y": y,
        "cameraId": item.get("camera_id"),
        "score": item.get("score"),
    }
    if index == 1:
        point["kind"] = "start"
    if index == total:
        point["kind"] = "end"
    return point


def _summarize_person_result(raw: dict[str, Any]) -> dict[str, Any]:
    persons = raw.get("persons") or []
    person = persons[0] if persons else {}
    matches = person.get("matches") or []
    trajectory = person.get("trajectory") or []
    selected_matches = matches[:5]
    records = [_record_from_match(match, index + 1) for index, match in enumerate(selected_matches)]
    if not records:
        records = [_record_from_match(item, index + 1) for index, item in enumerate(trajectory[:5])]

    total_points = max(1, min(8, len(trajectory)))
    route_points = [
        _route_point_from_item(item, index + 1, total_points)
        for index, item in enumerate(trajectory[:total_points])
    ]

    representative_face = _absolute_media_url(person.get("representative_face_crop_url"))
    if not representative_face and records:
        representative_face = _absolute_media_url(f"/api/v1/media/face/{records[0].get('faceId')}")

    return {
        "source": "c1",
        "baseUrl": C1_BASE_URL,
        "searchId": raw.get("search_id"),
        "engine": raw.get("engine"),
        "warning": raw.get("warning"),
        "ambiguous": raw.get("ambiguous", False),
        "person": {
            "personId": person.get("person_id"),
            "score": person.get("score"),
            "confidence": person.get("confidence"),
            "faceCount": person.get("face_count"),
            "representativeFaceUrl": representative_face,
        },
        "records": records,
        "routePoints": route_points,
        "appearanceEvents": person.get("appearance_events") or [],
        "raw": raw,
    }


def _request(method: str, path: str, **kwargs: Any) -> httpx.Response:
    url = f"{C1_BASE_URL}{path}"
    try:
        with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
            response = client.request(method, url, **kwargs)
            response.raise_for_status()
            return response
    except httpx.HTTPStatusError as exc:
        raise C1ServiceError(f"C1 returned HTTP {exc.response.status_code}", exc.response.status_code) from exc
    except httpx.HTTPError as exc:
        raise C1ServiceError(f"C1 unavailable: {exc}") from exc


def get_status() -> dict[str, Any]:
    status: dict[str, Any] = {"baseUrl": C1_BASE_URL, "reachable": False}
    try:
        openapi = _request("GET", "/openapi.json").json()
        status.update({"reachable": True, "title": openapi.get("info", {}).get("title"), "version": openapi.get("info", {}).get("version")})
    except C1ServiceError as exc:
        status["error"] = str(exc)

    try:
        health = _request("GET", "/health").json()
        status["health"] = health
        status["healthOk"] = True
    except C1ServiceError as exc:
        status["healthOk"] = False
        status["healthError"] = str(exc)
    return status


def list_people() -> list[dict[str, Any]]:
    people = _request("GET", "/api/v1/persons").json()
    for person in people:
        person["representative_face_crop_url"] = _absolute_media_url(person.get("representative_face_crop_url"))
        person["representative_frame_url"] = _absolute_media_url(person.get("representative_frame_url"))
    return people


def list_videos() -> list[dict[str, Any]]:
    return _request("GET", "/api/v1/videos").json()


def search_person_by_image(
    filename: str,
    content: bytes,
    content_type: str | None,
    top_k: int,
    min_score: float | None,
    max_gap_sec: float,
) -> dict[str, Any]:
    files = {"files": (filename, content, content_type or "application/octet-stream")}
    data: dict[str, str] = {"top_k": str(top_k), "max_gap_sec": str(max_gap_sec)}
    if min_score is not None:
        data["min_score"] = str(min_score)
    raw = _request("POST", "/api/v1/search/person-by-image", files=files, data=data).json()
    return _summarize_person_result(raw)


def fetch_media(kind: str, face_id: str) -> tuple[bytes, str]:
    if kind not in {"frame", "face"}:
        raise C1ServiceError("Unsupported C1 media kind", 400)
    response = _request("GET", f"/api/v1/media/{kind}/{face_id}")
    return response.content, response.headers.get("content-type", "image/jpeg")