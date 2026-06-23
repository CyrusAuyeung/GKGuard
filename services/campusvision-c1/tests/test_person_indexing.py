from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services import person_service  # noqa: E402
from app.services import person_merge_scorer  # noqa: E402
from app.schemas import AppearanceSessionOut, EventOut, PersonEventOut, PersonObservationOut  # noqa: E402


def _face(face_id: str, embedding: list[float], timestamp: float) -> dict:
    return {
        "face_id": face_id,
        "video_id": "video_1",
        "camera_id": "cam_1",
        "frame_path": "/tmp/frame.jpg",
        "video_timestamp_sec": timestamp,
        "captured_at": f"2026-06-22T00:00:{int(timestamp):02d}Z",
        "bbox": {"x1": 0, "y1": 0, "x2": 80, "y2": 80, "score": 0.95},
        "embedding": embedding,
    }


def test_select_clusters_with_guards_rejects_conflicts_and_weak_clusters():
    good = person_service._make_cluster(
        [
            _face("good_1", [1.0, 0.0, 0.0], 1.0),
            _face("good_2", [0.98, 0.02, 0.0], 2.0),
        ]
    )
    same_frame_conflict = person_service._make_cluster(
        [
            _face("conflict_1", [1.0, 0.0, 0.0], 3.0),
            _face("conflict_2", [0.99, 0.01, 0.0], 3.0),
        ]
    )
    weak = person_service._make_cluster(
        [
            _face("weak_1", [1.0, 0.0, 0.0], 4.0),
            _face("weak_2", [0.0, 1.0, 0.0], 5.0),
        ]
    )

    selected, skipped = person_service._select_clusters_with_guards(
        [good, same_frame_conflict, weak],
        min_faces=2,
        min_cluster_mean_similarity=0.76,
    )

    assert selected == [good]
    assert skipped["same_frame_conflict_clusters"] == 1
    assert skipped["low_intra_similarity_clusters"] == 1


def test_best_existing_person_match_uses_strict_threshold(monkeypatch):
    monkeypatch.setattr(person_service.db, "list_face_records_for_person", lambda person_id: [])
    cluster = person_service._make_cluster(
        [
            _face("query_1", [1.0, 0.0, 0.0], 1.0),
            _face("query_2", [0.99, 0.01, 0.0], 2.0),
        ]
    )
    persons = [
        {"person_id": "loose", "embedding": [0.74, 0.67, 0.0]},
        {"person_id": "strict", "embedding": [0.99, 0.01, 0.0]},
    ]

    assert person_service._best_existing_person_match(cluster, persons, threshold=0.82)["person_id"] == "strict"
    assert person_service._best_existing_person_match(cluster, persons[:1], threshold=0.82) is None


def test_auto_fragment_merge_guards_keep_low_threshold_safe():
    base = {
        "same_frame_conflict": False,
        "strong_clothing_conflict": False,
        "centroid_similarity": 0.65,
        "max_pair_similarity": 0.56,
        "nearest_margin": 0.36,
    }

    passed, reason = person_service._passes_auto_fragment_merge_guards(
        base,
        min_centroid_similarity=0.64,
        min_max_pair_similarity=0.55,
        min_nearest_margin=0.35,
    )
    assert passed is True
    assert reason == "passed"

    clothing_conflict = dict(base)
    clothing_conflict["strong_clothing_conflict"] = True
    passed, reason = person_service._passes_auto_fragment_merge_guards(
        clothing_conflict,
        min_centroid_similarity=0.64,
        min_max_pair_similarity=0.55,
        min_nearest_margin=0.35,
    )
    assert passed is True
    assert reason == "passed"
    passed, reason = person_service._passes_auto_fragment_merge_guards(
        clothing_conflict,
        min_centroid_similarity=0.64,
        min_max_pair_similarity=0.55,
        min_nearest_margin=0.35,
        use_clothing_conflict_guard=True,
    )
    assert passed is False
    assert reason == "strong_clothing_conflict"

    for key, value, expected_reason in [
        ("same_frame_conflict", True, "same_frame_conflict"),
        ("centroid_similarity", 0.63, "low_centroid_similarity"),
        ("max_pair_similarity", 0.54, "low_max_pair_similarity"),
        ("nearest_margin", 0.34, "low_nearest_margin"),
    ]:
        metrics = dict(base)
        metrics[key] = value
        passed, reason = person_service._passes_auto_fragment_merge_guards(
            metrics,
            min_centroid_similarity=0.64,
            min_max_pair_similarity=0.55,
            min_nearest_margin=0.35,
        )
        assert passed is False
        assert reason == expected_reason


