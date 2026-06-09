from __future__ import annotations

from typing import Any


LOCATION_KEYWORDS = {
    "dorm": "Dorm East Gate",
    "library": "Library West",
    "canteen": "Canteen Entrance",
    "lab": "Lab Building South",
    "clinic": "Clinic Door",
    "parking": "Parking Lot East",
    "gate": "Main Gate North",
}

COLOR_KEYWORDS = {"white", "black", "red", "silver", "blue", "gray"}
OBJECT_KEYWORDS = {
    "person": "person",
    "student": "person",
    "faculty": "person",
    "visitor": "person",
    "vehicle": "vehicle",
    "car": "vehicle",
    "sedan": "vehicle",
    "suv": "vehicle",
    "van": "vehicle",
}


def parse_natural_query(query: str) -> dict[str, Any]:
    normalized = query.lower()
    filters: dict[str, Any] = {}
    matched_terms: list[str] = []

    for keyword, location in LOCATION_KEYWORDS.items():
        if keyword in normalized:
            filters["location"] = location
            matched_terms.append(keyword)
            break

    for color in COLOR_KEYWORDS:
        if color in normalized:
            filters["color"] = color
            matched_terms.append(color)
            break

    for keyword, object_type in OBJECT_KEYWORDS.items():
        if keyword in normalized:
            filters["object_type"] = object_type
            matched_terms.append(keyword)
            break

    if "night" in normalized or "after hours" in normalized:
        filters["time_hint"] = "after_hours"
        matched_terms.append("night")
    elif "today" in normalized:
        filters["time_hint"] = "today"
        matched_terms.append("today")

    return {
        "query": query,
        "filters": filters,
        "matched_terms": matched_terms,
        "confidence": 0.65 if filters else 0.2,
        "note": "Rule-based parser for the C2 demo; replace with an LLM parser later if needed.",
    }
