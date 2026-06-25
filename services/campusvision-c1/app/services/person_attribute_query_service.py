from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from app.core.config import settings
from app.services import gender_presentation_service, glasses_status_service
from app.storage import db


GENDER_PRESENTATION_VALUES = {"masculine", "feminine", "neutral", "unknown"}
GLASSES_STATUS_VALUES = {"glasses", "no_glasses", "unknown"}
PERSON_SCOPES = {"stable", "identified", "all", "unidentified"}


def _clean_values(values: list[str] | tuple[str, ...] | None) -> list[str]:
    out = []
    for value in values or []:
        text = str(value or "").strip()
        if text and text not in out:
            out.append(text)
    return out


def _validate_values(name: str, values: list[str], allowed: set[str]) -> None:
    invalid = sorted(set(values) - allowed)
    if invalid:
        raise ValueError(f"unsupported {name}: {', '.join(invalid)}")


def _identity_status(person: dict[str, Any] | None) -> str | None:
    if not person:
        return None
    return (
        "stable"
        if int(person.get("face_count") or 0) >= int(settings.person_identity_stable_min_faces)
        else "candidate"
    )


def _time_display(seconds: float | int | None) -> str | None:
    if seconds is None:
        return None
    total_ms = max(0, int(round(float(seconds) * 1000)))
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    sec, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{sec:02d}.{ms:03d}"


def _camera_lookup() -> dict[str, dict[str, Any]]:
    return {str(camera["camera_id"]): camera for camera in db.list_cameras()}


def _person_lookup() -> dict[str, dict[str, Any]]:
    people = {}
    for raw_person in db.list_persons():
        person = dict(raw_person)
        person.pop("embedding", None)
        status = _identity_status(person)
        person["identity_status"] = status
        person["is_stable_identity"] = status == "stable"
        if person.get("representative_face_id"):
            person["representative_face_crop_url"] = (
                f"/api/v1/media/face/{person['representative_face_id']}"
            )
        people[str(person["person_id"])] = person
    return people


def _profile_value(profile: dict[str, Any] | None, *keys: str) -> Any:
    if not isinstance(profile, dict):
        return None
    for key in keys:
        value = profile.get(key)
        if value is not None:
            return value
    return None


def _choice_condition(
    *,
    field: str,
    expected: list[str],
    actual: str | None,
    confidence: float | None = None,
    probabilities: dict[str, Any] | None = None,
) -> tuple[float, dict[str, Any] | None]:
    if not expected:
        return 1.0, None

    actual_value = actual or "unknown"
    if actual_value in expected:
        return 1.0, None

    if actual_value == "unknown":
        return 0.35, {
            "field": field,
            "expected": expected,
            "actual": actual_value,
            "reason": f"{field}_unknown",
        }

    probability_score = 0.0
    if isinstance(probabilities, dict):
        for value in expected:
            try:
                probability_score = max(probability_score, float(probabilities.get(value) or 0.0))
            except (TypeError, ValueError):
                continue
    if probability_score > 0:
        score = min(0.65, max(0.05, probability_score))
    else:
        score = 0.0

    return score, {
        "field": field,
        "expected": expected,
        "actual": actual,
        "actual_confidence": confidence,
        "reason": f"{field}_mismatch",
    }


def _event_glasses_profile(
    event: dict[str, Any],
    *,
    event_profiles: dict[str, Any],
    person_profiles: dict[str, Any],
) -> dict[str, Any] | None:
    event_profile = event_profiles.get(str(event.get("event_id") or ""))
    if isinstance(event_profile, dict):
        return event_profile
    person_id = str(event.get("person_id") or "")
    person_profile = person_profiles.get(person_id)
    return person_profile if isinstance(person_profile, dict) else None


def _event_face_bbox(event: dict[str, Any]) -> Any:
    face_id = event.get("representative_face_id")
    if not face_id:
        return None
    face_record = db.get_face_record(str(face_id))
    if not isinstance(face_record, dict):
        return None
    return face_record.get("bbox")


