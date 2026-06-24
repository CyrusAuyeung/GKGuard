from app.services import glasses_status_service


def test_glasses_status_profile_evaluation_reports_targets(monkeypatch, tmp_path):
    label_path = tmp_path / "person_glasses_labels.json"
    label_path.write_text(
        """
        {
          "labels": {
            "person_1": {
              "glasses_status": "glasses",
              "event_glasses_labels": [
                {"event_id": "event_1", "glasses_status": "glasses"}
              ]
            },
            "person_2": {
              "glasses_status": "no_glasses",
              "event_glasses_labels": [
                {"event_id": "event_2", "glasses_status": "no_glasses"}
              ]
            }
          }
        }
        """,
        encoding="utf-8",
    )
    monkeypatch.setattr(glasses_status_service, "MANUAL_EVAL_LABEL_PATH", label_path)
    monkeypatch.setattr(
        glasses_status_service,
        "_person_status_lookup",
        lambda: {"person_1": "stable", "person_2": "candidate"},
    )
    monkeypatch.setattr(
        glasses_status_service,
        "_event_coverage",
        lambda: {
            "total_events": 2,
            "identified_events": 2,
            "anonymous_events": 0,
            "identified_event_rate": 1.0,
            "note": "",
        },
    )

    report = glasses_status_service.evaluate_profiles(
        {
            "profiles": {
                "person_1": {"glasses_status": "glasses", "sample_consistency": 1.0},
                "person_2": {"glasses_status": "no_glasses", "sample_consistency": 1.0},
            },
            "event_profiles": {
                "event_1": {
                    "event_id": "event_1",
                    "person_id": "person_1",
                    "glasses_status": "glasses",
                },
                "event_2": {
                    "event_id": "event_2",
                    "person_id": "person_2",
                    "glasses_status": "no_glasses",
                },
            },
        }
    )

    assert report["eval_only"] is True
    assert report["person_accuracy"] == 1.0
    assert report["person_macro_f1_observed_classes"] == 1.0
    assert report["identified_event_accuracy"] == 1.0
    assert report["same_person_event_consistency"] == 1.0
    assert report["targets"]["person_accuracy"]["passed"] is True
    assert report["targets"]["unknown_recall"]["passed"] is None
