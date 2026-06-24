import asyncio

from app.api import routes
from app.services import gender_presentation_service


class _JsonRequest:
    def __init__(self, payload):
        self._payload = payload

    async def json(self):
        return self._payload


def test_gender_presentation_labels_are_eval_only(monkeypatch, tmp_path):
    label_dir = tmp_path / "manual_gender_presentation_labels"
    label_path = label_dir / "person_gender_presentation_labels.json"
    monkeypatch.setattr(routes, "_MANUAL_GENDER_PRESENTATION_LABEL_DIR", label_dir)
    monkeypatch.setattr(routes, "_MANUAL_GENDER_PRESENTATION_LABEL_PATH", label_path)

    empty = routes._load_manual_gender_presentation_labels()
    assert empty["schema_version"] == "manual_gender_presentation_labels_v1"
    assert empty["source"] == "manual_gender_presentation_review_eval"
    assert empty["eval_only"] is True
    assert empty["labels"] == {}

    empty["labels"]["person_1"] = {
        "person_id": "person_1",
        "gender_presentation": "neutral",
        "source": "wrong_source",
        "eval_only": False,
    }
    routes._save_manual_gender_presentation_labels(empty)

    saved = routes._load_manual_gender_presentation_labels()
    assert saved["source"] == "manual_gender_presentation_review_eval"
    assert saved["eval_only"] is True
    assert saved["labels"]["person_1"]["gender_presentation"] == "neutral"


def test_gender_presentation_labels_accept_candidate_people(monkeypatch, tmp_path):
    label_dir = tmp_path / "manual_gender_presentation_labels"
    label_path = label_dir / "person_gender_presentation_labels.json"
    monkeypatch.setattr(routes, "_MANUAL_GENDER_PRESENTATION_LABEL_DIR", label_dir)
    monkeypatch.setattr(routes, "_MANUAL_GENDER_PRESENTATION_LABEL_PATH", label_path)
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
    monkeypatch.setattr(routes, "_snapshot_manual_samples", lambda *_args, **_kwargs: [])

    response = asyncio.run(
        routes.save_manual_gender_presentation_labels(
            _JsonRequest(
                {
                    "labels": [
                        {
                            "person_id": "candidate_person",
                            "gender_presentation": "unknown",
                            "evidence_quality": "poor",
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
    saved = routes._load_manual_gender_presentation_labels()
    assert saved["labels"]["candidate_person"]["gender_presentation"] == "unknown"
    assert saved["labels"]["candidate_person"]["evidence_quality"] == "poor"


def test_gender_presentation_profile_evaluation_is_eval_only(monkeypatch, tmp_path):
    label_path = tmp_path / "manual_gender.json"
    label_path.write_text(
        """
        {
          "eval_only": true,
          "labels": {
            "person_1": {"gender_presentation": "masculine"},
            "person_2": {"gender_presentation": "feminine"}
          }
        }
        """,
        encoding="utf-8",
    )
    monkeypatch.setattr(gender_presentation_service, "MANUAL_EVAL_LABEL_PATH", label_path)
    monkeypatch.setattr(
        gender_presentation_service,
        "_person_status_lookup",
        lambda: {"person_1": "stable", "person_2": "candidate"},
    )

    report = gender_presentation_service.evaluate_profiles(
        {
            "profiles": {
                "person_1": {"gender_presentation": "masculine", "sample_predictions": []},
                "person_2": {"gender_presentation": "feminine", "sample_predictions": []},
            }
        }
    )

    assert report["eval_only"] is True
    assert report["accuracy"] == 1.0
    assert report["macro_f1_observed_classes"] == 1.0
    assert report["targets"]["person_accuracy"]["passed"] is True
    assert report["targets"]["unknown_recall"]["passed"] is None
