from app.api import routes


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
