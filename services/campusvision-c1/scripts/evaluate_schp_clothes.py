from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch
import torchvision.transforms as transforms


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.storage import db  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.vision import person_analysis  # noqa: E402
from app.vision.body_detector import get_body_detector  # noqa: E402


SCHP_ROOT = ROOT / "data" / "models" / "schp" / "Self-Correction-Human-Parsing"
SCHP_CHECKPOINT = ROOT / "data" / "models" / "schp" / "checkpoints" / "schp" / "exp-schp-201908261155-lip.pth"
if not SCHP_CHECKPOINT.exists():
    SCHP_CHECKPOINT = ROOT / "data" / "models" / "schp" / "checkpoints" / "exp-schp-201908261155-lip.pth"

LIP_INPUT_SIZE = [473, 473]
UPPER_LABELS = {5, 7}
LOWER_LABELS = {9, 12}
DRESS_LABELS = {6, 10}
DEBUG_IMAGE_HEIGHT = 360


def _ensure_schp_import_path() -> None:
    os.environ["PATH"] = f"{sys.prefix}/bin:{os.environ.get('PATH', '')}"
    sys.path.insert(0, str(SCHP_ROOT))


def _load_schp(device: str):
    _ensure_schp_import_path()
    import networks  # noqa: WPS433

    checkpoint = torch.load(str(SCHP_CHECKPOINT), map_location="cpu")
    state_dict = OrderedDict()
    for key, value in checkpoint["state_dict"].items():
        state_dict[key[7:] if key.startswith("module.") else key] = value

    model = networks.init_model("resnet101", num_classes=20, pretrained=None)
    model.load_state_dict(state_dict)
    model.to(device)
    model.eval()
    return model


def _box_to_center_scale(width: int, height: int, input_size: list[int]) -> tuple[np.ndarray, np.ndarray]:
    aspect_ratio = input_size[1] / input_size[0]
    w = float(width - 1)
    h = float(height - 1)
    center = np.asarray([w * 0.5, h * 0.5], dtype=np.float32)
    if w > aspect_ratio * h:
        h = w / aspect_ratio
    elif w < aspect_ratio * h:
        w = h * aspect_ratio
    scale = np.asarray([w, h], dtype=np.float32)
    return center, scale


def _predict_parsing(model, image_bgr: np.ndarray, device: str) -> np.ndarray:
    _ensure_schp_import_path()
    from utils.transforms import get_affine_transform, transform_logits  # noqa: WPS433

    height, width = image_bgr.shape[:2]
    center, scale = _box_to_center_scale(width, height, LIP_INPUT_SIZE)
    trans = get_affine_transform(center, scale, 0, np.asarray(LIP_INPUT_SIZE))
    warped = cv2.warpAffine(
        image_bgr,
        trans,
        (int(LIP_INPUT_SIZE[1]), int(LIP_INPUT_SIZE[0])),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0),
    )
    transform = transforms.Compose(
        [
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.406, 0.456, 0.485], std=[0.225, 0.224, 0.229]),
        ]
    )
    image_tensor = transform(warped).unsqueeze(0).to(device)
    with torch.no_grad():
        output = model(image_tensor)
        upsample = torch.nn.functional.interpolate(
            output[0][-1],
            size=LIP_INPUT_SIZE,
            mode="bilinear",
            align_corners=True,
        )
    logits = upsample[0].permute(1, 2, 0).detach().cpu().numpy()
    logits = transform_logits(logits, center, scale, width, height, input_size=LIP_INPUT_SIZE)
    return np.argmax(logits, axis=2).astype(np.uint8)