def _event_payload(
    event: dict[str, Any],
    *,
    person: dict[str, Any] | None,
    camera: dict[str, Any] | None,
    gender_profile: dict[str, Any] | None,
    glasses_profile: dict[str, Any] | None,
) -> dict[str, Any]:
    upper_color = event.get("normalized_upper_color") or event.get("upper_color") or "unknown"
    upper_confidence = event.get("normalized_upper_color_confidence")
    if upper_confidence is None:
        upper_confidence = event.get("upper_color_confidence")

    gender_value = _profile_value(gender_profile, "gender_presentation") or "unknown"
    glasses_value = _profile_value(glasses_profile, "glasses_status") or "unknown"
    glasses_confidence = _profile_value(glasses_profile, "glasses_confidence", "confidence")
    representative_observation = (
        event.get("representative_observation")
        if isinstance(event.get("representative_observation"), dict)
        else None
    )
    person_bbox = (
        event.get("person_bbox")
        or event.get("person_box")
        or event.get("body_bbox")
        or event.get("body_box")
        or event.get("representative_person_bbox")
        or event.get("representative_body_bbox")
        or (representative_observation or {}).get("person_bbox")
    )
    face_bbox = (
        event.get("face_bbox")
        or event.get("face_box")
        or event.get("representative_face_bbox")
        or event.get("representative_face_box")
        or _event_face_bbox(event)
    )

    return {
        "event_id": event.get("event_id"),
        "person_id": event.get("person_id"),
        "identity_status": (person or {}).get("identity_status"),
        "is_stable_identity": (person or {}).get("is_stable_identity"),
        "camera_id": event.get("camera_id"),
        "camera_name": (camera or {}).get("name"),
        "location": (camera or {}).get("location"),
        "video_id": event.get("video_id"),
        "live_source_id": event.get("live_source_id"),
        "track_id": event.get("track_id"),
        "start_time": event.get("start_time"),
        "end_time": event.get("end_time"),
        "start_timestamp_sec": event.get("start_timestamp_sec"),
        "end_timestamp_sec": event.get("end_timestamp_sec"),
        "start_time_display": _time_display(event.get("start_timestamp_sec")),
        "end_time_display": _time_display(event.get("end_timestamp_sec")),
        "observation_count": int(event.get("observation_count") or 0),
        "face_count": int(event.get("face_count") or 0),
        "representative_observation_id": event.get("representative_observation_id"),
        "representative_face_id": event.get("representative_face_id"),
        "representative_frame_url": event.get("representative_frame_url"),
        "representative_body_crop_url": event.get("representative_body_crop_url"),
        "representative_face_crop_url": event.get("representative_face_crop_url"),
        "person_bbox": person_bbox,
        "body_bbox": person_bbox,
        "representative_person_bbox": person_bbox,
        "representative_body_bbox": person_bbox,
        "face_bbox": face_bbox,
        "face_box": face_bbox,
        "representative_face_bbox": face_bbox,
        "representative_face_box": face_bbox,
        "body_visibility": event.get("body_visibility"),
        "upper_color": upper_color,
        "upper_color_confidence": upper_confidence,
        "upper_visible": event.get("normalized_upper_visible")
        if event.get("normalized_upper_visible") is not None
        else event.get("upper_visible"),
        "raw_upper_color": event.get("raw_upper_color"),
        "raw_upper_color_confidence": event.get("raw_upper_color_confidence"),
        "normalized_upper_color": event.get("normalized_upper_color"),
        "normalized_upper_color_confidence": event.get("normalized_upper_color_confidence"),
        "appearance_session_id": event.get("appearance_session_id"),
        "clothing_normalization_version": event.get("clothing_normalization_version"),
        "gender_presentation": gender_value,
        "gender_presentation_label": _profile_value(
            gender_profile,
            "gender_presentation_label",
        ),
        "gender_presentation_confidence": _profile_value(gender_profile, "confidence"),
        "gender_presentation_evidence_quality": _profile_value(gender_profile, "evidence_quality"),
        "glasses_status": glasses_value,
        "glasses_status_label": _profile_value(glasses_profile, "glasses_status_label"),
        "glasses_confidence": glasses_confidence,
        "glasses_evidence_quality": _profile_value(glasses_profile, "glasses_evidence_quality", "evidence_quality"),
        "glasses_model_version": _profile_value(glasses_profile, "glasses_model_version", "model_version"),
        "identity_confidence": event.get("identity_confidence"),
        "event_status": event.get("event_status"),
        "aggregation_version": event.get("aggregation_version"),
        "created_at": event.get("created_at"),
        "updated_at": event.get("updated_at"),
    }


