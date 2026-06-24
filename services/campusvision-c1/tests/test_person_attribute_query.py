from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

pytest.importorskip("cv2")

from app.services import person_attribute_query_service as service  # noqa: E402


def _event(
    event_id: str,
    *,
    person_id: str | None,
    upper_color: str,
    camera_id: str = "c1",
    start_time: str = "2026-06-23T08:00:00",
    probs: dict | None = None,
) -> dict:
    return {
        "event_id": event_id,
        "person_id": person_id,
        "camera_id": camera_id,
        "video_id": "video1",
        "start_time": start_time,
        "end_time": start_time,
        "start_timestamp_sec": 1.0,
        "end_timestamp_sec": 1.0,
        "observation_count": 1,
        "face_count": 1,
        "representative_observation_id": "obs_" + event_id,
        "representative_face_id": "face_" + event_id,
        "representative_frame_url": "/api/v1/media/event/frame/" + event_id,
        "representative_body_crop_url": "/api/v1/media/event/body/" + event_id,
        "representative_face_crop_url": "/api/v1/media/face/face_" + event_id,
        "upper_color": upper_color,
        "upper_color_confidence": 0.8,
        "upper_visible": True,
        "normalized_upper_color": upper_color,
        "normalized_upper_color_confidence": 0.8,
        "normalized_upper_visible": True,
        "normalized_upper_color_probs": probs or {upper_color: 0.8},
        "appearance_session_id": "appearance_" + event_id,
        "event_status": "closed",
        "aggregation_version": "event_window_v1",
        "created_at": start_time,
        "updated_at": start_time,
    }


def _patch_store(monkeypatch, *, events, gender_profiles=None, glasses_profiles=None, event_glasses=None):
    monkeypatch.setattr(
        service.db,
        "list_persons",
        lambda: [
            {"person_id": "p1", "face_count": 12, "representative_face_id": "face_p1"},
            {"person_id": "p2", "face_count": 11, "representative_face_id": "face_p2"},
            {"person_id": "p3", "face_count": 2, "representative_face_id": "face_p3"},
        ],
    )
    monkeypatch.setattr(
        service.db,
        "list_cameras",
        lambda: [{"camera_id": "c1", "name": "Camera 1", "location": "Hall"}],
    )

    def list_events(**filters):
        out = list(events)
        if filters.get("camera_id"):
            out = [event for event in out if event["camera_id"] == filters["camera_id"]]
        identified = filters.get("identified")
        if identified is True:
            out = [event for event in out if event.get("person_id")]
        elif identified is False:
            out = [event for event in out if not event.get("person_id")]
        offset = int(filters.get("offset") or 0)
        limit = int(filters.get("limit") or len(out))
        return out[offset : offset + limit]

    monkeypatch.setattr(service.db, "list_events", list_events)
    monkeypatch.setattr(
        service.gender_presentation_service,
        "load_profiles",
        lambda: {"profiles": gender_profiles or {}},
    )
    monkeypatch.setattr(
        service.glasses_status_service,
        "load_profiles",
        lambda: {"profiles": glasses_profiles or {}, "event_profiles": event_glasses or {}},
    )


def test_attribute_query_returns_exact_before_partial_with_failures(monkeypatch):
    events = [
        _event("e1", person_id="p1", upper_color="black", start_time="2026-06-23T08:00:01"),
        _event(
            "e2",
            person_id="p2",
            upper_color="white",
            start_time="2026-06-23T08:00:02",
            probs={"white": 0.7, "black": 0.22},
        ),
    ]
    _patch_store(
        monkeypatch,
        events=events,
        gender_profiles={
            "p1": {"gender_presentation": "masculine", "confidence": 0.9},
            "p2": {"gender_presentation": "masculine", "confidence": 0.8},
        },
        event_glasses={
            "e1": {"glasses_status": "no_glasses", "glasses_confidence": 0.9},
            "e2": {"glasses_status": "unknown", "glasses_confidence": 0.4},
        },
    )

    result = service.query_person_attributes(
        {
            "camera_ids": ["c1"],
            "gender_presentation": ["masculine"],
            "glasses_status": ["no_glasses"],
            "upper_colors": ["black"],
            "include_near_misses": True,
            "person_scope": "stable",
            "limit": 10,
        }
    )

    assert [item["event_id"] for item in result["results"]] == ["e1", "e2"]
    assert result["results"][0]["match_type"] == "exact"
    assert result["results"][1]["match_type"] == "partial"
    assert {failure["field"] for failure in result["results"][1]["failed_conditions"]} == {
        "glasses_status",
        "upper_color",
    }
    assert result["results"][0]["representative_body_crop_url"].endswith("/e1")
    assert result["summary"]["exact_matches"] == 1
    assert result["summary"]["partial_matches"] == 1


def test_attribute_query_excludes_candidates_until_requested(monkeypatch):
    events = [
        _event("stable", person_id="p1", upper_color="black"),
        _event("candidate", person_id="p3", upper_color="black"),
    ]
    _patch_store(
        monkeypatch,
        events=events,
        gender_profiles={
            "p1": {"gender_presentation": "masculine", "confidence": 0.9},
            "p3": {"gender_presentation": "masculine", "confidence": 0.9},
        },
    )

    stable_only = service.query_person_attributes({"upper_colors": ["black"], "person_scope": "stable"})
    with_candidates = service.query_person_attributes(
        {"upper_colors": ["black"], "include_candidates": True}
    )

    assert [item["event_id"] for item in stable_only["results"]] == ["stable"]
    assert {item["event_id"] for item in with_candidates["results"]} == {"stable", "candidate"}


def test_attribute_query_scores_before_candidate_pool_truncation(monkeypatch):
    events = [
        _event("partial_old", person_id="p1", upper_color="white", start_time="2026-06-23T08:00:01"),
        _event("exact_new", person_id="p2", upper_color="black", start_time="2026-06-23T08:00:02"),
    ]
    _patch_store(monkeypatch, events=events)

    result = service.query_person_attributes(
        {
            "upper_colors": ["black"],
            "person_scope": "stable",
            "include_near_misses": True,
            "candidate_pool_size": 1,
            "limit": 10,
        }
    )

    assert result["summary"]["scanned_events"] == 2
    assert result["summary"]["ranked_candidates"] == 1
    assert [item["event_id"] for item in result["results"]] == ["exact_new"]


def test_attribute_query_rejects_unsupported_values():
    try:
        service.query_person_attributes({"glasses_status": ["maybe"]})
    except ValueError as exc:
        assert "unsupported glasses_status" in str(exc)
    else:
        raise AssertionError("expected unsupported glasses status to fail")
