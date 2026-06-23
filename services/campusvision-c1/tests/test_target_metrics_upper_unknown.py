from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.evaluate_c1_target_metrics import _upper_unknown_false_metrics  # noqa: E402


def test_upper_unknown_false_metrics_counts_visible_manual_unknown_predictions():
    metrics = _upper_unknown_false_metrics(
        [
            {
                "person_id": "p1",
                "split_group": "A",
                "manual_upper_color": "black",
                "predicted_upper_color": "unknown",
            },
            {
                "person_id": "p2",
                "split_group": "A",
                "manual_upper_color": "white",
                "predicted_upper_color": "white",
            },
            {
                "person_id": "p3",
                "split_group": "A",
                "manual_upper_color": "unknown",
                "predicted_upper_color": "unknown",
            },
        ]
    )

    assert metrics["manual_visible_total"] == 2
    assert metrics["false_unknown_count"] == 1
    assert metrics["false_unknown_rate"] == 0.5
    assert metrics["unknown_prediction_count"] == 2
    assert metrics["unknown_prediction_rate"] == 0.666667