def _hydrate_page_media(results: list[dict[str, Any]]) -> None:
    for result in results:
        event_id = result.get("event_id")
        if not event_id:
            continue
        event = db.get_event(str(event_id))
        if not event:
            continue
        for field in (
            "representative_frame_url",
            "representative_body_crop_url",
            "representative_face_crop_url",
            "body_visibility",
            "person_bbox",
            "body_bbox",
            "representative_person_bbox",
            "representative_body_bbox",
            "face_bbox",
            "face_box",
            "representative_face_bbox",
            "representative_face_box",
        ):
            if event.get(field) is not None:
                result[field] = event.get(field)
        nested_event = result.get("event")
        if isinstance(nested_event, dict):
            for field in (
                "representative_frame_url",
                "representative_body_crop_url",
                "representative_face_crop_url",
                "body_visibility",
                "person_bbox",
                "body_bbox",
                "representative_person_bbox",
                "representative_body_bbox",
                "face_bbox",
                "face_box",
                "representative_face_bbox",
                "representative_face_box",
            ):
                if event.get(field) is not None:
                    nested_event[field] = event.get(field)


def _passes_person_scope(event: dict[str, Any], person: dict[str, Any] | None, scope: str) -> bool:
    person_id = event.get("person_id")
    if scope == "all":
        return True
    if scope == "unidentified":
        return not person_id
    if not person_id:
        return False
    if scope == "identified":
        return True
    return bool(person and person.get("is_stable_identity"))


def _active_conditions(
    *,
    gender_values: list[str],
    glasses_values: list[str],
    upper_colors: list[str],
) -> list[str]:
    out = []
    if gender_values:
        out.append("gender_presentation")
    if glasses_values:
        out.append("glasses_status")
    if upper_colors:
        out.append("upper_color")
    return out


