import asyncio

from app.api import routes


class _JsonRequest:
    def __init__(self, payload):
        self._payload = payload

    async def json(self):
        return self._payload


def test_person_glasses_labels_propagate_to_person_events(monkeypatch, tmp_path):
    label_dir = tmp_path / "manual_person_glasses_labels"
    label_path = label_dir / "person_glasses_labels.json"
    monkeypatch.setattr(routes, "_MANUAL_PERSON_GLASSES_LABEL_DIR", label_dir)
    monkeypatch.setattr(routes, "_MANUAL_PERSON_GLASSES_LABEL_PATH", label_path)
    monkeypatch.setattr(
        routes.person_service,
        "list_persons",
        lambda include_candidates=False: [
            {"person_id": "stable_person", "identity_status": "stable"},
            {"person_id": "candidate_person", "identity_status": "candidate"},
        ]
        if include_candidates
        else [{"person_id": "stable_person", "identity_status": "stable"}],
    )
    monkeypatch.setattr(
        routes.db,
        "list_events",
        lambda **kwargs: [
            {
                "event_id": "event_1",
                "person_id": kwargs.get("person_id"),
                "camera_id": "cam_1",
                "video_id": "video_1",
                "start_time": "2026-06-24T00:00:00Z",
                "end_time": "2026-06-24T00:00:03Z",
                "representative_observation_id": "obs_1",
                "representative_face_id": "face_1",
            },
            {
                "event_id": "event_2",
                "person_id": kwargs.get("person_id"),
                "camera_id": "cam_2",
                "video_id": "video_2",
                "start_time": "2026-06-24T00:01:00Z",
                "end_time": "2026-06-24T00:01:03Z",
                "representative_observation_id": "obs_2",
                "representative_face_id": "face_2",
            },
        ],
    )
    monkeypatch.setattr(routes, "_snapshot_manual_samples", lambda *_args, **_kwargs: [])

    response = asyncio.run(
        routes.save_manual_person_glasses_labels(
            _JsonRequest(
                {
                    "labels": [
                        {
                            "person_id": "candidate_person",
                            "glasses_status": "glasses",
                            "evidence_quality": "clear",
                            "review_status": "confirmed",
                            "sample_event_ids": ["event_1"],
                            "sample_observation_ids": ["obs_1"],
                        }
                    ]
                }
            )
        )
    )

    assert response["saved"] == 1
    assert response["propagated_events"] == 2
    saved = routes._load_manual_person_glasses_labels()
    label = saved["labels"]["candidate_person"]
    assert label["glasses_status"] == "glasses"
    assert label["event_count"] == 2
    assert [event["event_id"] for event in label["event_glasses_labels"]] == ["event_1", "event_2"]
    assert {event["glasses_status"] for event in label["event_glasses_labels"]} == {"glasses"}
    assert {event["propagation_source"] for event in label["event_glasses_labels"]} == {"manual_person_level"}
