from pathlib import Path
import sys
import importlib.util

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CV2_AVAILABLE = importlib.util.find_spec("cv2") is not None
pytestmark = pytest.mark.skipif(not CV2_AVAILABLE, reason="CampusVision C1 tests require opencv-python")

if CV2_AVAILABLE:
    from app.vision import person_analysis  # noqa: E402


def test_face_only_visibility_when_body_missing():
    image = np.zeros((120, 100, 3), dtype=np.uint8)
    face = {"x1": 35, "y1": 10, "x2": 65, "y2": 45, "score": 0.9}

    visibility = person_analysis.classify_body_visibility(image, None, face)
    clothing = person_analysis.analyze_clothing(image, None, visibility)

    assert visibility == "face_only"
    assert clothing["upper_visible"] is False
    assert clothing["lower_visible"] is False
    assert clothing["upper_color"] == "unknown"
    assert clothing["lower_color"] == "unknown"


def test_upper_body_does_not_force_lower_color():
    image = np.zeros((140, 100, 3), dtype=np.uint8)
    image[:, :] = (220, 0, 0)
    body = {"x1": 20, "y1": 10, "x2": 80, "y2": 100, "score": 0.8}
    face = {"x1": 35, "y1": 12, "x2": 65, "y2": 52, "score": 0.9}

    visibility = person_analysis.classify_body_visibility(image, body, face)
    clothing = person_analysis.analyze_clothing(image, body, visibility)

    assert visibility == "upper_body"
    assert clothing["upper_visible"] is True
    assert clothing["upper_color"] == "blue"
    assert clothing["lower_visible"] is False
    assert clothing["lower_color"] == "unknown"


def test_full_body_extracts_upper_and_lower_colors():
    image = np.zeros((220, 120, 3), dtype=np.uint8)
    image[40:112, 20:100] = (240, 240, 240)
    image[112:200, 20:100] = (220, 0, 0)
    body = {"x1": 20, "y1": 10, "x2": 100, "y2": 205, "score": 0.86}
    face = {"x1": 45, "y1": 16, "x2": 75, "y2": 46, "score": 0.92}

    visibility = person_analysis.classify_body_visibility(image, body, face)
    clothing = person_analysis.analyze_clothing(image, body, visibility)

    assert visibility == "full_body"
    assert clothing["upper_visible"] is True
    assert clothing["upper_color"] == "white"
    assert clothing["lower_visible"] is True
    assert clothing["lower_color"] == "blue"


def test_estimated_body_can_extract_lower_color_when_region_is_available():
    image = np.zeros((220, 120, 3), dtype=np.uint8)
    image[40:112, 20:100] = (240, 240, 240)
    image[112:200, 20:100] = (220, 0, 0)
    face = {"x1": 45, "y1": 16, "x2": 75, "y2": 46, "score": 0.92}
    body = person_analysis.estimate_body_bbox_from_face(face, image_width=120, image_height=220)

    visibility = person_analysis.classify_body_visibility(image, body, face)
    clothing = person_analysis.analyze_clothing(image, body, visibility)

    assert visibility == "upper_body"
    assert clothing["upper_visible"] is True
    assert clothing["lower_visible"] is True
    assert clothing["lower_color"] == "blue"


def test_bottom_truncated_body_does_not_extract_lower_color():
    image = np.zeros((220, 120, 3), dtype=np.uint8)
    image[40:112, 20:100] = (240, 240, 240)
    image[112:220, 20:100] = (220, 0, 0)
    body = {"x1": 20, "y1": 10, "x2": 100, "y2": 220, "score": 0.86}
    face = {"x1": 45, "y1": 16, "x2": 75, "y2": 46, "score": 0.92}

    visibility = person_analysis.classify_body_visibility(image, body, face)
    clothing = person_analysis.analyze_clothing(image, body, visibility)

    assert visibility == "upper_body"
    assert clothing["upper_visible"] is True
    assert clothing["lower_visible"] is False
    assert clothing["lower_color"] == "unknown"


def test_mixed_color_roi_without_dominant_color_is_unknown():
    roi = np.zeros((40, 100, 3), dtype=np.uint8)
    roi[:, :45] = (220, 0, 0)
    roi[:, 45:] = (0, 0, 220)

    result = person_analysis.classify_clothing_color(roi)

    assert result.visible is False
    assert result.color == "unknown"


def test_repeated_black_white_stripes_are_classified_as_striped():
    roi = np.zeros((60, 120, 3), dtype=np.uint8)
    for x in range(0, roi.shape[1], 8):
        roi[:, x : x + 4] = (245, 245, 245)
        roi[:, x + 4 : x + 8] = (20, 20, 20)

    result = person_analysis.classify_clothing_color(roi, part="upper")

    assert result.visible is True
    assert result.color == "striped"


def test_repeated_color_stripes_are_classified_as_striped():
    roi = np.zeros((72, 120, 3), dtype=np.uint8)
    for y in range(0, roi.shape[0], 8):
        roi[y : y + 4, :] = (220, 0, 0)
        roi[y + 4 : y + 8, :] = (0, 0, 220)

    result = person_analysis.classify_clothing_color(roi, part="upper")

    assert result.visible is True
    assert result.color == "striped"


@pytest.mark.parametrize(
    ("bgr", "expected"),
    [
        ((255, 255, 255), "white"),
        ((245, 235, 225), "white"),
        ((0, 0, 0), "black"),
        ((45, 28, 24), "black"),
        ((220, 0, 0), "blue"),
        ((90, 35, 20), "blue"),
    ],
)
def test_achromatic_colors_do_not_fall_through_to_blue(bgr, expected):
    roi = np.zeros((50, 80, 3), dtype=np.uint8)
    roi[:, :] = bgr

    result = person_analysis.classify_clothing_color(roi)

    assert result.visible is True
    assert result.color == expected


def test_upper_blue_cast_white_is_recovered():
    roi = np.zeros((50, 80, 3), dtype=np.uint8)
    roi[:, :] = (176, 143, 131)

    result = person_analysis.classify_clothing_color(roi, part="upper")

    assert result.visible is True
    assert result.color == "white"


def test_suspicious_upper_blue_confidence_is_capped():
    roi = np.zeros((50, 80, 3), dtype=np.uint8)
    roi[:, :] = (104, 77, 65)

    result = person_analysis.classify_clothing_color(roi, part="upper")

    assert result.visible is True
    assert result.color == "blue"
    assert result.confidence <= 0.42


def test_face_body_matching_keeps_unmatched_face_only_case():
    faces = [{"x1": 5, "y1": 5, "x2": 30, "y2": 35, "score": 0.9}]
    bodies = [{"x1": 50, "y1": 20, "x2": 95, "y2": 120, "score": 0.8}]

    result = person_analysis.match_faces_to_bodies(faces, bodies)

    assert result["pairs"] == []
    assert result["unmatched_face_indices"] == [0]
    assert result["unmatched_body_indices"] == [0]
