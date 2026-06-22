from __future__ import annotations

import os
import json
import ipaddress
import time
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Any
from urllib.parse import urlparse

import httpx


DEFAULT_C1_BASE_URL = "http://127.0.0.1:18000"
C1_BASE_URL = os.getenv("C1_BASE_URL", DEFAULT_C1_BASE_URL).rstrip("/")
REQUEST_TIMEOUT = float(os.getenv("C1_TIMEOUT_SEC", "30"))
C1_PROBE_TIMEOUT = float(os.getenv("C1_PROBE_TIMEOUT_SEC", "1.5"))
C1_STATUS_CACHE_TTL = float(os.getenv("C1_STATUS_CACHE_TTL_SEC", "15"))
C1_MEDIA_CACHE_TTL = float(os.getenv("C1_MEDIA_CACHE_TTL_SEC", "300"))
C1_MEDIA_CACHE_MAX_ITEMS = int(os.getenv("C1_MEDIA_CACHE_MAX_ITEMS", "64"))
C1_API_KEY = (os.getenv("CAMPUSVISION_API_KEY") or os.getenv("C1_API_KEY") or "").strip()
DEFAULT_C1_ALLOWED_HOSTS = "localhost,127.0.0.1,::1"
_selected_base_url: str | None = None
RETRYABLE_STATUS_CODES = {502, 503, 504}
_status_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_media_cache: OrderedDict[tuple[str, str, str], tuple[float, bytes, str]] = OrderedDict()
_cache_lock = RLock()