def test_auto_consolidate_can_scan_all_small_persons(monkeypatch):
    persons = [
        {"person_id": "small_blank", "display_name": None, "face_count": 2, "embedding": [1.0, 0.0]},
        {"person_id": "candidate_small", "display_name": "candidate_x", "face_count": 3, "embedding": [1.0, 0.0]},
        {"person_id": "stable_blank", "display_name": None, "face_count": 8, "embedding": [1.0, 0.0]},
    ]
    metrics = {
        "source_person_id": "small_blank",
        "target_person_id": "stable_blank",
        "centroid_similarity": 0.8,
        "max_pair_similarity": 0.7,
        "top5_pair_similarity": 0.68,
        "nearest_margin": 0.4,
        "same_frame_conflict": False,
        "strong_clothing_conflict": True,
    }

    monkeypatch.setattr(person_service.db, "list_persons", lambda: persons)
    monkeypatch.setattr(
        person_service,
        "_best_fragment_target",
        lambda source, targets, **_kwargs: (targets[0], metrics | {"source_person_id": source["person_id"]}),
    )
    monkeypatch.setattr(
        person_service,
        "merge_person_into",
        lambda **kwargs: {
            "source_person_id": kwargs["source_person_id"],
            "target_person_id": kwargs["target_person_id"],
            "moved_faces": 2,
            "video_ids": [],
            "metrics": metrics,
        },
    )

    result = person_service.auto_consolidate_person_fragments(
        include_all_small_sources=True,
        max_source_faces=3,
        min_target_faces=5,
        dry_run=True,
    )

    assert result["source_candidates"] == 2
    assert result["target_candidates"] == 1
    assert result["merge_count"] == 2
    assert result["skip_count"] == 0


def test_person_merge_scorer_predicts_probability_from_serialized_model():
    model = {
        "model_version": person_merge_scorer.MODEL_VERSION,
        "feature_names": person_merge_scorer.FEATURE_NAMES,
        "threshold": 0.5,
        "scaler_mean": [0.0 for _ in person_merge_scorer.FEATURE_NAMES],
        "scaler_scale": [1.0 for _ in person_merge_scorer.FEATURE_NAMES],
        "coef": [1.0 if name == "centroid_similarity" else 0.0 for name in person_merge_scorer.FEATURE_NAMES],
        "intercept": 0.0,
    }
    features = {name: 0.0 for name in person_merge_scorer.FEATURE_NAMES}
    features["centroid_similarity"] = 2.0

    probability = person_merge_scorer.predict_probability(model, features)

    assert 0.88 < probability < 0.89


def test_merge_scorer_guard_requires_probability():
    base = {
        "same_frame_conflict": False,
        "strong_clothing_conflict": False,
        "centroid_similarity": 0.65,
        "max_pair_similarity": 0.56,
        "nearest_margin": 0.36,
        "merge_probability": 0.84,
    }

    passed, reason = person_service._passes_auto_fragment_merge_guards(
        base,
        min_centroid_similarity=0.64,
        min_max_pair_similarity=0.55,
        min_nearest_margin=0.35,
        min_merge_probability=0.85,
    )

    assert passed is False
    assert reason == "low_merge_probability"


def test_list_persons_filters_candidate_identities_by_default(monkeypatch):
    persons = [
        {
            "person_id": "stable",
            "face_count": 10,
            "embedding": [1.0, 0.0],
            "representative_face_id": "face_stable",
        },
        {
            "person_id": "candidate",
            "face_count": 2,
            "embedding": [0.0, 1.0],
            "representative_face_id": "face_candidate",
        },
    ]
    monkeypatch.setattr(person_service.settings, "person_identity_stable_min_faces", 10)
    monkeypatch.setattr(person_service.db, "list_persons", lambda: [dict(person) for person in persons])
    monkeypatch.setattr(person_service.db, "list_events", lambda **_kwargs: [])
    monkeypatch.setattr(person_service, "person_events", lambda *_args, **_kwargs: [])

    stable_only = person_service.list_persons()
    all_people = person_service.list_persons(include_candidates=True)

    assert [person["person_id"] for person in stable_only] == ["stable"]
    assert stable_only[0]["identity_status"] == "stable"
    assert [person["identity_status"] for person in all_people] == ["stable", "candidate"]


def test_list_persons_attaches_cached_gender_presentation_profile(monkeypatch):
    persons = [
        {
            "person_id": "stable",
            "face_count": 10,
            "embedding": [1.0, 0.0],
            "representative_face_id": "face_stable",
        },
    ]
    monkeypatch.setattr(person_service.settings, "person_identity_stable_min_faces", 10)
    monkeypatch.setattr(person_service.db, "list_persons", lambda: [dict(person) for person in persons])
    monkeypatch.setattr(person_service.db, "list_events", lambda **_kwargs: [])
    monkeypatch.setattr(person_service, "person_events", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        person_service.gender_presentation_service,
        "load_profiles",
        lambda: {
            "profiles": {
                "stable": {
                    "gender_presentation": "masculine",
                    "gender_presentation_label": "偏男性",
                    "confidence": 0.91,
                    "evidence_quality": "partial",
                }
            }
        },
    )

    result = person_service.list_persons()

    assert result[0]["gender_presentation"] == "masculine"
    assert result[0]["gender_presentation_label"] == "偏男性"
    assert result[0]["gender_presentation_confidence"] == 0.91
    assert result[0]["gender_presentation_profile"]["evidence_quality"] == "partial"


