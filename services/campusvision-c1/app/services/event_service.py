from __future__ import annotations

from collections import Counter
from datetime import datetime
from hashlib import sha1

from app.core.config import settings
from app.storage import db
from app.vision.person_analysis import bbox_area
from app.vision.upper_color_postprocess import choose_upper_color_from_probs


_UPPER_PROB_COLORS = tuple(
    color
    for color in settings.clothing_color_labels
    if color not in {"unknown", "other"}
)


def _core_clothing_parts() -> tuple[str, ...]:
    return ("upper", "lower") if settings.enable_lower_clothing_core else ("upper",)


def _unknown_part() -> dict:
    return {
        "color": "unknown",
        "confidence": None,
        "support": 0,
        "visible": False,
        "counts": {},
        "probabilities": None,
    }


def _disabled_lower_reason(event: dict) -> dict:
    raw = _raw_part(event, "lower")
    return {
        "raw_color": raw["color"],
        "raw_confidence": raw["confidence"],
        "raw_observed": raw["observed"],
        "profile_color": None,
        "profile_confidence": None,
        "profile_support": 0,
        "action": "ignore_lower_clothing_core_disabled",
        "normalized_color": "unknown",
        "normalized_confidence": None,
    }


def _parse_iso_seconds(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _time_key(observation: dict) -> tuple[float, float]:
    captured = _parse_iso_seconds(observation.get("captured_at"))
    return (
        captured if captured is not None else float("inf"),
        float(observation.get("video_timestamp_sec") or 0.0),
    )


def _time_gap(left: dict, right: dict) -> float | None:
    left_captured = _parse_iso_seconds(left.get("captured_at"))
    right_captured = _parse_iso_seconds(right.get("captured_at"))
    if left_captured is not None and right_captured is not None:
        return right_captured - left_captured
    if left.get("video_id") == right.get("video_id"):
        return float(right.get("video_timestamp_sec") or 0.0) - float(
            left.get("video_timestamp_sec") or 0.0
        )
    return None


def _bbox_center(box: dict | None) -> tuple[float, float] | None:
    if not box:
        return None
    return ((float(box["x1"]) + float(box["x2"])) / 2.0, (float(box["y1"]) + float(box["y2"])) / 2.0)


def _body_distance(left: dict, right: dict) -> float | None:
    left_box = left.get("person_bbox")
    right_box = right.get("person_bbox")
    left_center = _bbox_center(left_box)
    right_center = _bbox_center(right_box)
    if left_center is None or right_center is None:
        return None

    normalizer = max(1.0, bbox_area(left_box) ** 0.5, bbox_area(right_box) ** 0.5)
    return (((left_center[0] - right_center[0]) ** 2 + (left_center[1] - right_center[1]) ** 2) ** 0.5) / normalizer


def _colors_compatible(left: dict, right: dict) -> bool:
    for prefix in _core_clothing_parts():
        left_visible = bool(left.get(f"{prefix}_visible"))
        right_visible = bool(right.get(f"{prefix}_visible"))
        left_color = left.get(f"{prefix}_color")
        right_color = right.get(f"{prefix}_color")
        if left_visible and right_visible and left_color and right_color:
            if left_color != "unknown" and right_color != "unknown" and left_color != right_color:
                return False
    return True


def _can_merge(left: dict, right: dict) -> bool:
    if left.get("camera_id") != right.get("camera_id"):
        return False

    gap = _time_gap(left, right)
    if gap is None or gap < 0.0 or gap > settings.event_time_window_sec:
        return False

    left_person = left.get("person_id")
    right_person = right.get("person_id")
    if left_person or right_person:
        return left_person is not None and left_person == right_person

    if left.get("track_id") or right.get("track_id"):
        return left.get("track_id") is not None and left.get("track_id") == right.get("track_id")

    distance = _body_distance(left, right)
    if distance is None:
        return False
    return distance <= 0.55 and _colors_compatible(left, right)


def _aggregate_color(
    observations: list[dict],
    prefix: str,
) -> tuple[str | None, float | None, bool | None, dict[str, float] | None]:
    if prefix == "upper":
        prob_color, prob_confidence, prob_visible, probabilities = _aggregate_upper_color_probs(observations)
        if probabilities:
            return prob_color, prob_confidence, prob_visible, probabilities

    threshold = (
        settings.upper_color_confidence_threshold
        if prefix == "upper"
        else settings.lower_color_confidence_threshold
    )
    weights: dict[str, float] = {}
    support: Counter[str] = Counter()
    total_weight = 0.0
    for obs in observations:
        if not obs.get(f"{prefix}_visible"):
            continue
        color = obs.get(f"{prefix}_color")
        confidence = obs.get(f"{prefix}_color_confidence")
        valid_ratio = obs.get(f"{prefix}_valid_pixel_ratio")
        if not color or color == "unknown" or confidence is None or float(confidence) < threshold:
            continue
        weight = float(confidence) * float(valid_ratio or 0.0)
        weights[color] = weights.get(color, 0.0) + weight
        support[color] += 1
        total_weight += weight

    if not weights or total_weight <= 0.0:
        visible = any(bool(obs.get(f"{prefix}_visible")) for obs in observations)
        return "unknown", 0.0 if visible else None, visible, None

    color, weight = max(weights.items(), key=lambda item: item[1])
    dominance = weight / total_weight
    average_source_confidence = weight / max(1, support[color])
    confidence = dominance * min(1.0, average_source_confidence)
    return color, round(float(confidence), 4), True, None


def _valid_upper_probabilities(value: dict | None) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    out = {}
    for color in _UPPER_PROB_COLORS:
        try:
            probability = float(value.get(color) or 0.0)
        except (TypeError, ValueError):
            probability = 0.0
        if probability > 0.0:
            out[color] = probability
    total = sum(out.values())
    if total <= 0.0:
        return {}
    return {color: probability / total for color, probability in out.items()}


def _aggregate_upper_color_probs(observations: list[dict]) -> tuple[str, float | None, bool, dict[str, float] | None]:
    totals: dict[str, float] = {}
    total_weight = 0.0
    for obs in observations:
        probabilities = _valid_upper_probabilities(obs.get("upper_color_probs"))
        if not probabilities:
            continue
        valid_ratio = float(obs.get("upper_valid_pixel_ratio") or 1.0)
        confidence = float(obs.get("upper_color_confidence") or 0.0)
        weight = max(0.20, min(1.0, valid_ratio)) * max(0.30, min(1.0, confidence * 4.0))
        for color, probability in probabilities.items():
            totals[color] = totals.get(color, 0.0) + probability * weight
        total_weight += weight

    if not totals or total_weight <= 0.0:
        visible = any(bool(obs.get("upper_visible")) for obs in observations)
        return "unknown", 0.0 if visible else None, visible, None

    normalized = {color: value / total_weight for color, value in totals.items()}
    color = choose_upper_color_from_probs(normalized)
    probability = normalized.get(color, 0.0)
    return color, round(float(probability), 4), True, {
        color_name: round(float(normalized.get(color_name, 0.0)), 6)
        for color_name in _UPPER_PROB_COLORS
    }


def _representative_observation(observations: list[dict]) -> dict:
    return max(
        observations,
        key=lambda obs: (
            1 if obs.get("face_record_id") else 0,
            float(obs.get("person_detection_confidence") or 0.0),
            float(obs.get("upper_color_confidence") or 0.0),
            float(obs.get("lower_color_confidence") or 0.0),
            bbox_area(obs.get("person_bbox")),
        ),
    )


def _event_id(event: dict) -> str:
    raw = "|".join(
        [
            str(event.get("camera_id") or ""),
            str(event.get("video_id") or ""),
            str(event.get("track_id") or ""),
            str(event.get("person_id") or ""),
            str(event.get("start_time") or ""),
            str(event.get("end_time") or ""),
            f"{float(event.get('start_timestamp_sec') or 0.0):.3f}",
            f"{float(event.get('end_timestamp_sec') or 0.0):.3f}",
            str(event.get("representative_observation_id") or ""),
        ]
    )
    return "event_" + sha1(raw.encode("utf-8")).hexdigest()[:16]


def _appearance_session_id(person_id: str, session_index: int, events: list[dict]) -> str:
    first = events[0]
    last = events[-1]
    raw = "|".join(
        [
            person_id,
            str(session_index),
            str(first.get("event_id") or ""),
            str(last.get("event_id") or ""),
            str(first.get("start_time") or ""),
            str(last.get("end_time") or ""),
        ]
    )
    return "appearance_" + sha1(raw.encode("utf-8")).hexdigest()[:16]


def _event_sort_key(event: dict) -> tuple[float, float, str]:
    captured = _parse_iso_seconds(event.get("start_time") or event.get("end_time"))
    return (
        captured if captured is not None else float("inf"),
        float(event.get("start_timestamp_sec") or 0.0),
        str(event.get("event_id") or ""),
    )


def _event_gap(left: dict, right: dict) -> float | None:
    left_time = _parse_iso_seconds(left.get("end_time") or left.get("start_time"))
    right_time = _parse_iso_seconds(right.get("start_time") or right.get("end_time"))
    if left_time is not None and right_time is not None:
        return right_time - left_time
    if left.get("video_id") and left.get("video_id") == right.get("video_id"):
        return float(right.get("start_timestamp_sec") or 0.0) - float(
            left.get("end_timestamp_sec") or 0.0
        )
    return None


def _raw_part(event: dict, prefix: str) -> dict:
    color = event.get(f"raw_{prefix}_color")
    if color is None:
        color = event.get(f"{prefix}_color")
    confidence = event.get(f"raw_{prefix}_color_confidence")
    if confidence is None:
        confidence = event.get(f"{prefix}_color_confidence")
    visible = event.get(f"raw_{prefix}_visible")
    if visible is None:
        visible = event.get(f"{prefix}_visible")
    probabilities = None
    if prefix == "upper":
        probabilities = event.get("raw_upper_color_probs")
        if probabilities is None:
            probabilities = event.get("upper_color_probs")
    observed = bool(visible)
    return {
        "color": color or "unknown",
        "confidence": confidence,
        "observed": observed,
        "visible": observed and color not in (None, "", "unknown"),
        "probabilities": _valid_upper_probabilities(probabilities) if prefix == "upper" else None,
    }


def _profile_for_events(events: list[dict], prefix: str) -> dict:
    if prefix == "upper":
        profile = _upper_probability_profile(events)
        if profile is not None:
            return profile

    weights: Counter[str] = Counter()
    support: Counter[str] = Counter()
    confidence_sum: Counter[str] = Counter()
    for event in events:
        part = _raw_part(event, prefix)
        if not part["visible"]:
            continue
        confidence = float(part["confidence"] or 0.0)
        weights[part["color"]] += max(0.05, confidence)
        confidence_sum[part["color"]] += confidence
        support[part["color"]] += 1

    if not weights:
        return {
            "color": "unknown",
            "confidence": None,
            "support": 0,
            "visible": False,
            "counts": {},
            "probabilities": None,
        }

    color, weight = weights.most_common(1)[0]
    total = sum(weights.values())
    average_confidence = confidence_sum[color] / max(1, support[color])
    return {
        "color": color,
        "confidence": round(float((weight / max(1e-6, total)) * min(1.0, average_confidence)), 4),
        "support": int(support[color]),
        "visible": True,
        "counts": dict(support.most_common()),
        "probabilities": None,
    }


def _upper_probability_profile(events: list[dict]) -> dict | None:
    totals: dict[str, float] = {}
    support = 0
    counts: Counter[str] = Counter()
    for event in events:
        part = _raw_part(event, "upper")
        probabilities = part.get("probabilities")
        if not probabilities:
            continue
        confidence = float(part.get("confidence") or 0.0)
        weight = max(0.35, min(1.0, confidence * 4.0))
        for color, probability in probabilities.items():
            totals[color] = totals.get(color, 0.0) + float(probability) * weight
        if part["visible"]:
            counts[part["color"]] += 1
        support += 1

    if not totals or support == 0:
        return None

    total_weight = sum(totals.values())
    probabilities = {color: value / max(1e-6, total_weight) for color, value in totals.items()}
    color = choose_upper_color_from_probs(probabilities)
    probability = probabilities.get(color, 0.0)
    return {
        "color": color,
        "confidence": round(float(probability), 4),
        "support": support,
        "visible": True,
        "counts": dict(counts.most_common()),
        "probabilities": {
            color_name: round(float(probabilities.get(color_name, 0.0)), 6)
            for color_name in _UPPER_PROB_COLORS
        },
    }


def _session_profile(events: list[dict]) -> dict:
    lower_profile = _profile_for_events(events, "lower") if settings.enable_lower_clothing_core else _unknown_part()
    return {
        "upper": _profile_for_events(events, "upper"),
        "lower": lower_profile,
    }


def _strong_profile(profile: dict) -> bool:
    return (
        profile.get("visible")
        and int(profile.get("support") or 0) >= settings.appearance_session_min_support
        and float(profile.get("confidence") or 0.0) >= settings.appearance_session_profile_confidence
        and profile.get("color") not in (None, "", "unknown")
    )


def _should_start_new_appearance_session(current_events: list[dict], event: dict) -> bool:
    if not current_events:
        return False

    gap = _event_gap(current_events[-1], event)
    if gap is not None and gap > settings.appearance_session_max_gap_sec:
        return True

    profile = _session_profile(current_events)
    conflicts = 0
    matches = 0
    for prefix in _core_clothing_parts():
        part = _raw_part(event, prefix)
        part_confidence = float(part["confidence"] or 0.0)
        if not part["visible"] or part_confidence < settings.appearance_session_change_confidence:
            continue
        session_part = profile[prefix]
        if not _strong_profile(session_part):
            continue
        if part["color"] == session_part["color"]:
            matches += 1
        else:
            conflicts += 1

    return conflicts > 0 and conflicts >= matches


def _normalize_part(event: dict, session_profile: dict, prefix: str) -> tuple[dict, dict]:
    if prefix == "lower" and not settings.enable_lower_clothing_core:
        return {"color": "unknown", "confidence": None, "visible": False}, _disabled_lower_reason(event)

    raw = _raw_part(event, prefix)
    profile = session_profile[prefix]
    normalized = dict(raw)
    reason = {
        "raw_color": raw["color"],
        "raw_confidence": raw["confidence"],
        "raw_observed": raw["observed"],
        "raw_probabilities": raw.get("probabilities"),
        "profile_color": profile.get("color"),
        "profile_confidence": profile.get("confidence"),
        "profile_support": profile.get("support"),
        "profile_probabilities": profile.get("probabilities"),
        "action": "keep_raw",
    }

    if _strong_profile(profile):
        profile_color = profile["color"]
        profile_confidence = float(profile.get("confidence") or 0.0)
        profile_probabilities = profile.get("probabilities")
        raw_confidence = float(raw["confidence"] or 0.0)
        if not raw["observed"]:
            reason["action"] = "keep_unobserved"
        elif not raw["visible"]:
            normalized = {
                "color": profile_color,
                "confidence": round(min(0.75, profile_confidence * 0.75), 4),
                "visible": True,
                "probabilities": profile_probabilities,
            }
            reason["action"] = "fill_unknown_color_from_appearance_session"
        elif raw["color"] != profile_color and raw_confidence < settings.appearance_session_low_confidence_threshold:
            normalized = {
                "color": profile_color,
                "confidence": round(min(0.82, max(raw_confidence, profile_confidence * 0.85)), 4),
                "visible": True,
                "probabilities": profile_probabilities,
            }
            reason["action"] = "override_low_confidence_with_appearance_session"

    reason["normalized_color"] = normalized["color"]
    reason["normalized_confidence"] = normalized["confidence"]
    reason["normalized_probabilities"] = normalized.get("probabilities")
    return normalized, reason


def _appearance_session_from_events(person_id: str, session_id: str, events: list[dict]) -> dict:
    ordered = sorted(events, key=_event_sort_key)
    profile = _session_profile(ordered)
    start_times = [event.get("start_time") for event in ordered if event.get("start_time")]
    end_times = [event.get("end_time") for event in ordered if event.get("end_time")]
    start_timestamps = [
        float(event.get("start_timestamp_sec"))
        for event in ordered
        if event.get("start_timestamp_sec") is not None
    ]
    end_timestamps = [
        float(event.get("end_timestamp_sec"))
        for event in ordered
        if event.get("end_timestamp_sec") is not None
    ]
    return {
        "session_id": session_id,
        "person_id": person_id,
        "start_time": min(start_times) if start_times else None,
        "end_time": max(end_times) if end_times else None,
        "start_timestamp_sec": min(start_timestamps) if start_timestamps else None,
        "end_timestamp_sec": max(end_timestamps) if end_timestamps else None,
        "event_count": len(ordered),
        "upper_color": profile["upper"]["color"],
        "upper_color_confidence": profile["upper"]["confidence"],
        "upper_color_support": profile["upper"]["support"],
        "upper_visible": profile["upper"]["visible"],
        "lower_color": profile["lower"]["color"],
        "lower_color_confidence": profile["lower"]["confidence"],
        "lower_color_support": profile["lower"]["support"],
        "lower_visible": profile["lower"]["visible"],
        "profile": profile,
        "session_status": "active",
        "aggregation_version": "appearance_session_v1",
    }


def _appearance_session_groups(events: list[dict]) -> list[list[dict]]:
    groups: list[list[dict]] = []
    current: list[dict] = []
    for event in sorted(events, key=_event_sort_key):
        if not current:
            current = [event]
            continue
        if _should_start_new_appearance_session(current, event):
            groups.append(current)
            current = [event]
            continue
        current.append(event)
    if current:
        groups.append(current)
    return groups


def rebuild_appearance_sessions_for_person(person_id: str) -> dict:
    events = db.list_events(person_id=person_id, limit=5000)
    db.delete_appearance_sessions_for_person(person_id)
    groups = _appearance_session_groups(events)
    sessions = []
    updated_events = 0
    for index, group in enumerate(groups, start=1):
        session_id = _appearance_session_id(person_id, index, group)
        session = db.add_appearance_session(_appearance_session_from_events(person_id, session_id, group))
        profile = session["profile"]
        sessions.append(session)
        for event in group:
            normalized_upper, upper_reason = _normalize_part(event, profile, "upper")
            normalized_lower, lower_reason = _normalize_part(event, profile, "lower")
            db.update_event_clothing_normalization(
                event["event_id"],
                {
                    "appearance_session_id": session_id,
                    "upper_color": normalized_upper["color"],
                    "upper_color_confidence": normalized_upper["confidence"],
                    "upper_visible": normalized_upper["visible"],
                    "upper_color_probs": normalized_upper.get("probabilities"),
                    "lower_color": normalized_lower["color"],
                    "lower_color_confidence": normalized_lower["confidence"],
                    "lower_visible": normalized_lower["visible"],
                    "normalized_upper_color": normalized_upper["color"],
                    "normalized_upper_color_confidence": normalized_upper["confidence"],
                    "normalized_upper_visible": normalized_upper["visible"],
                    "normalized_upper_color_probs": normalized_upper.get("probabilities"),
                    "normalized_lower_color": normalized_lower["color"],
                    "normalized_lower_color_confidence": normalized_lower["confidence"],
                    "normalized_lower_visible": normalized_lower["visible"],
                    "clothing_normalization_version": "appearance_session_v1",
                    "clothing_normalization_reason": {
                        "upper": upper_reason,
                        "lower": lower_reason,
                    },
                },
            )
            updated_events += 1

    db.update_person_event_stats(person_id)
    return {
        "person_id": person_id,
        "source_events": len(events),
        "sessions": len(sessions),
        "updated_events": updated_events,
    }


def rebuild_appearance_sessions_for_persons(person_ids: set[str]) -> dict:
    results = [
        rebuild_appearance_sessions_for_person(person_id)
        for person_id in sorted(person_ids)
        if person_id
    ]
    return {
        "persons": len(results),
        "sessions": sum(int(result["sessions"]) for result in results),
        "updated_events": sum(int(result["updated_events"]) for result in results),
        "results": results,
    }


def rebuild_all_appearance_sessions() -> dict:
    return rebuild_appearance_sessions_for_persons(
        {person["person_id"] for person in db.list_persons()}
    )


def list_appearance_sessions(person_id: str | None = None) -> list[dict]:
    return db.list_appearance_sessions(person_id=person_id)


def _event_from_observations(observations: list[dict]) -> dict:
    ordered = sorted(observations, key=_time_key)
    representative = _representative_observation(ordered)
    captured_values = [obs.get("captured_at") for obs in ordered if obs.get("captured_at")]
    timestamps = [float(obs.get("video_timestamp_sec") or 0.0) for obs in ordered]
    person_ids = [obs.get("person_id") for obs in ordered if obs.get("person_id")]
    upper_color, upper_confidence, upper_visible, upper_probs = _aggregate_color(ordered, "upper")
    raw_lower_color, raw_lower_confidence, raw_lower_visible, _ = _aggregate_color(ordered, "lower")
    if settings.enable_lower_clothing_core:
        lower_color = raw_lower_color
        lower_confidence = raw_lower_confidence
        lower_visible = raw_lower_visible
    else:
        lower_color = "unknown"
        lower_confidence = None
        lower_visible = False
    event = {
        "event_id": "",
        "camera_id": representative["camera_id"],
        "video_id": representative.get("video_id"),
        "live_source_id": representative.get("live_source_id"),
        "track_id": representative.get("track_id"),
        "person_id": person_ids[0] if person_ids else None,
        "start_time": min(captured_values) if captured_values else None,
        "end_time": max(captured_values) if captured_values else None,
        "start_timestamp_sec": min(timestamps) if timestamps else None,
        "end_timestamp_sec": max(timestamps) if timestamps else None,
        "observation_count": len(ordered),
        "face_count": sum(1 for obs in ordered if obs.get("face_record_id")),
        "representative_observation_id": representative["observation_id"],
        "representative_face_id": representative.get("face_record_id"),
        "representative_frame_path": representative.get("frame_path"),
        "upper_color": upper_color,
        "upper_color_confidence": upper_confidence,
        "upper_visible": upper_visible,
        "upper_color_probs": upper_probs,
        "lower_color": lower_color,
        "lower_color_confidence": lower_confidence,
        "lower_visible": lower_visible,
        "raw_upper_color": upper_color,
        "raw_upper_color_confidence": upper_confidence,
        "raw_upper_visible": upper_visible,
        "raw_upper_color_probs": upper_probs,
        "raw_lower_color": raw_lower_color,
        "raw_lower_color_confidence": raw_lower_confidence,
        "raw_lower_visible": raw_lower_visible,
        "normalized_upper_color": upper_color,
        "normalized_upper_color_confidence": upper_confidence,
        "normalized_upper_visible": upper_visible,
        "normalized_upper_color_probs": upper_probs,
        "normalized_lower_color": lower_color,
        "normalized_lower_color_confidence": lower_confidence,
        "normalized_lower_visible": lower_visible,
        "appearance_session_id": None,
        "clothing_normalization_version": "event_raw_v1",
        "clothing_normalization_reason": None,
        "identity_confidence": 1.0 if person_ids else None,
        "event_status": "closed",
        "aggregation_version": "event_window_v1",
    }
    event["event_id"] = _event_id(event)
    return event


def _event_bucket_key(observation: dict) -> tuple:
    camera_id = observation.get("camera_id")
    if observation.get("person_id"):
        return ("person", camera_id, observation["person_id"])
    if observation.get("track_id"):
        return ("track", camera_id, observation["track_id"])
    if observation.get("person_bbox"):
        return ("body", camera_id, observation["observation_id"])
    return ("face", camera_id, observation["observation_id"])


def rebuild_events_for_video(video_id: str) -> dict:
    touched_person_ids = set(db.delete_events_for_video(video_id))
    observations = sorted(db.list_person_observations(video_id=video_id), key=_time_key)
    buckets: dict[tuple, list[dict]] = {}
    for observation in observations:
        buckets.setdefault(_event_bucket_key(observation), []).append(observation)

    groups: list[list[dict]] = []

    for bucket_observations in buckets.values():
        current: list[dict] = []
        for observation in sorted(bucket_observations, key=_time_key):
            if not current:
                current = [observation]
                continue
            if _can_merge(current[-1], observation):
                current.append(observation)
                continue
            groups.append(current)
            current = [observation]

        if current:
            groups.append(current)

    events = []
    for group in groups:
        event = _event_from_observations(group)
        saved = db.add_event(event, group)
        events.append(saved)
        if saved.get("person_id"):
            touched_person_ids.add(saved["person_id"])

    appearance_result = rebuild_appearance_sessions_for_persons(touched_person_ids)

    return {
        "video_id": video_id,
        "source_observations": len(observations),
        "events": len(events),
        "appearance_sessions": appearance_result,
    }


def rebuild_events_for_videos(video_ids: set[str]) -> dict:
    results = [rebuild_events_for_video(video_id) for video_id in sorted(video_ids) if video_id]
    return {
        "videos": len(results),
        "events": sum(int(result["events"]) for result in results),
        "source_observations": sum(int(result["source_observations"]) for result in results),
        "results": results,
    }


def list_events(**filters) -> list[dict]:
    return db.list_events(**filters)


def search_by_clothes(
    *,
    upper_color: str | None = None,
    lower_color: str | None = None,
    camera_id: str | None = None,
    identified: bool | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    effective_lower_color = lower_color if settings.enable_lower_clothing_core else None
    events = db.list_events(
        upper_color=upper_color,
        lower_color=effective_lower_color,
        camera_id=camera_id,
        identified=identified,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
    )
    for event in events:
        reasons = []
        score = 0.0
        if upper_color:
            reasons.append(f"upper_color={upper_color}")
            score += float(event.get("upper_color_confidence") or 0.0)
        if lower_color:
            if settings.enable_lower_clothing_core:
                reasons.append(f"lower_color={lower_color}")
                score += float(event.get("lower_color_confidence") or 0.0)
            else:
                event["ignored_lower_color_filter"] = lower_color
        event["match_reasons"] = reasons
        event["match_score"] = round(score / max(1, len(reasons)), 4) if reasons else None
    return events
