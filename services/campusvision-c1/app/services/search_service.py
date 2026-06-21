from __future__ import annotations

import uuid
import warnings
from dataclasses import dataclass
from hashlib import sha1
from pathlib import Path
from typing import BinaryIO

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError
from PIL.Image import DecompressionBombError, DecompressionBombWarning

from app.core.config import settings
from app.services.upload_limits import UploadTooLarge, copy_upload_with_limit
from app.storage import db
from app.vision.face_engine import default_similarity_threshold, get_face_engine
from app.vision.vector_math import cosine_similarity

MAX_QUERY_IMAGE_PIXELS = 16_000_000
MAX_QUERY_IMAGE_DIMENSION = 8192
Image.MAX_IMAGE_PIXELS = MAX_QUERY_IMAGE_PIXELS


class QueryImageTooLarge(ValueError):
    pass


@dataclass(frozen=True)
class QueryImageVariant:
    label: str
    image: np.ndarray
    display_width: int
    display_height: int
    scale: float = 1.0
    pad_x: int = 0
    pad_y: int = 0

    def to_display_box(self, box: dict) -> dict:
        return {
            "x1": (float(box["x1"]) - self.pad_x) / self.scale,
            "y1": (float(box["y1"]) - self.pad_y) / self.scale,
            "x2": (float(box["x2"]) - self.pad_x) / self.scale,
            "y2": (float(box["y2"]) - self.pad_y) / self.scale,
            "score": float(box.get("score") or 0),
        }


def save_query_image(fileobj: BinaryIO, filename: str, search_id: str) -> str:
    settings.ensure_dirs()

    suffix = Path(filename).suffix.lower() or ".jpg"
    dest_dir = settings.query_uploads_dir / search_id
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest = dest_dir / f"{uuid.uuid4().hex}{suffix}"
    try:
        copy_upload_with_limit(fileobj, dest, settings.max_query_image_upload_bytes, label="Query image upload")
    except UploadTooLarge as exc:
        raise QueryImageTooLarge(str(exc)) from exc
    return str(dest)


def _bbox_payload(box: dict, image_width: int, image_height: int) -> dict:
    x1 = max(0, min(image_width - 1, int(box["x1"])))
    y1 = max(0, min(image_height - 1, int(box["y1"])))
    x2 = max(x1 + 1, min(image_width, int(box["x2"])))
    y2 = max(y1 + 1, min(image_height, int(box["y2"])))
    width = x2 - x1
    height = y2 - y1
    return {
        "x1": x1,
        "y1": y1,
        "x2": x2,
        "y2": y2,
        "width": width,
        "height": height,
        "leftPct": round(x1 / image_width * 100, 4) if image_width else 0,
        "topPct": round(y1 / image_height * 100, 4) if image_height else 0,
        "widthPct": round(width / image_width * 100, 4) if image_width else 0,
        "heightPct": round(height / image_height * 100, 4) if image_height else 0,
        "score": float(box.get("score") or 0),
    }


def _pil_to_bgr(image: Image.Image) -> np.ndarray:
    if image.mode in {"RGBA", "LA"}:
        background = Image.new("RGBA", image.size, (255, 255, 255, 255))
        background.alpha_composite(image.convert("RGBA"))
        image = background.convert("RGB")
    else:
        image = image.convert("RGB")
    return cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)


def _validate_query_image_size(width: int, height: int) -> None:
    if (
        width <= 0
        or height <= 0
        or width > MAX_QUERY_IMAGE_DIMENSION
        or height > MAX_QUERY_IMAGE_DIMENSION
        or width * height > MAX_QUERY_IMAGE_PIXELS
    ):
        raise QueryImageTooLarge("Query image dimensions exceed the allowed limit.")


def _load_query_image(path: str) -> Image.Image | None:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", DecompressionBombWarning)
            with Image.open(path) as image:
                width, height = image.size
                _validate_query_image_size(width, height)
                return ImageOps.exif_transpose(image).copy()
    except QueryImageTooLarge:
        raise
    except (DecompressionBombError, DecompressionBombWarning) as exc:
        raise QueryImageTooLarge("Query image dimensions exceed the allowed limit.") from exc
    except (OSError, UnidentifiedImageError):
        return None