def query_person_attributes(query: dict[str, Any]) -> dict[str, Any]:
    time_range = query.get("time_range") or {}
    start_time = time_range.get("start_time") if isinstance(time_range, dict) else None
    end_time = time_range.get("end_time") if isinstance(time_range, dict) else None
    camera_ids = _clean_values(query.get("camera_ids"))
    gender_values = _clean_values(query.get("gender_presentation"))
    glasses_values = _clean_values(query.get("glasses_status"))
    upper_colors = _clean_values(query.get("upper_colors"))
    include_near_misses = bool(query.get("include_near_misses", True))
    include_candidates = bool(query.get("include_candidates", False))
    person_scope = str(query.get("person_scope") or "").strip() or (
        "identified" if include_candidates else "stable"
    )
    if include_candidates and person_scope == "stable":
        person_scope = "identified"
    limit = max(1, min(int(query.get("limit") or 50), 200))
    offset = max(0, int(query.get("offset") or 0))
    candidate_pool_size = max(1, min(int(query.get("candidate_pool_size") or 5000), 5000))
    candidate_scan_limit = max(
        candidate_pool_size,
        offset + limit,
        max(1, min(int(query.get("scan_limit") or 20000), 50000)),
    )
    min_score = query.get("min_score")
    if min_score is not None:
        min_score = max(0.0, min(float(min_score), 1.0))

    _validate_values("person_scope", [person_scope], PERSON_SCOPES)
    _validate_values("gender_presentation", gender_values, GENDER_PRESENTATION_VALUES)
    _validate_values("glasses_status", glasses_values, GLASSES_STATUS_VALUES)
    _validate_values("upper_color", upper_colors, set(settings.clothing_color_labels))

    people = _person_lookup()
    cameras = _camera_lookup()
    gender_profiles = gender_presentation_service.load_profiles().get("profiles") or {}
    glasses_data = glasses_status_service.load_profiles()
    glasses_person_profiles = glasses_data.get("profiles") or {}
    glasses_event_profiles = glasses_data.get("event_profiles") or {}

    identified = None
    if person_scope in {"stable", "identified"}:
        identified = True
    elif person_scope == "unidentified":
        identified = False

    db_camera_id = camera_ids[0] if len(camera_ids) == 1 else None
    events = db.list_events(
        camera_id=db_camera_id,
        identified=identified,
        start_time=start_time,
        end_time=end_time,
        limit=candidate_scan_limit,
        offset=0,
        latest_first=True,
        include_representative_observation=True,
    )

    active = _active_conditions(
        gender_values=gender_values,
        glasses_values=glasses_values,
        upper_colors=upper_colors,
    )
    effective_min_score = min_score
    if effective_min_score is None and active:
        effective_min_score = 0.01

    results = []
    scanned = 0
    filtered_by_camera = 0
    filtered_by_scope = 0
    camera_id_set = set(camera_ids)
    for event in events:
        scanned += 1
        if camera_id_set and str(event.get("camera_id") or "") not in camera_id_set:
            filtered_by_camera += 1
            continue
        person_id = str(event.get("person_id") or "")
        person = people.get(person_id)
        if not _passes_person_scope(event, person, person_scope):
            filtered_by_scope += 1
            continue

        gender_profile = gender_profiles.get(person_id)
        if not isinstance(gender_profile, dict):
            gender_profile = None
        glasses_profile = _event_glasses_profile(
            event,
            event_profiles=glasses_event_profiles,
            person_profiles=glasses_person_profiles,
        )
        camera = cameras.get(str(event.get("camera_id") or ""))
        payload = _event_payload(
            event,
            person=person,
            camera=camera,
            gender_profile=gender_profile,
            glasses_profile=glasses_profile,
        )

        condition_scores: dict[str, float] = {}
        failed_conditions: list[dict[str, Any]] = []
        if start_time or end_time:
            condition_scores["time_range"] = 1.0
        if camera_ids:
            condition_scores["camera_id"] = 1.0
        if person_scope:
            condition_scores["person_scope"] = 1.0

        soft_scores = []
        score, failure = _choice_condition(
            field="gender_presentation",
            expected=gender_values,
            actual=payload.get("gender_presentation"),
            confidence=payload.get("gender_presentation_confidence"),
        )
        if gender_values:
            soft_scores.append(score)
            condition_scores["gender_presentation"] = round(score, 4)
            if failure:
                failed_conditions.append(failure)

        score, failure = _choice_condition(
            field="glasses_status",
            expected=glasses_values,
            actual=payload.get("glasses_status"),
            confidence=payload.get("glasses_confidence"),
        )
        if glasses_values:
            soft_scores.append(score)
            condition_scores["glasses_status"] = round(score, 4)
            if failure:
                failed_conditions.append(failure)

        score, failure = _choice_condition(
            field="upper_color",
            expected=upper_colors,
            actual=payload.get("upper_color"),
            confidence=payload.get("upper_color_confidence"),
            probabilities=event.get("normalized_upper_color_probs") or event.get("upper_color_probs"),
        )
        if upper_colors:
            soft_scores.append(score)
            condition_scores["upper_color"] = round(score, 4)
            if failure:
                failed_conditions.append(failure)

        overall_score = sum(soft_scores) / len(soft_scores) if soft_scores else 1.0
        exact = not failed_conditions
        if failed_conditions and not include_near_misses:
            continue
        if effective_min_score is not None and overall_score < effective_min_score:
            continue

        match_type = "exact" if exact else "partial"
        result = {
            **payload,
            "score": round(overall_score, 6),
            "match_type": match_type,
            "failed_conditions": failed_conditions,
            "condition_scores": condition_scores,
            "event": payload,
        }
        results.append(result)

    results.sort(
        key=lambda item: (
            item.get("start_time") or item.get("end_time") or "",
            float(item.get("start_timestamp_sec") or 0.0),
            item.get("created_at") or "",
        ),
        reverse=True,
    )
    results.sort(key=lambda item: float(item["score"]), reverse=True)
    results.sort(key=lambda item: 0 if item["match_type"] == "exact" else 1)

    total = len(results)
    ranked_results = results[:candidate_pool_size]
    page = ranked_results[offset : offset + limit]
    _hydrate_page_media(page)
    exact_count = sum(1 for item in results if item["match_type"] == "exact")
    partial_count = total - exact_count
    return {
        "query_id": "attr_query_" + uuid4().hex,
        "created_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "query": {
            "time_range": {"start_time": start_time, "end_time": end_time},
            "camera_ids": camera_ids,
            "gender_presentation": gender_values,
            "glasses_status": glasses_values,
            "upper_colors": upper_colors,
            "person_scope": person_scope,
            "include_candidates": include_candidates,
            "include_near_misses": include_near_misses,
            "min_score": min_score,
            "limit": limit,
            "offset": offset,
            "candidate_pool_size": candidate_pool_size,
            "scan_limit": candidate_scan_limit,
        },
        "summary": {
            "active_soft_conditions": active,
            "scanned_events": scanned,
            "candidate_scan_limit": candidate_scan_limit,
            "ranked_candidates": len(ranked_results),
            "filtered_by_camera": filtered_by_camera,
            "filtered_by_person_scope": filtered_by_scope,
            "total_matches": total,
            "exact_matches": exact_count,
            "partial_matches": partial_count,
            "returned": len(page),
            "limit": limit,
            "offset": offset,
        },
        "results": page,
    }
