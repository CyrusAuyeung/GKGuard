from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import settings  # noqa: E402
from app.services import outfit_service  # noqa: E402
from app.storage import db  # noqa: E402


DEFAULT_LABEL_PATH = settings.data_dir / "evals" / "manual_outfit_labels" / "outfit_labels.json"
DEFAULT_EXPORT_ROOT = settings.data_dir / "evals" / "manual_outfit_labels" / "remap_exports"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_component(value: object) -> str:
    raw = str(value or "item")
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in raw).strip("._")
    return safe[:96] or "item"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _sha256_file(path: Path, cache: dict[str, str]) -> str | None:
    key = str(path)
    if key in cache:
        return cache[key]
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    value = digest.hexdigest()
    cache[key] = value
    return value


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _image_dhash(image_bgr: np.ndarray | None) -> str | None:
    if image_bgr is None or image_bgr.size == 0:
        return None
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, (9, 8), interpolation=cv2.INTER_AREA)
    diff = resized[:, 1:] > resized[:, :-1]
    value = 0
    for bit in diff.flatten():
        value = (value << 1) | int(bool(bit))
    return f"{value:016x}"


def _image_file_dhash(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    image = cv2.imread(str(path))
    return _image_dhash(image)


def _crop_bbox(image: np.ndarray | None, bbox: dict[str, Any] | None, *, padding_ratio: float = 0.0) -> np.ndarray | None:
    if image is None or not bbox:
        return None
    height, width = image.shape[:2]
    x1 = float(bbox.get("x1", 0))
    y1 = float(bbox.get("y1", 0))
    x2 = float(bbox.get("x2", 0))
    y2 = float(bbox.get("y2", 0))
    if x2 <= x1 or y2 <= y1:
        return None
    pad_x = (x2 - x1) * padding_ratio
    pad_y = (y2 - y1) * padding_ratio
    left = max(0, int(round(x1 - pad_x)))
    top = max(0, int(round(y1 - pad_y)))
    right = min(width, int(round(x2 + pad_x)))
    bottom = min(height, int(round(y2 + pad_y)))
    if right <= left or bottom <= top:
        return None
    return image[top:bottom, left:right]


def _jpeg_hash_and_dhash(image: np.ndarray | None) -> dict[str, Any]:
    if image is None or image.size == 0:
        return {}
    ok, encoded = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
    if not ok:
        return {}
    return {
        "jpeg_sha256": _sha256_bytes(encoded.tobytes()),
        "dhash_8x8": _image_dhash(image),
        "shape": [int(image.shape[1]), int(image.shape[0])],
    }


def _resolve_data_path(value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    if path.is_absolute():
        return path
    return settings.data_dir / path


def _path_info(path: Path | None, *, hash_cache: dict[str, str], include_sha: bool = True) -> dict[str, Any]:
    if path is None:
        return {}
    out: dict[str, Any] = {"path": str(path)}
    if not path.exists():
        out["exists"] = False
        return out
    stat = path.stat()
    out.update(
        {
            "exists": True,
            "size_bytes": int(stat.st_size),
            "mtime_ns": int(stat.st_mtime_ns),
            "name": path.name,
        }
    )
    if include_sha:
        out["sha256"] = _sha256_file(path, hash_cache)
    return out


def _copy_artifact(
    *,
    source: Path | None,
    export_dir: Path,
    dest_dir: Path,
    name_prefix: str,
    hash_cache: dict[str, str],
) -> dict[str, Any]:
    if source is None or not source.exists() or not source.is_file():
        return {"available": False}
    dest_dir.mkdir(parents=True, exist_ok=True)
    suffix = source.suffix.lower() or ".jpg"
    dest = dest_dir / f"{name_prefix}{suffix}"
    shutil.copy2(source, dest)
    return {
        "available": True,
        "source_path": str(source),
        "export_path": str(dest),
        "export_relative_path": str(dest.relative_to(export_dir)),
        "sha256": _sha256_file(dest, hash_cache),
        "dhash_8x8": _image_file_dhash(dest),
        "size_bytes": int(dest.stat().st_size),
    }


def _video_anchor(video_id: str | None, *, hash_cache: dict[str, str]) -> dict[str, Any]:
    if not video_id:
        return {}
    video = db.get_video(video_id)
    if not video:
        return {"video_id": video_id, "video_missing": True}
    path = Path(str(video.get("path") or ""))
    return {
        "video_id": video.get("video_id"),
        "filename": video.get("filename"),
        "camera_id": video.get("camera_id"),
        "recorded_at": video.get("recorded_at"),
        "frame_interval_sec": video.get("frame_interval_sec"),
        "path_info": _path_info(path if str(path) else None, hash_cache=hash_cache, include_sha=False),
    }


def _event_anchor(event: dict[str, Any], *, hash_cache: dict[str, str]) -> dict[str, Any]:
    event_id = str(event.get("event_id") or "")
    observation_id = str(event.get("representative_observation_id") or "")
    face_id = str(event.get("representative_face_id") or "")
    observation = db.get_person_observation(observation_id) if observation_id else None
    face = db.get_face_record(face_id) if face_id else None
    frame_path = _resolve_data_path(
        (observation or {}).get("frame_path") or event.get("representative_frame_path") or (face or {}).get("frame_path")
    )
    frame_image = cv2.imread(str(frame_path)) if frame_path and frame_path.exists() else None
    body_bbox = (observation or {}).get("person_bbox")
    face_bbox = (face or {}).get("bbox")
    body_crop = _crop_bbox(frame_image, body_bbox, padding_ratio=0.04)
    face_crop = _crop_bbox(frame_image, face_bbox, padding_ratio=0.0)

    return {
        "event_id": event_id,
        "observation_id": observation_id,
        "face_id": face_id,
        "person_id": event.get("person_id"),
        "camera_id": event.get("camera_id"),
        "video_id": event.get("video_id"),
        "live_source_id": event.get("live_source_id"),
        "track_id": event.get("track_id"),
        "appearance_session_id": event.get("appearance_session_id"),
        "start_time": event.get("start_time"),
        "end_time": event.get("end_time"),
        "start_timestamp_sec": event.get("start_timestamp_sec"),
        "end_timestamp_sec": event.get("end_timestamp_sec"),
        "event_status": event.get("event_status"),
        "observation_count": event.get("observation_count"),
        "face_count": event.get("face_count"),
        "video_anchor": _video_anchor(str(event.get("video_id") or ""), hash_cache=hash_cache),
        "observation_anchor": {
            "observation_id": (observation or {}).get("observation_id"),
            "camera_id": (observation or {}).get("camera_id"),
            "video_id": (observation or {}).get("video_id"),
            "frame_index": (observation or {}).get("frame_index"),
            "video_timestamp_sec": (observation or {}).get("video_timestamp_sec"),
            "captured_at": (observation or {}).get("captured_at"),
            "track_id": (observation or {}).get("track_id"),
            "body_visibility": (observation or {}).get("body_visibility"),
            "person_bbox": body_bbox,
            "person_detection_confidence": (observation or {}).get("person_detection_confidence"),
        },
        "face_anchor": {
            "face_id": (face or {}).get("face_id"),
            "video_timestamp_sec": (face or {}).get("video_timestamp_sec"),
            "captured_at": (face or {}).get("captured_at"),
            "bbox": face_bbox,
        },
        "frame_file": _path_info(frame_path, hash_cache=hash_cache),
        "frame_dhash_8x8": _image_dhash(frame_image),
        "body_crop_fingerprint": _jpeg_hash_and_dhash(body_crop),
        "face_crop_fingerprint": _jpeg_hash_and_dhash(face_crop),
        "model_at_export": {
            "upper_color": event.get("upper_color") or "unknown",
            "upper_color_confidence": event.get("upper_color_confidence"),
            "normalized_upper_color": event.get("normalized_upper_color") or event.get("upper_color") or "unknown",
            "normalized_upper_color_confidence": event.get("normalized_upper_color_confidence"),
            "upper_visible": event.get("upper_visible"),
            "raw_upper_color": event.get("raw_upper_color"),
            "raw_upper_color_confidence": event.get("raw_upper_color_confidence"),
            "clothing_normalization_version": event.get("clothing_normalization_version"),
        },
    }


def _snapshot_artifacts(
    label: dict[str, Any],
    *,
    export_dir: Path,
    outfit_id: str,
    hash_cache: dict[str, str],
    copy_artifacts: bool,
) -> list[dict[str, Any]]:
    artifacts = []
    for index, snapshot in enumerate(label.get("sample_snapshots") or [], start=1):
        if not isinstance(snapshot, dict):
            continue
        sample_key = str(snapshot.get("sample_key") or snapshot.get("observation_id") or snapshot.get("event_id") or index)
        dest_dir = export_dir / "images" / _safe_component(outfit_id) / f"{index:03d}_{_safe_component(sample_key)}"
        item = {
            "sample_key": sample_key,
            "event_id": snapshot.get("event_id"),
            "observation_id": snapshot.get("observation_id"),
            "face_id": snapshot.get("face_id"),
            "body_bbox": snapshot.get("body_bbox"),
            "frame_shape": snapshot.get("frame_shape"),
            "source_frame_path": snapshot.get("source_frame_path"),
            "snapshot_errors": snapshot.get("snapshot_errors") or [],
        }
        for kind, field in [
            ("frame", "snapshot_frame_path"),
            ("body", "snapshot_body_path"),
            ("face", "snapshot_face_path"),
        ]:
            source = _resolve_data_path(snapshot.get(field))
            if copy_artifacts:
                item[f"{kind}_artifact"] = _copy_artifact(
                    source=source,
                    export_dir=export_dir,
                    dest_dir=dest_dir,
                    name_prefix=kind,
                    hash_cache=hash_cache,
                )
            else:
                item[f"{kind}_artifact"] = _path_info(source, hash_cache=hash_cache)
        artifacts.append(item)
    return artifacts


def _manual_outfit_labels(labels: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out = {}
    for key, value in labels.items():
        if not isinstance(value, dict):
            continue
        outfit_id = str(value.get("outfit_id") or key)
        if outfit_id.startswith("outfit_") and value.get("source") == "manual_outfit_review":
            out[outfit_id] = value
    return out


def export_remappable_eval(
    *,
    label_path: Path,
    export_root: Path,
    distance_threshold: float,
    copy_artifacts: bool,
) -> dict[str, Any]:
    db.init_db()
    label_data = _load_json(label_path)
    labels = _manual_outfit_labels(label_data.get("labels") or {})
    groups = {
        group["outfit_id"]: group
        for group in outfit_service.build_outfit_groups(distance_threshold=distance_threshold)
    }

    export_id = datetime.now().strftime("remappable_outfit_eval_%Y%m%d_%H%M%S")
    export_dir = export_root / export_id
    hash_cache: dict[str, str] = {}
    current_outfits = []
    stale_labels = []

    for outfit_id in sorted(labels):
        label = labels[outfit_id]
        group = groups.get(outfit_id)
        manual_color = str(label.get("upper_color") or "unknown")
        base = {
            "outfit_id": outfit_id,
            "legacy_person_id": label.get("person_id"),
            "manual_upper_color": manual_color,
            "manual_upper_visible": bool(label.get("upper_visible")),
            "review_status": label.get("review_status") or "unreviewed",
            "saved_at": label.get("saved_at"),
            "note": label.get("note") or "",
            "manual_split_required": bool(label.get("manual_split_required")),
            "manual_split_group_count": int(label.get("manual_split_group_count") or 0),
            "source_session_ids": label.get("source_session_ids") or [],
            "camera_ids": label.get("camera_ids") or [],
            "sample_event_ids": label.get("sample_event_ids") or [],
            "sample_observation_ids": label.get("sample_observation_ids") or [],
            "sample_snapshot_count": int(label.get("sample_snapshot_count") or 0),
            "label_distance_threshold": label.get("distance_threshold"),
            "label_grouping_version": label.get("grouping_version"),
            "model_at_label_save": {
                "upper_color": label.get("model_upper_color") or "unknown",
                "upper_color_confidence": label.get("model_upper_color_confidence"),
                "upper_color_counts": label.get("model_upper_color_counts") or {},
            },
        }
        if not group:
            stale_labels.append(base)
            continue

        event_anchors = [
            _event_anchor(event, hash_cache=hash_cache)
            for event in group.get("events") or []
        ]
        video_filenames = sorted(
            {
                str(((anchor.get("video_anchor") or {}).get("filename")) or "")
                for anchor in event_anchors
                if ((anchor.get("video_anchor") or {}).get("filename"))
            }
        )
        model_color = group.get("model_upper_color") or "unknown"
        current_outfits.append(
            {
                **base,
                "remap_key": {
                    "camera_ids": group.get("camera_ids") or [],
                    "video_filenames": video_filenames,
                    "start_timestamp_sec": group.get("start_timestamp_sec"),
                    "end_timestamp_sec": group.get("end_timestamp_sec"),
                    "start_time": group.get("start_time"),
                    "end_time": group.get("end_time"),
                },
                "current_group": {
                    "person_id": group.get("person_id"),
                    "group_index": group.get("group_index"),
                    "event_count": int(group.get("event_count") or 0),
                    "session_count": int(group.get("session_count") or 0),
                    "source_session_ids": group.get("source_session_ids") or [],
                    "source_segment_ids": group.get("source_segment_ids") or [],
                    "camera_ids": group.get("camera_ids") or [],
                    "start_time": group.get("start_time"),
                    "end_time": group.get("end_time"),
                    "start_timestamp_sec": group.get("start_timestamp_sec"),
                    "end_timestamp_sec": group.get("end_timestamp_sec"),
                    "grouping_version": group.get("grouping_version"),
                },
                "model_at_export": {
                    "upper_color": model_color,
                    "upper_color_confidence": group.get("model_upper_color_confidence"),
                    "upper_color_counts": group.get("model_upper_color_counts") or {},
                    "matches_manual": model_color == manual_color,
                },
                "event_anchors": event_anchors,
                "sample_artifacts": _snapshot_artifacts(
                    label,
                    export_dir=export_dir,
                    outfit_id=outfit_id,
                    hash_cache=hash_cache,
                    copy_artifacts=copy_artifacts,
                ),
            }
        )

    correct = sum(1 for item in current_outfits if item["model_at_export"]["matches_manual"])
    visible_items = [item for item in current_outfits if item["manual_upper_visible"]]
    visible_correct = sum(1 for item in visible_items if item["model_at_export"]["matches_manual"])
    report = {
        "schema_version": "remappable_outfit_eval_v1",
        "generated_at": _now(),
        "export_id": export_id,
        "export_dir": str(export_dir),
        "source_label_path": str(label_path),
        "source_label_updated_at": label_data.get("updated_at"),
        "distance_threshold": distance_threshold,
        "copy_artifacts": copy_artifacts,
        "policy": {
            "manual_labels_usage": "eval_only",
            "training_allowed": False,
            "purpose": "Remap manual outfit upper-color labels after a full database rerun.",
        },
        "remap_guidance": [
            "Primary exact anchors: camera_id + video filename + video_timestamp_sec/start_timestamp_sec.",
            "Secondary visual anchors: exported body/frame/face dhash_8x8 and sha256 fingerprints.",
            "Legacy IDs are trace fields only; do not require person_id/event_id/outfit_id to remain stable.",
        ],
        "summary": {
            "current_group_count": len(groups),
            "exported_current_outfit_count": len(current_outfits),
            "stale_label_count": len(stale_labels),
            "remaining_unlabeled_current_group_count": max(0, len(groups) - len(current_outfits)),
            "manual_upper_color_counts": dict(
                Counter(item["manual_upper_color"] for item in current_outfits).most_common()
            ),
            "review_status_counts": dict(Counter(item["review_status"] for item in current_outfits).most_common()),
            "model_accuracy_at_export": round(correct / len(current_outfits), 4) if current_outfits else None,
            "model_visible_accuracy_at_export": round(visible_correct / len(visible_items), 4) if visible_items else None,
        },
        "outfits": current_outfits,
        "stale_labels": stale_labels,
    }

    report_path = export_dir / "remappable_outfit_eval.json"
    latest_path = export_root / "remappable_outfit_eval_latest.json"
    _write_json(report_path, report)
    _write_json(latest_path, report)
    return {
        "report_path": str(report_path),
        "latest_path": str(latest_path),
        "summary": report["summary"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Export remappable eval-only outfit labels for future full reruns.")
    parser.add_argument("--labels", type=Path, default=DEFAULT_LABEL_PATH)
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--distance-threshold", type=float, default=0.42)
    parser.add_argument("--no-copy-artifacts", action="store_true")
    args = parser.parse_args()

    result = export_remappable_eval(
        label_path=args.labels,
        export_root=args.export_root,
        distance_threshold=max(0.1, min(float(args.distance_threshold), 0.9)),
        copy_artifacts=not args.no_copy_artifacts,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