def test_list_persons_attaches_cached_glasses_profiles_to_person_and_events(monkeypatch):
    persons = [
        {
            "person_id": "stable",
            "face_count": 10,
            "embedding": [1.0, 0.0],
            "representative_face_id": "face_stable",
        },
    ]
    events = [
        {
            "event_id": "event_1",
            "person_id": "stable",
            "camera_id": "cam_1",
            "observation_count": 1,
            "face_count": 1,
            "representative_face_id": "face_stable",
        }
    ]
    monkeypatch.setattr(person_service.settings, "person_identity_stable_min_faces", 10)
    monkeypatch.setattr(person_service.db, "list_persons", lambda: [dict(person) for person in persons])
    monkeypatch.setattr(person_service.db, "list_events", lambda **_kwargs: [dict(event) for event in events])
    monkeypatch.setattr(
        person_service.gender_presentation_service,
        "load_profiles",
        lambda: {"profiles": {}},
    )
    monkeypatch.setattr(
        person_service.glasses_status_service,
        "load_profiles",
        lambda: {
            "profiles": {
                "stable": {
                    "glasses_status": "glasses",
                    "glasses_status_label": "戴眼镜",
                    "confidence": 0.91,
                    "evidence_quality": "clear",
                }
            },
            "event_profiles": {
                "event_1": {
                    "glasses_status": "glasses",
                    "glasses_status_label": "戴眼镜",
                    "glasses_confidence": 0.91,
                    "glasses_evidence_quality": "clear",
                    "glasses_model_version": "test",
                }
            },
        },
    )

    result = person_service.list_persons()

    assert result[0]["glasses_status"] == "glasses"
    assert result[0]["glasses_status_label"] == "戴眼镜"
    assert result[0]["glasses_status_confidence"] == 0.91
    assert result[0]["events"][0]["glasses_status"] == "glasses"
    assert result[0]["events"][0]["glasses_model_version"] == "test"


def test_public_schemas_do_not_expose_lower_clothing_fields():
    payloads = [
        EventOut.model_validate(
            {
                "event_id": "event_1",
                "camera_id": "cam_1",
                "observation_count": 1,
                "face_count": 1,
                "lower_color": "blue",
                "lower_color_confidence": 0.9,
                "lower_visible": True,
                "raw_lower_color": "blue",
                "raw_lower_color_confidence": 0.9,
                "raw_lower_visible": True,
                "normalized_lower_color": "blue",
                "normalized_lower_color_confidence": 0.9,
                "normalized_lower_visible": True,
            }
        ).model_dump(),
        PersonEventOut.model_validate(
            {
                "event_id": "event_1",
                "person_id": "person_1",
                "camera_id": "cam_1",
                "face_count": 1,
                "representative_face_id": "face_1",
                "representative_face_crop_url": "/api/v1/media/face/face_1",
                "representative_frame_url": "/api/v1/media/frame/face_1",
                "lower_color": "blue",
                "raw_lower_color": "blue",
                "normalized_lower_color": "blue",
            }
        ).model_dump(),
        PersonObservationOut.model_validate(
            {
                "observation_id": "obs_1",
                "camera_id": "cam_1",
                "frame_path": "/tmp/frame.jpg",
                "observation_type": "detected_person",
                "body_visibility": "full",
                "lower_color": "blue",
                "lower_color_confidence": 0.9,
                "lower_visible": True,
            }
        ).model_dump(),
        AppearanceSessionOut.model_validate(
            {
                "session_id": "session_1",
                "person_id": "person_1",
                "event_count": 1,
                "lower_color": "blue",
                "lower_color_confidence": 0.9,
                "lower_color_support": 1,
                "lower_visible": True,
            }
        ).model_dump(),
    ]

    for payload in payloads:
        assert not any(
            key.startswith("lower_")
            or key.startswith("raw_lower_")
            or key.startswith("normalized_lower_")
            for key in payload
        )


def test_person_public_event_payloads_do_not_expose_lower_clothing_fields():
    event = {
        "event_id": "event_1",
        "camera_id": "cam_1",
        "face_count": 1,
        "lower_color": "blue",
        "lower_color_confidence": 0.9,
        "lower_visible": True,
        "raw_lower_color": "blue",
        "raw_lower_color_confidence": 0.9,
        "raw_lower_visible": True,
        "normalized_lower_color": "blue",
        "normalized_lower_color_confidence": 0.9,
        "normalized_lower_visible": True,
    }

    person_event = person_service._persisted_event_for_person(event, "person_1")
    latest_clothing = person_service._latest_clothing(event)

    for payload in (person_event, latest_clothing):
        assert payload is not None
        assert not any(
            key.startswith("lower_")
            or key.startswith("raw_lower_")
            or key.startswith("normalized_lower_")
            for key in payload
        )