class C1ServiceError(RuntimeError):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def _normalize_base_url(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().rstrip("/")
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.path not in {"", "/"}:
        return None
    if not _host_allowed(parsed.hostname):
        return None
    return normalized


def _allowed_c1_hosts() -> set[str]:
    configured_hosts = os.getenv("C1_ALLOWED_HOSTS", DEFAULT_C1_ALLOWED_HOSTS)
    return {host.strip().strip("[]").lower() for host in configured_hosts.replace(";", ",").split(",") if host.strip()}


def _looks_like_ip_address(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True


def _host_allowed(hostname: str | None) -> bool:
    if not hostname:
        return False
    host = hostname.strip().strip("[]").lower()
    allowed_hosts = _allowed_c1_hosts()
    if host in allowed_hosts:
        return True
    try:
        ip_address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return any(
        ip_address == ipaddress.ip_address(allowed_host)
        for allowed_host in allowed_hosts
        if _looks_like_ip_address(allowed_host)
    )


def _split_urls(value: str | None) -> list[str]:
    if not value:
        return []
    urls: list[str] = []
    for raw_url in value.replace(";", ",").split(","):
        normalized = _normalize_base_url(raw_url)
        if normalized:
            urls.append(normalized)
    return urls


def _config_paths() -> list[Path]:
    explicit_path = os.getenv("C1_CONFIG_PATH")
    if explicit_path:
        return [Path(explicit_path)]

    appdata = os.getenv("APPDATA")
    if appdata:
        return [Path(appdata) / "GKGuard" / "c1-connection.json"]
    return []


def _load_config_candidate_urls() -> list[str]:
    urls: list[str] = []
    for config_path in _config_paths():
        try:
            if not config_path.exists():
                continue
            config = json.loads(config_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue

        if isinstance(config, dict):
            for key in ("baseUrl", "base_url"):
                urls.extend(_split_urls(config.get(key)))
            for key in ("candidateUrls", "candidate_urls", "candidates"):
                candidate_value = config.get(key)
                if isinstance(candidate_value, list):
                    for item in candidate_value:
                        urls.extend(_split_urls(str(item)))
                elif isinstance(candidate_value, str):
                    urls.extend(_split_urls(candidate_value))
        elif isinstance(config, list):
            for item in config:
                urls.extend(_split_urls(str(item)))
    return urls


def _candidate_urls() -> list[str]:
    urls: list[str] = []
    urls.extend(_split_urls(os.getenv("C1_BASE_URL")))
    urls.extend(_split_urls(os.getenv("C1_CANDIDATE_URLS")))
    urls.extend(_load_config_candidate_urls())
    urls.extend(_split_urls(C1_BASE_URL))

    deduped: list[str] = []
    for url in urls:
        if url not in deduped:
            deduped.append(url)
    return deduped


def _current_base_url() -> str:
    candidates = _candidate_urls()
    return _selected_base_url or (candidates[0] if candidates else DEFAULT_C1_BASE_URL)


def _is_campusvision_identity(openapi_body: Any, health_body: Any) -> bool:
    openapi_info = openapi_body.get("info", {}) if isinstance(openapi_body, dict) else {}
    if not isinstance(openapi_info, dict):
        openapi_info = {}
    title = str(openapi_info.get("title") or "").strip()
    description = ""
    if isinstance(openapi_body, dict):
        description = str(openapi_body.get("description") or openapi_info.get("description") or "")
    health_app = str(health_body.get("app") or "").strip() if isinstance(health_body, dict) else ""
    return "CampusVision C1" in {title, health_app} or "CampusVision C1" in description


def _is_healthy_c1_status(status: dict[str, Any]) -> bool:
    return bool(status.get("reachable") and status.get("healthOk") and status.get("identityOk"))


def _cache_deadline(ttl_seconds: float) -> float:
    return time.monotonic() + max(0, ttl_seconds)


def _store_status_cache(base_url: str, status: dict[str, Any]) -> None:
    with _cache_lock:
        if C1_STATUS_CACHE_TTL <= 0 or not _is_healthy_c1_status(status):
            _status_cache.pop(base_url, None)
            return
        _status_cache[base_url] = (_cache_deadline(C1_STATUS_CACHE_TTL), dict(status))


def _cached_status_for_url(base_url: str) -> dict[str, Any]:
    if C1_STATUS_CACHE_TTL > 0:
        with _cache_lock:
            cached = _status_cache.get(base_url)
            if cached and cached[0] > time.monotonic():
                return dict(cached[1])

    status = _status_for_url(base_url)
    _store_status_cache(base_url, status)
    return status


def _status_for_url(base_url: str) -> dict[str, Any]:
    status: dict[str, Any] = {"baseUrl": base_url, "reachable": False, "identityOk": False}
    openapi_body: Any = None
    health_body: Any = None
    try:
        with httpx.Client(timeout=C1_PROBE_TIMEOUT) as client:
            openapi = client.get(f"{base_url}/openapi.json")
            openapi.raise_for_status()
            openapi_body = openapi.json()
            openapi_info = openapi_body.get("info", {}) if isinstance(openapi_body, dict) else {}
            if not isinstance(openapi_info, dict):
                openapi_info = {}
            status.update({
                "reachable": True,
                "title": openapi_info.get("title"),
                "version": openapi_info.get("version"),
            })
    except (httpx.HTTPError, ValueError, AttributeError) as exc:
        status["error"] = str(exc)

    try:
        with httpx.Client(timeout=C1_PROBE_TIMEOUT) as client:
            health = client.get(f"{base_url}/health")
            health.raise_for_status()
            status["reachable"] = True
            health_body = health.json()
            status["health"] = health_body
            status["healthOk"] = True
    except (httpx.HTTPError, ValueError) as exc:
        status["healthOk"] = False
        status["healthError"] = str(exc)
    status["identityOk"] = _is_campusvision_identity(openapi_body, health_body)
    return status


def _resolve_base_url() -> str:
    global _selected_base_url

    candidates = _candidate_urls()
    if not candidates:
        _selected_base_url = None
        raise C1ServiceError("No allowed CampusVision C1 candidate URLs are configured.", 400)
    if _selected_base_url in candidates:
        selected_status = _cached_status_for_url(_selected_base_url)
        if _is_healthy_c1_status(selected_status):
            return _selected_base_url

    for base_url in candidates:
        status = _cached_status_for_url(base_url)
        if _is_healthy_c1_status(status):
            _selected_base_url = base_url
            return base_url

    _selected_base_url = None
    raise C1ServiceError("No healthy CampusVision C1 candidate passed identity checks.", 502)


def _absolute_media_url(path: str | None) -> str | None:
    if not path:
        return None
    if path.startswith("http://") or path.startswith("https://"):
        return path
    if not path.startswith("/api/v1/media/"):
        return f"{_current_base_url()}{path if path.startswith('/') else '/' + path}"
    return "/c1/media/" + path.removeprefix("/api/v1/media/")


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _first_number(*values: Any) -> float | None:
    for value in values:
        number = _number(value)
        if number is not None:
            return number
    return None


def _normalize_bbox(
    box: dict[str, Any] | list[Any] | tuple[Any, ...] | None,
    image_width: Any = None,
    image_height: Any = None,
) -> dict[str, Any] | None:
    if isinstance(box, (list, tuple)) and len(box) >= 4:
        box = {"x1": box[0], "y1": box[1], "x2": box[2], "y2": box[3]}
    if not isinstance(box, dict):
        return None

    if isinstance(box.get("bbox"), (dict, list, tuple)):
        return _normalize_bbox(box.get("bbox"), image_width=image_width, image_height=image_height)

    image_width = _first_number(image_width, box.get("image_width"), box.get("frame_width"), box.get("width_px"))
    image_height = _first_number(image_height, box.get("image_height"), box.get("frame_height"), box.get("height_px"))

    x1 = _first_number(box.get("x1"), box.get("left"), box.get("x"))
    y1 = _first_number(box.get("y1"), box.get("top"), box.get("y"))
    x2 = _first_number(box.get("x2"), box.get("right"))
    y2 = _first_number(box.get("y2"), box.get("bottom"))
    width = _first_number(box.get("width"), box.get("w"))
    height = _first_number(box.get("height"), box.get("h"))

    if x1 is None or y1 is None:
        return None
    if x2 is None and width is not None:
        x2 = x1 + width
    if y2 is None and height is not None:
        y2 = y1 + height
    if x2 is None or y2 is None:
        return None

    width = width if width is not None else x2 - x1
    height = height if height is not None else y2 - y1

    values = [x1, y1, x2, y2, width, height]
    looks_normalized = all(0 <= value <= 1 for value in values if value is not None)
    if looks_normalized:
        left_pct = x1 * 100
        top_pct = y1 * 100
        width_pct = width * 100
        height_pct = height * 100
        if image_width and image_height:
            x1 *= image_width
            x2 *= image_width
            width *= image_width
            y1 *= image_height
            y2 *= image_height
            height *= image_height
    else:
        left_pct = _first_number(box.get("leftPct"), box.get("left_pct"), box.get("left_percent"))
        top_pct = _first_number(box.get("topPct"), box.get("top_pct"), box.get("top_percent"))
        width_pct = _first_number(box.get("widthPct"), box.get("width_pct"), box.get("width_percent"))
        height_pct = _first_number(box.get("heightPct"), box.get("height_pct"), box.get("height_percent"))
        if left_pct is None and image_width:
            left_pct = x1 / image_width * 100
        if top_pct is None and image_height:
            top_pct = y1 / image_height * 100
        if width_pct is None and image_width:
            width_pct = width / image_width * 100
        if height_pct is None and image_height:
            height_pct = height / image_height * 100

    if left_pct is None:
        left_pct = _first_number(box.get("leftPct"), box.get("left_pct"), box.get("left_percent"))
    if top_pct is None:
        top_pct = _first_number(box.get("topPct"), box.get("top_pct"), box.get("top_percent"))
    if width_pct is None:
        width_pct = _first_number(box.get("widthPct"), box.get("width_pct"), box.get("width_percent"))
    if height_pct is None:
        height_pct = _first_number(box.get("heightPct"), box.get("height_pct"), box.get("height_percent"))

    if width <= 0 or height <= 0:
        return None

    payload: dict[str, Any] = {
        "x1": round(x1, 4),
        "y1": round(y1, 4),
        "x2": round(x2, 4),
        "y2": round(y2, 4),
        "width": round(width, 4),
        "height": round(height, 4),
    }
    for target_key, value in (
        ("leftPct", left_pct),
        ("topPct", top_pct),
        ("widthPct", width_pct),
        ("heightPct", height_pct),
        ("score", _first_number(box.get("score"), box.get("det_score"), box.get("confidence"))),
    ):
        if value is not None:
            payload[target_key] = round(value, 4)
    return payload


def _query_face_from_item(item: dict[str, Any]) -> dict[str, Any]:
    bbox = _normalize_bbox(
        item.get("bbox") or item.get("face_box"),
        image_width=item.get("image_width"),
        image_height=item.get("image_height"),
    )
    return {
        "index": item.get("index"),
        "imageIndex": item.get("image_index"),
        "faceIndex": item.get("face_index"),
        "score": item.get("score"),
        "imageWidth": item.get("image_width"),
        "imageHeight": item.get("image_height"),
        "bbox": bbox,
    }


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
    face_url = _absolute_media_url(match.get("face_url") or match.get("face_crop_url") or f"/api/v1/media/face/{face_id}")
    raw_box = match.get("bbox") or match.get("face_box") or (match.get("best_match") or {}).get("bbox")
    face_box = _normalize_bbox(
        raw_box,
        image_width=match.get("image_width") or match.get("frame_width"),
        image_height=match.get("image_height") or match.get("frame_height"),
    )
    return {
        "id": index,
        "title": f"记录{index}",
        "time": time,
        "fullTime": full_time,
        "location": location,
        "camera": match.get("camera_name") or camera_id,
        "cameraId": camera_id,
        "similarity": score,
        "note": "来自 CampusVision C1 的真实检索结果",
        "sceneClass": f"scene-{((index - 1) % 5) + 1}",
        "progress": min(92, max(8, 8 + index * 13)),
        "frameUrl": frame_url,
        "faceUrl": face_url,
        "faceId": face_id,
        "faceBox": face_box,
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
    query_faces = [_query_face_from_item(item) for item in raw.get("query_faces") or []]
    selected_query_face = raw.get("selected_query_face")

    return {
        "source": "c1",
        "baseUrl": C1_BASE_URL,
        "searchId": raw.get("search_id"),
        "engine": raw.get("engine"),
        "warning": raw.get("warning"),
        "ambiguous": raw.get("ambiguous", False),
        "queryFaces": query_faces,
        "selectedQueryFace": _query_face_from_item(selected_query_face) if isinstance(selected_query_face, dict) else None,
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


def _request_once(base_url: str, method: str, path: str, **kwargs: Any) -> httpx.Response:
    url = f"{base_url}{path}"
    if C1_API_KEY:
        headers = dict(kwargs.pop("headers", {}) or {})
        headers.setdefault("X-CampusVision-API-Key", C1_API_KEY)
        kwargs["headers"] = headers
    with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
        response = client.request(method, url, **kwargs)
        response.raise_for_status()
        return response


def _ordered_request_urls(primary_url: str | None = None) -> list[str]:
    urls: list[str] = []
    for url in [primary_url, *_candidate_urls()]:
        if url and url not in urls:
            urls.append(url)
    return urls


def _healthy_request_urls(primary_url: str | None = None) -> list[str]:
    urls: list[str] = []
    for url in _ordered_request_urls(primary_url):
        status = _cached_status_for_url(url)
        if _is_healthy_c1_status(status):
            urls.append(url)
    return urls


def _request(method: str, path: str, primary_url: str | None = None, **kwargs: Any) -> httpx.Response:
    global _selected_base_url

    base_url = primary_url or _resolve_base_url()
    last_error: Exception | None = None
    request_urls = _healthy_request_urls(base_url)
    if not request_urls:
        _selected_base_url = None
        raise C1ServiceError("No healthy CampusVision C1 candidate passed identity checks.", 502)

    for request_url in request_urls:
        try:
            response = _request_once(request_url, method, path, **kwargs)
            _selected_base_url = request_url
            return response
        except httpx.HTTPStatusError as exc:
            last_error = exc
            status_code = exc.response.status_code
            if status_code not in RETRYABLE_STATUS_CODES:
                raise C1ServiceError(f"C1 returned HTTP {status_code}", status_code) from exc
            _selected_base_url = None
        except httpx.HTTPError as exc:
            last_error = exc
            _selected_base_url = None

    if isinstance(last_error, httpx.HTTPStatusError):
        raise C1ServiceError(f"C1 returned HTTP {last_error.response.status_code}", last_error.response.status_code) from last_error
    if isinstance(last_error, httpx.HTTPError):
        _selected_base_url = None
        raise C1ServiceError(f"C1 unavailable: {last_error}") from last_error
    raise C1ServiceError("C1 unavailable")


def get_status() -> dict[str, Any]:
    global _selected_base_url

    candidates = _candidate_urls()
    if not candidates:
        _selected_base_url = None
        return {
            "baseUrl": None,
            "selectedBaseUrl": None,
            "reachable": False,
            "healthOk": False,
            "identityOk": False,
            "error": "No allowed CampusVision C1 candidate URLs are configured.",
            "candidateUrls": [],
            "candidates": [],
        }
    candidate_statuses = [_status_for_url(base_url) for base_url in candidates]
    for item in candidate_statuses:
        _store_status_cache(item["baseUrl"], item)
    selected = next(
        (item for item in candidate_statuses if _is_healthy_c1_status(item)),
        None,
    )
    _selected_base_url = selected["baseUrl"] if selected else None
    status = dict(selected or {"baseUrl": candidates[0], "reachable": False, "healthOk": False, "identityOk": False})
    status["baseUrl"] = selected["baseUrl"] if selected else candidates[0]
    status["selectedBaseUrl"] = selected["baseUrl"] if selected else None
    status["candidateUrls"] = candidates
    status["candidates"] = candidate_statuses
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
    query_face_index: int | None = None,
) -> dict[str, Any]:
    files = {"files": (filename, content, content_type or "application/octet-stream")}
    data: dict[str, str] = {"top_k": str(top_k), "max_gap_sec": str(max_gap_sec)}
    if min_score is not None:
        data["min_score"] = str(min_score)
    if query_face_index is not None:
        data["query_face_index"] = str(query_face_index)
    raw = _request("POST", "/api/v1/search/person-by-image", files=files, data=data).json()
    return _summarize_person_result(raw)


def detect_query_faces(filename: str, content: bytes, content_type: str | None) -> dict[str, Any]:
    files = {"files": (filename, content, content_type or "application/octet-stream")}
    raw = _request("POST", "/api/v1/search/query-faces", files=files).json()
    return {
        "source": "c1",
        "baseUrl": C1_BASE_URL,
        "engine": raw.get("engine"),
        "faceCount": raw.get("face_count", 0),
        "diagnostics": raw.get("diagnostics") or {},
        "queryFaces": [_query_face_from_item(item) for item in raw.get("query_faces") or []],
    }


def fetch_media(kind: str, face_id: str) -> tuple[bytes, str]:
    if kind not in {"frame", "face"}:
        raise C1ServiceError("Unsupported C1 media kind", 400)
    base_url = _resolve_base_url()
    cache_key = (base_url, kind, face_id)
    if C1_MEDIA_CACHE_TTL > 0:
        with _cache_lock:
            cached = _media_cache.get(cache_key)
            if cached and cached[0] > time.monotonic():
                _media_cache.move_to_end(cache_key)
                return cached[1], cached[2]
            if cached:
                _media_cache.pop(cache_key, None)

    response = _request("GET", f"/api/v1/media/{kind}/{face_id}", primary_url=base_url)
    content = response.content
    media_type = response.headers.get("content-type", "image/jpeg")
    if C1_MEDIA_CACHE_TTL > 0 and content:
        cache_base_url = _selected_base_url or base_url
        cache_key = (cache_base_url, kind, face_id)
        with _cache_lock:
            _media_cache[cache_key] = (_cache_deadline(C1_MEDIA_CACHE_TTL), content, media_type)
            _media_cache.move_to_end(cache_key)
            while len(_media_cache) > max(1, C1_MEDIA_CACHE_MAX_ITEMS):
                _media_cache.popitem(last=False)
    return content, media_type
