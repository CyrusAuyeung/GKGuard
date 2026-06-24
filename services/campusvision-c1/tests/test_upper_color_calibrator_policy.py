from pathlib import Path
import json
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.vision import upper_color_calibrator  # noqa: E402
from scripts import train_upper_color_calibrator  # noqa: E402


def _model(**updates):
    data = {
        "model_version": upper_color_calibrator.MODEL_VERSION,
        "deployment_allowed": True,
        "training_source": "synthetic_non_manual_training",
        "labels": ["black"],
        "feature_vectors": [[0.0, 1.0]],
        "feature_mean": [0.0, 0.0],
        "feature_scale": [1.0, 1.0],
    }
    data.update(updates)
    return data


def test_upper_color_calibrator_rejects_models_without_deployment_provenance(tmp_path):
    model_path = tmp_path / "model.json"
    model_path.write_text(
        json.dumps(_model(deployment_allowed=None)),
        encoding="utf-8",
    )

    assert upper_color_calibrator.load_model(model_path) is None


def test_upper_color_calibrator_rejects_manual_eval_models(tmp_path):
    model_path = tmp_path / "model.json"
    model_path.write_text(
        json.dumps(
            _model(
                deployment_allowed=True,
                training_source="manual_upper_color_eval_labels",
                eval_only=True,
            )
        ),
        encoding="utf-8",
    )

    assert upper_color_calibrator.load_model(model_path) is None


def test_upper_color_calibrator_accepts_explicit_deployable_non_manual_model(tmp_path):
    model_path = tmp_path / "model.json"
    model_path.write_text(json.dumps(_model()), encoding="utf-8")

    assert upper_color_calibrator.load_model(model_path) is not None


def test_manual_upper_color_training_script_is_disabled(tmp_path):
    with pytest.raises(RuntimeError, match="eval-only"):
        train_upper_color_calibrator.train_and_evaluate(
            label_path=tmp_path / "labels.json",
            model_path=tmp_path / "model.json",
            report_path=tmp_path / "report.json",
            k=1,
            allow_face_estimated=True,
            write_model=False,
        )
