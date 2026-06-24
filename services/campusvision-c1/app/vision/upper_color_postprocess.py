from __future__ import annotations

from typing import Mapping


def choose_upper_color_from_probs(probabilities: Mapping[str, float]) -> str:
    """Pick an upper-clothing color from low-confidence CLIP probabilities."""
    probs = {
        str(color): max(0.0, float(value or 0.0))
        for color, value in probabilities.items()
    }
    if not probs:
        return "unknown"

    top_color, top_probability = max(probs.items(), key=lambda item: item[1])
    if top_probability <= 0.0:
        return "unknown"

    if (
        top_color == "gray"
        and top_probability < 0.16
        and probs.get("striped", 0.0) >= top_probability - 0.03
    ):
        return "striped"

    if top_color in {"blue", "purple"} and top_probability < 0.14:
        neutral = max(("gray", "white", "black"), key=lambda color: probs.get(color, 0.0))
        if probs.get(neutral, 0.0) >= top_probability - 0.015:
            return neutral

    if (
        top_color in {"red", "pink", "purple"}
        and top_probability < 0.14
        and probs.get("black", 0.0) >= top_probability - 0.03
    ):
        return "black"

    return top_color