def _query_image_variants(path: str) -> tuple[list[QueryImageVariant], dict]:
    try:
        image = _load_query_image(path)
    except QueryImageTooLarge as exc:
        return [], {"path": Path(path).name, "loaded": False, "rejected": True, "reason": str(exc), "attempts": []}
    if image is None:
        return [], {"path": Path(path).name, "loaded": False, "attempts": []}

    width, height = image.size
    diagnostics = {
        "path": Path(path).name,
        "loaded": True,
        "width": width,
        "height": height,
        "attempts": [],
    }

    variants: list[QueryImageVariant] = [
        QueryImageVariant(
            label="normalized",
            image=_pil_to_bgr(image),
            display_width=width,
            display_height=height,
        )
    ]

    shortest_edge = max(1, min(width, height))
    scale = max(1.0, min(2.0, 640 / shortest_edge))
    scaled_width = int(round(width * scale))
    scaled_height = int(round(height * scale))
    scaled = image.resize((scaled_width, scaled_height), Image.Resampling.LANCZOS) if scale > 1.01 else image

    for ratio in (0.16, 0.28):
        pad_x = max(16, int(round(scaled_width * ratio)))
        pad_y = max(16, int(round(scaled_height * ratio)))
        padded_width = scaled_width + pad_x * 2
        padded_height = scaled_height + pad_y * 2
        try:
            _validate_query_image_size(padded_width, padded_height)
        except QueryImageTooLarge as exc:
            diagnostics["attempts"].append(
                {
                    "label": f"padded-{int(ratio * 100)}",
                    "width": padded_width,
                    "height": padded_height,
                    "skipped": True,
                    "reason": str(exc),
                }
            )
            continue
        padded = ImageOps.expand(scaled, border=(pad_x, pad_y, pad_x, pad_y), fill=(238, 244, 255))
        variants.append(
            QueryImageVariant(
                label=f"padded-{int(ratio * 100)}",
                image=_pil_to_bgr(padded),
                display_width=width,
                display_height=height,
                scale=scale,
                pad_x=pad_x,
                pad_y=pad_y,
            )
        )

    return variants, diagnostics


def _query_faces_from_images(paths: list[str], include_embeddings: bool = False) -> dict:
    engine = get_face_engine()
    faces: list[dict] = []
    diagnostics = {"images": []}

    for image_index, path in enumerate(paths):
        variants, image_diagnostics = _query_image_variants(path)
        diagnostics["images"].append(image_diagnostics)
        if not variants:
            continue

        boxes: list[dict] = []
        selected_variant: QueryImageVariant | None = None
        for variant in variants:
            variant_boxes = engine.detect_faces(variant.image)
            image_diagnostics["attempts"].append(
                {
                    "label": variant.label,
                    "width": int(variant.image.shape[1]),
                    "height": int(variant.image.shape[0]),
                    "face_count": len(variant_boxes),
                }
            )
            if variant_boxes:
                selected_variant = variant
                boxes = variant_boxes
                image_diagnostics["selected_attempt"] = variant.label
                break

        if not boxes:
            continue

        assert selected_variant is not None
        embeddings = engine.embed_faces(selected_variant.image, boxes) if include_embeddings else []
        for face_index, box in enumerate(boxes):
            display_box = selected_variant.to_display_box(box)
            face = {
                "index": len(faces),
                "image_index": image_index,
                "face_index": face_index,
                "bbox": _bbox_payload(display_box, selected_variant.display_width, selected_variant.display_height),
                "score": round(float(box.get("score") or 0), 6),
                "image_width": selected_variant.display_width,
                "image_height": selected_variant.display_height,
                "detection_attempt": selected_variant.label,
            }
            if include_embeddings and face_index < len(embeddings):
                face["embedding"] = embeddings[face_index]
            faces.append(face)

    return {"faces": faces, "diagnostics": diagnostics}


def detect_query_faces(paths: list[str]) -> dict:
    result = _query_faces_from_images(paths, include_embeddings=False)
    faces = result["faces"]
    return {
        "engine": get_face_engine().name,
        "query_faces": faces,
        "face_count": len(faces),
        "diagnostics": result["diagnostics"],
    }


def load_embeddings_from_images(paths: list[str], query_face_index: int | None = None) -> list[list[float]]:
    faces = _query_faces_from_images(paths, include_embeddings=True)["faces"]
    embeddings: list[list[float]] = []
    for face in faces:
        if query_face_index is not None and int(face["index"]) != int(query_face_index):
            continue
        embedding = face.get("embedding")
        if embedding is not None:
            embeddings.append(embedding)

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
        "bbox": record.get("bbox"),
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
