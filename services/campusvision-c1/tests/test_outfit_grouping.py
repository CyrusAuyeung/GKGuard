from __future__ import annotations

from collections import Counter

import numpy as np

from app.services import outfit_service


def _unit(values: list[float]) -> np.ndarray:
    vector = np.asarray(values, dtype=np.float32)
    return vector / np.linalg.norm(vector)


def _item(event_id: str, source: str, color: str, feature: np.ndarray) -> dict:
    return {
        "event": {"event_id": event_id, "start_timestamp_sec": float(event_id.rsplit("_", 1)[-1])},
        "source_segment": source,
        "model_upper_color": color,
        "feature": feature,
        "diagnostics": {"feature_status": "ok"},
    }


def test_chokepoint_camera_ids_share_source_segment_by_portal():
    assert outfit_service._source_segment_key({"camera_id": "p1e_s1_c1"}) == "p1"
    assert outfit_service._source_segment_key({"camera_id": "P1E_S3_C2"}) == "p1"
    assert outfit_service._source_segment_key({"camera_id": "p2e_s5_c1"}) == "p2"
    assert outfit_service._source_segment_key({"camera_id": "p2l_s5_c3"}) == "p2"


def test_generic_camera_ids_strip_only_channel_suffix():
    assert outfit_service._source_segment_key({"camera_id": "north_gate_cam1"}) == "north_gate"
    assert outfit_service._source_segment_key({"camera_id": "library-floor2-c3"}) == "library-floor2"
    assert outfit_service._source_segment_key({"camera_id": "cam02"}) == "cam02"


def test_merge_source_groups_requires_different_sources_same_pure_color_and_close_features():
    left = [
        _item("event_1", "p1", "black", _unit([1.0, 0.0, 0.0])),
        _item("event_2", "p1", "black", _unit([0.99, 0.01, 0.0])),
    ]
    right = [
        _item("event_3", "p2", "black", _unit([0.99, 0.02, 0.0])),
        _item("event_4", "p2", "black", _unit([0.98, 0.02, 0.0])),
    ]

    merged = outfit_service._merge_source_compatible_groups([left, right])

    assert len(merged) == 1
    assert {item["event"]["event_id"] for item in merged[0]} == {"event_1", "event_2", "event_3", "event_4"}


def test_merge_source_groups_keeps_mixed_color_sources_separate():
    left = [
        _item("event_1", "p1", "black", _unit([1.0, 0.0, 0.0])),
        _item("event_2", "p1", "black", _unit([0.99, 0.01, 0.0])),
    ]
    right = [
        _item("event_3", "p2", "black", _unit([0.99, 0.02, 0.0])),
        _item("event_4", "p2", "white", _unit([0.98, 0.02, 0.0])),
    ]

    merged = outfit_service._merge_source_compatible_groups([left, right])

    assert len(merged) == 2


def test_outfit_upper_color_resolver_guards_dark_purple_cast():
    color, reason = outfit_service._resolve_outfit_upper_color(
        Counter({"purple": 1, "black": 1}),
        [],
        average_confidence=0.47,
        max_striped_score=0.15,
    )

    assert color == "black"
    assert reason["action"] == "override_dark_purple_cast"


def test_outfit_upper_color_resolver_uses_white_for_gray_tie():
    color, reason = outfit_service._resolve_outfit_upper_color(
        Counter({"gray": 2, "white": 2}),
        [],
        average_confidence=0.52,
        max_striped_score=0.23,
    )

    assert color == "white"
    assert reason["action"] == "override_gray_white_tie"


def test_outfit_upper_color_resolver_keeps_striped_when_stripe_evidence_is_high():
    color, reason = outfit_service._resolve_outfit_upper_color(
        Counter({"gray": 7, "striped": 2}),
        [],
        average_confidence=0.42,
        max_striped_score=0.62,
    )

    assert color == "striped"
    assert reason["action"] == "override_gray_high_stripe_evidence"


def test_outfit_upper_color_resolver_rejects_low_evidence_striped():
    color, reason = outfit_service._resolve_outfit_upper_color(
        Counter({"striped": 2, "gray": 1}),
        [
            {"upper_color_confidence": 0.5, "upper_color_probs": {"gray": 0.31, "striped": 0.30}},
            {"upper_color_confidence": 0.5, "upper_color_probs": {"gray": 0.30, "striped": 0.30}},
        ],
        average_confidence=0.56,
        max_striped_score=0.29,
    )

    assert color == "gray"
    assert reason["action"] == "override_low_stripe_gray_evidence"


def test_outfit_upper_color_resolver_handles_low_confidence_blue_purple_tie():
    color, reason = outfit_service._resolve_outfit_upper_color(
        Counter({"blue": 2, "purple": 2, "striped": 1}),
        [],
        average_confidence=0.28,
        max_striped_score=0.34,
    )

    assert color == "purple"
    assert reason["action"] == "override_low_confidence_blue_purple_tie"