def _identified_event_rows() -> list[dict[str, Any]]:
    with db.get_conn() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM events
            WHERE person_id IS NOT NULL
            ORDER BY person_id, camera_id, start_timestamp_sec, event_id
            """
        ).fetchall()
    return [dict(row) for row in rows]


def _event_observation_ids() -> dict[str, list[str]]:
    with db.get_conn() as conn:
        rows = conn.execute(
            """
            SELECT eo.event_id, eo.observation_id
            FROM event_observations eo
            JOIN events e ON e.event_id = eo.event_id
            WHERE e.person_id IS NOT NULL
            ORDER BY eo.event_id, eo.sequence_index
            """
        ).fetchall()
    out: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        out[row["event_id"]].append(row["observation_id"])
    return out


def _face_by_observation_id(observations: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out = {}
    for observation in observations:
        face_record_id = observation.get("face_record_id")
        if not face_record_id:
            continue
        face_record = db.get_face_record(face_record_id)
        if face_record is None:
            continue
        out[observation["observation_id"]] = {"face_id": face_record_id, **face_record["bbox"]}
    return out


def _apply_detector_bboxes(
    observations: list[dict[str, Any]],
    *,
    fallback_estimated: bool,
    print_every: int = 25,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    detector = get_body_detector()
    faces_by_observation_id = _face_by_observation_id(observations)
    observations_by_frame: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for observation in observations:
        observations_by_frame[observation["frame_path"]].append(observation)

    stats = {
        "bbox_source": "detector",
        "detector": detector.name,
        "frames": len(observations_by_frame),
        "observations": len(observations),
        "detections": 0,
        "matched": 0,
        "fallback_estimated": 0,
        "unmatched": 0,
    }
    rewritten: list[dict[str, Any]] = []
    for frame_index, (frame_path, frame_observations) in enumerate(observations_by_frame.items(), start=1):
        frame = cv2.imread(frame_path)
        if frame is None:
            rewritten.extend(dict(observation, person_bbox=None, body_visibility="unknown_body") for observation in frame_observations)
            continue

        bodies = detector.detect_people(frame)
        stats["detections"] += len(bodies)
        known_face_items = [
            (observation, faces_by_observation_id[observation["observation_id"]])
            for observation in frame_observations
            if observation["observation_id"] in faces_by_observation_id
        ]
        known_faces = [face for _, face in known_face_items]
        match_result = person_analysis.match_faces_to_bodies(known_faces, bodies)
        body_by_known_face_index = {
            pair["face_index"]: bodies[pair["body_index"]]
            for pair in match_result["pairs"]
        }
        known_index_by_observation_id = {
            observation["observation_id"]: index for index, (observation, _) in enumerate(known_face_items)
        }

        height, width = frame.shape[:2]
        for observation in frame_observations:
            updated = dict(observation)
            face = faces_by_observation_id.get(observation["observation_id"])
            known_index = known_index_by_observation_id.get(observation["observation_id"])
            body = body_by_known_face_index.get(known_index) if known_index is not None else None
            body_model_version = detector.name
            if body is None and fallback_estimated and face is not None:
                body = person_analysis.estimate_body_bbox_from_face(face, width, height)
                body_model_version = "face_estimated_body_v1"
                stats["fallback_estimated"] += 1

            if body is None:
                updated["person_bbox"] = None
                updated["body_visibility"] = "face_only" if face is not None else "unknown_body"
                updated["person_detection_confidence"] = None
                updated["body_model_version"] = detector.name
                stats["unmatched"] += 1
            else:
                updated["person_bbox"] = body
                updated["body_visibility"] = person_analysis.classify_body_visibility(frame, body, face)
                updated["person_detection_confidence"] = body.get("score")
                updated["body_model_version"] = body_model_version
                stats["matched"] += 1
            rewritten.append(updated)

        if frame_index % print_every == 0:
            print({"detector_frames": frame_index, "total_frames": len(observations_by_frame), **stats}, flush=True)

    return rewritten, stats


def _unknown_mask_color() -> dict[str, Any]:
    return {
        "color": "unknown",
        "confidence": None,
        "visible": False,
        "valid_pixel_ratio": None,
        "mask_pixels": 0,
        "mask_ratio": 0.0,
    }


def _classify_mask_color(crop_bgr: np.ndarray, mask: np.ndarray) -> dict[str, Any]:
    pixels = crop_bgr[mask]
    if pixels.size == 0:
        return _unknown_mask_color()
    pseudo_roi = pixels.reshape(-1, 1, 3)
    result = person_analysis.classify_clothing_color(pseudo_roi)
    return {
        "color": result.color or "unknown",
        "confidence": result.confidence,
        "visible": bool(result.visible),
        "valid_pixel_ratio": result.valid_pixel_ratio,
        "mask_pixels": int(mask.sum()),
        "mask_ratio": round(float(mask.sum() / max(1, mask.size)), 6),
    }


def _bbox_crop(image_bgr: np.ndarray, bbox: dict) -> tuple[np.ndarray | None, tuple[int, int, int, int] | None]:
    height, width = image_bgr.shape[:2]
    box = person_analysis.clamp_bbox(bbox, width, height)
    crop = image_bgr[box["y1"] : box["y2"], box["x1"] : box["x2"]]
    if crop.size == 0:
        return None, None
    return crop, (box["x1"], box["y1"], box["x2"], box["y2"])


def _parse_masks(observation: dict[str, Any], crop_bgr: np.ndarray, pred: np.ndarray, crop_box: tuple[int, int, int, int]) -> dict[str, Any]:
    upper_mask, lower_mask = _part_masks(pred)
    upper = _classify_mask_color(crop_bgr, upper_mask)
    lower = _classify_mask_color(crop_bgr, lower_mask)
    if upper["mask_pixels"] < 250:
        upper.update({"color": "unknown", "confidence": None, "visible": False})
    if lower["mask_pixels"] < 250:
        lower.update({"color": "unknown", "confidence": None, "visible": False})

    return {
        "observation_id": observation["observation_id"],
        "status": "ok",
        "body_model_version": observation.get("body_model_version"),
        "body_visibility": observation.get("body_visibility"),
        "crop_box": crop_box,
        "crop_shape": [int(crop_bgr.shape[0]), int(crop_bgr.shape[1])],
        "upper": upper,
        "lower": lower,
    }


def _part_masks(pred: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    height = pred.shape[0]
    y_indices = np.arange(height)[:, None]
    upper_mask = np.isin(pred, list(UPPER_LABELS)) | (
        np.isin(pred, list(DRESS_LABELS)) & (y_indices < int(height * 0.58))
    )
    lower_mask = np.isin(pred, list(LOWER_LABELS)) | (
        np.isin(pred, list(DRESS_LABELS)) & (y_indices >= int(height * 0.58))
    )
    return upper_mask, lower_mask


def _parse_observation_crop_mode(observation: dict[str, Any], *, model, device: str) -> dict[str, Any]:
    if not observation.get("person_bbox"):
        return {"observation_id": observation["observation_id"], "status": "no_person_bbox", "upper": _unknown_mask_color(), "lower": _unknown_mask_color()}
    image = cv2.imread(observation["frame_path"])
    if image is None:
        return {"observation_id": observation["observation_id"], "status": "frame_not_found", "upper": _unknown_mask_color(), "lower": _unknown_mask_color()}
    crop_bgr, crop_box = _bbox_crop(image, observation["person_bbox"])
    if crop_bgr is None or crop_box is None:
        return {"observation_id": observation["observation_id"], "status": "empty_crop", "upper": _unknown_mask_color(), "lower": _unknown_mask_color()}
    pred = _predict_parsing(model, crop_bgr, device)
    return _parse_masks(observation, crop_bgr, pred, crop_box)


def _parse_observation_frame_mode(
    observation: dict[str, Any],
    *,
    frame_bgr: np.ndarray,
    frame_pred: np.ndarray,
) -> dict[str, Any]:
    if not observation.get("person_bbox"):
        return {"observation_id": observation["observation_id"], "status": "no_person_bbox", "upper": _unknown_mask_color(), "lower": _unknown_mask_color()}
    crop_bgr, crop_box = _bbox_crop(frame_bgr, observation["person_bbox"])
    if crop_bgr is None or crop_box is None:
        return {"observation_id": observation["observation_id"], "status": "empty_crop", "upper": _unknown_mask_color(), "lower": _unknown_mask_color()}
    x1, y1, x2, y2 = crop_box
    pred = frame_pred[y1:y2, x1:x2]
    if pred.size == 0:
        return {"observation_id": observation["observation_id"], "status": "empty_mask_crop", "upper": _unknown_mask_color(), "lower": _unknown_mask_color()}
    return _parse_masks(observation, crop_bgr, pred, crop_box)


def _aggregate_color(items: list[dict[str, Any]], part: str) -> dict[str, Any]:
    weights: Counter[str] = Counter()
    visible_items = []
    for item in items:
        result = item[part]
        if not result.get("visible") or result.get("color") in {None, "", "unknown"}:
            continue
        weight = float(result.get("confidence") or 0.0) * max(1.0, float(result.get("mask_pixels") or 0))
        weights[result["color"]] += weight
        visible_items.append(result)

    if not weights:
        return {
            f"{part}_color": "unknown",
            f"{part}_visible": False,
            f"{part}_confidence": None,
            f"{part}_support": 0,
        }

    ranked = weights.most_common()
    color, weight = ranked[0]
    total = sum(weights.values())
    confidence = float(weight / max(1e-6, total))
    if len(ranked) > 1 and confidence < 0.62:
        return {
            f"{part}_color": "unknown",
            f"{part}_visible": False,
            f"{part}_confidence": round(confidence, 4),
            f"{part}_support": len(visible_items),
        }
    return {
        f"{part}_color": color,
        f"{part}_visible": True,
        f"{part}_confidence": round(confidence, 4),
        f"{part}_support": len(visible_items),
    }


def _known(row: dict[str, Any], part: str) -> bool:
    color = row[f"{part}_color"]
    return bool(row.get(f"{part}_visible")) and color not in (None, "", "unknown")


def _evaluate(rows: list[dict[str, Any]], *, label: str) -> dict[str, Any]:
    report: dict[str, Any] = {"label": label}
    for part in ("upper", "lower"):
        by_person: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            if _known(row, part):
                by_person[row["person_id"]].append(row)

        known_events = sum(len(items) for items in by_person.values())
        eval_people = {person_id: items for person_id, items in by_person.items() if len(items) >= 2}
        eval_events = sum(len(items) for items in eval_people.values())
        mismatch = 0
        inconsistent_people = 0
        confusion: Counter[tuple[str, str]] = Counter()
        camera_stats: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"total": 0, "known": 0, "unknown": 0, "mismatch": 0, "colors": Counter()}
        )

        majority: dict[str, str] = {}
        for person_id, items in eval_people.items():
            counts = Counter(row[f"{part}_color"] for row in items)
            color, count = counts.most_common(1)[0]
            majority[person_id] = color
            mismatch += len(items) - count
            inconsistent_people += 1 if len(counts) > 1 else 0
            for row in items:
                observed = row[f"{part}_color"]
                if observed != color:
                    confusion[(color, observed)] += 1

        for row in rows:
            person_id = row["person_id"]
            if person_id not in majority:
                continue
            stats = camera_stats[row["camera_id"]]
            stats["total"] += 1
            if _known(row, part):
                stats["known"] += 1
                color = row[f"{part}_color"]
                stats["colors"][color] += 1
                if color != majority[person_id]:
                    stats["mismatch"] += 1
            else:
                stats["unknown"] += 1

        report[part] = {
            "known_events_all": known_events,
            "eval_people_ge2_known": len(eval_people),
            "eval_events_ge2_known": eval_events,
            "inconsistent_people": inconsistent_people,
            "person_inconsistency_rate": round(inconsistent_people / max(1, len(eval_people)), 4),
            "event_mismatch_to_person_majority": mismatch,
            "event_mismatch_rate": round(mismatch / max(1, eval_events), 4),
            "top_confusions": [
                {"majority": majority_color, "observed": observed, "count": count}
                for (majority_color, observed), count in confusion.most_common(10)
            ],
            "camera_stats": {
                camera_id: {
                    "total": stats["total"],
                    "known": stats["known"],
                    "unknown_rate": round(stats["unknown"] / max(1, stats["total"]), 4),
                    "mismatch_known": stats["mismatch"],
                    "mismatch_rate_known": round(stats["mismatch"] / max(1, stats["known"]), 4),
                    "colors": dict(stats["colors"].most_common()),
                }
                for camera_id, stats in sorted(camera_stats.items())
            },
        }
    return report


def _majority_colors(rows: list[dict[str, Any]], part: str) -> dict[str, str]:
    by_person: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if _known(row, part):
            by_person[row["person_id"]].append(row)

    out: dict[str, str] = {}
    for person_id, items in by_person.items():
        if len(items) < 2:
            continue
        out[person_id] = Counter(row[f"{part}_color"] for row in items).most_common(1)[0][0]
    return out


def _debug_event_candidates(
    schp_rows: list[dict[str, Any]],
    current_rows_by_event: dict[str, dict[str, Any]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    upper_majority = _majority_colors(schp_rows, "upper")
    lower_majority = _majority_colors(schp_rows, "lower")
    scored: list[tuple[int, dict[str, Any]]] = []
    for row in schp_rows:
        reasons = []
        if (
            row["person_id"] in upper_majority
            and _known(row, "upper")
            and row["upper_color"] != upper_majority[row["person_id"]]
        ):
            reasons.append(f"upper:{upper_majority[row['person_id']]}->{row['upper_color']}")
        if (
            row["person_id"] in lower_majority
            and _known(row, "lower")
            and row["lower_color"] != lower_majority[row["person_id"]]
        ):
            reasons.append(f"lower:{lower_majority[row['person_id']]}->{row['lower_color']}")
        if not reasons:
            continue
        current = current_rows_by_event.get(row["event_id"], {})
        score = len(reasons) * 100 + int(row.get("upper_support") or 0) + int(row.get("lower_support") or 0)
        scored.append(
            (
                score,
                {
                    "event": row,
                    "current": current,
                    "reasons": reasons,
                    "upper_majority": upper_majority.get(row["person_id"]),
                    "lower_majority": lower_majority.get(row["person_id"]),
                },
            )
        )
    scored.sort(key=lambda item: item[0], reverse=True)
    return [item for _, item in scored[:limit]]


def _resize_to_height(image: np.ndarray, height: int) -> np.ndarray:
    scale = height / max(1, image.shape[0])
    width = max(1, int(round(image.shape[1] * scale)))
    return cv2.resize(image, (width, height), interpolation=cv2.INTER_AREA)


def _mask_panel(crop_bgr: np.ndarray, mask: np.ndarray, color: tuple[int, int, int]) -> np.ndarray:
    overlay = crop_bgr.copy()
    overlay[mask] = (np.asarray(overlay[mask], dtype=np.float32) * 0.35 + np.asarray(color) * 0.65).astype(np.uint8)
    return overlay


def _text_panel(lines: list[str], height: int, width: int = 460) -> np.ndarray:
    panel = np.full((height, width, 3), 245, dtype=np.uint8)
    y = 24
    for line in lines:
        cv2.putText(panel, line[:70], (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (20, 20, 20), 1, cv2.LINE_AA)
        y += 21
    return panel


def _parse_for_debug(
    observation: dict[str, Any],
    *,
    model,
    device: str,
    parse_mode: str,
) -> tuple[np.ndarray | None, np.ndarray | None, tuple[int, int, int, int] | None]:
    frame = cv2.imread(observation["frame_path"])
    if frame is None or not observation.get("person_bbox"):
        return None, None, None
    crop_bgr, crop_box = _bbox_crop(frame, observation["person_bbox"])
    if crop_bgr is None or crop_box is None:
        return None, None, None
    if parse_mode == "crop":
        return crop_bgr, _predict_parsing(model, crop_bgr, device), crop_box

    frame_pred = _predict_parsing(model, frame, device)
    x1, y1, x2, y2 = crop_box
    return crop_bgr, frame_pred[y1:y2, x1:x2], crop_box


def _write_debug_images(
    candidates: list[dict[str, Any]],
    event_observation_ids: dict[str, list[str]],
    parsed_by_observation: dict[str, dict[str, Any]],
    observations_by_id: dict[str, dict[str, Any]],
    *,
    model,
    device: str,
    parse_mode: str,
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    for index, candidate in enumerate(candidates, start=1):
        event = candidate["event"]
        observation_ids = event_observation_ids.get(event["event_id"], [])
        observation_id = None
        for oid in observation_ids:
            parsed = parsed_by_observation.get(oid)
            if parsed and parsed.get("status") == "ok":
                observation_id = oid
                break
        if observation_id is None:
            continue
        observation = observations_by_id.get(observation_id)
        if observation is None:
            continue
        crop_bgr, pred, crop_box = _parse_for_debug(
            observation,
            model=model,
            device=device,
            parse_mode=parse_mode,
        )
        if crop_bgr is None or pred is None or crop_box is None:
            continue
        upper_mask, lower_mask = _part_masks(pred)
        upper = _classify_mask_color(crop_bgr, upper_mask)
        lower = _classify_mask_color(crop_bgr, lower_mask)

        original = _resize_to_height(crop_bgr, DEBUG_IMAGE_HEIGHT)
        upper_panel = _resize_to_height(_mask_panel(crop_bgr, upper_mask, (40, 190, 40)), DEBUG_IMAGE_HEIGHT)
        lower_panel = _resize_to_height(_mask_panel(crop_bgr, lower_mask, (190, 40, 190)), DEBUG_IMAGE_HEIGHT)
        text = _text_panel(
            [
                f"#{index} {parse_mode} SCHP-LIP",
                f"person {event['person_id'][-8:]}",
                f"event {event['event_id'][-8:]}",
                f"camera {event['camera_id']}",
                f"time {event.get('start_timestamp_sec')} - {event.get('end_timestamp_sec')}",
                f"reason {','.join(candidate['reasons'])}",
                f"current upper {candidate['current'].get('upper_color')} visible={candidate['current'].get('upper_visible')}",
                f"schp upper {event.get('upper_color')} majority={candidate.get('upper_majority')}",
                f"mask upper {upper.get('color')} conf={upper.get('confidence')} ratio={upper.get('mask_ratio')}",
                f"current lower {candidate['current'].get('lower_color')} visible={candidate['current'].get('lower_visible')}",
                f"schp lower {event.get('lower_color')} majority={candidate.get('lower_majority')}",
                f"mask lower {lower.get('color')} conf={lower.get('confidence')} ratio={lower.get('mask_ratio')}",
                f"visibility {observation.get('body_visibility')} model={observation.get('body_model_version')}",
                f"crop {crop_box}",
            ],
            DEBUG_IMAGE_HEIGHT,
        )
        canvas = np.concatenate([original, upper_panel, lower_panel, text], axis=1)
        filename = f"{index:02d}_{event['person_id'][-8:]}_{event['camera_id']}_{event['event_id'][-8:]}.jpg"
        out_path = output_dir / filename
        cv2.imwrite(str(out_path), canvas)
        manifest.append(
            {
                "image": str(out_path),
                "event": event,
                "observation_id": observation_id,
                "crop_box": crop_box,
                "debug_upper": upper,
                "debug_lower": lower,
                "reasons": candidate["reasons"],
            }
        )
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate SCHP-LIP parsing on current C1 events.")
    parser.add_argument("--limit-observations", type=int, default=None)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--parse-mode", choices=["crop", "frame"], default="crop")
    parser.add_argument("--bbox-source", choices=["db", "detector"], default="db")
    parser.add_argument("--body-backend", default=None)
    parser.add_argument("--detector-fallback-estimated", action="store_true")
    parser.add_argument("--output", default=str(ROOT / "data" / "evals" / "schp_lip_eval.json"))
    parser.add_argument("--debug-samples", type=int, default=0)
    parser.add_argument("--debug-dir", default=str(ROOT / "data" / "evals" / "schp_debug"))
    args = parser.parse_args()

    if not SCHP_ROOT.exists():
        raise SystemExit(f"SCHP source not found: {SCHP_ROOT}")
    if not SCHP_CHECKPOINT.exists():
        raise SystemExit(f"SCHP checkpoint not found: {SCHP_CHECKPOINT}")

    device = args.device
    if device == "cuda" and not torch.cuda.is_available():
        device = "cpu"
    if args.body_backend:
        settings.body_detection_backend = args.body_backend.strip().lower()
        get_body_detector.cache_clear()
    print(
        {
            "device": device,
            "cuda_available": torch.cuda.is_available(),
            "parse_mode": args.parse_mode,
            "bbox_source": args.bbox_source,
            "body_backend": settings.body_detection_backend,
        },
        flush=True,
    )
    model = _load_schp(device)

    events = _identified_event_rows()
    event_observation_ids = _event_observation_ids()
    observation_ids = sorted({oid for ids in event_observation_ids.values() for oid in ids})
    if args.limit_observations:
        observation_ids = observation_ids[: args.limit_observations]
    observations = [obs for oid in observation_ids if (obs := db.get_person_observation(oid)) is not None]
    bbox_stats: dict[str, Any] = {"bbox_source": "db"}
    if args.bbox_source == "detector":
        observations, bbox_stats = _apply_detector_bboxes(
            observations,
            fallback_estimated=args.detector_fallback_estimated,
        )
    observations_by_id = {observation["observation_id"]: observation for observation in observations}

    parsed_by_observation: dict[str, dict[str, Any]] = {}
    if args.parse_mode == "crop":
        for index, observation in enumerate(observations, start=1):
            parsed_by_observation[observation["observation_id"]] = _parse_observation_crop_mode(
                observation,
                model=model,
                device=device,
            )
            if index % 25 == 0:
                print({"parsed_observations": index, "total": len(observations)}, flush=True)
    else:
        observations_by_frame: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for observation in observations:
            observations_by_frame[observation["frame_path"]].append(observation)
        parsed_count = 0
        for frame_index, (frame_path, frame_observations) in enumerate(observations_by_frame.items(), start=1):
            frame_bgr = cv2.imread(frame_path)
            if frame_bgr is None:
                continue
            frame_pred = _predict_parsing(model, frame_bgr, device)
            for observation in frame_observations:
                parsed_by_observation[observation["observation_id"]] = _parse_observation_frame_mode(
                    observation,
                    frame_bgr=frame_bgr,
                    frame_pred=frame_pred,
                )
                parsed_count += 1
            if frame_index % 25 == 0:
                print(
                    {
                        "parsed_frames": frame_index,
                        "total_frames": len(observations_by_frame),
                        "parsed_observations": parsed_count,
                    },
                    flush=True,
                )

    schp_rows = []
    for event in events:
        parsed_items = [
            parsed_by_observation[observation_id]
            for observation_id in event_observation_ids.get(event["event_id"], [])
            if observation_id in parsed_by_observation
        ]
        schp_rows.append(
            {
                "event_id": event["event_id"],
                "person_id": event["person_id"],
                "camera_id": event["camera_id"],
                "video_id": event.get("video_id"),
                **_aggregate_color(parsed_items, "upper"),
                **_aggregate_color(parsed_items, "lower"),
            }
        )

    current_report = _evaluate(events, label="current_db")
    schp_report = _evaluate(schp_rows, label="schp_lip")
    if args.debug_samples > 0:
            _write_debug_images(
                _debug_event_candidates(
                    schp_rows,
                    {event["event_id"]: event for event in events},
                    limit=args.debug_samples,
                ),
                event_observation_ids,
                parsed_by_observation,
                observations_by_id,
                model=model,
                device=device,
                parse_mode=args.parse_mode,
            output_dir=Path(args.debug_dir) / args.parse_mode,
        )
    output = {
        "model": "schp_lip",
        "checkpoint": str(SCHP_CHECKPOINT),
        "parse_mode": args.parse_mode,
        "bbox_stats": bbox_stats,
        "events": len(events),
        "observations_parsed": len(parsed_by_observation),
        "current_report": current_report,
        "schp_report": schp_report,
        "schp_events": schp_rows,
        "parsed_observations": parsed_by_observation,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"current_report": current_report, "schp_report": schp_report}, ensure_ascii=False, indent=2))
    print({"output": str(output_path)})


if __name__ == "__main__":
    main()
