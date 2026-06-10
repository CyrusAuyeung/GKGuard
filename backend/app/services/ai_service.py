from __future__ import annotations

from typing import Any


LOCATION_KEYWORDS = {
    "dorm": "Dorm East Gate",
    "宿舍": "Dorm East Gate",
    "library": "Library West",
    "图书馆": "Library West",
    "canteen": "Canteen Entrance",
    "食堂": "Canteen Entrance",
    "lab": "Lab Building South",
    "实验楼": "Lab Building South",
    "clinic": "Clinic Door",
    "医务室": "Clinic Door",
    "parking": "Parking Lot East",
    "停车场": "Parking Lot East",
    "gate": "Main Gate North",
    "校门": "Main Gate North",
}

COLOR_KEYWORDS = {
    "white": "white",
    "白色": "white",
    "black": "black",
    "黑色": "black",
    "red": "red",
    "红色": "red",
    "silver": "silver",
    "银色": "silver",
    "blue": "blue",
    "蓝色": "blue",
    "gray": "gray",
    "灰色": "gray",
}
OBJECT_KEYWORDS = {
    "person": "person",
    "人员": "person",
    "人": "person",
    "student": "person",
    "学生": "person",
    "faculty": "person",
    "教职工": "person",
    "visitor": "person",
    "访客": "person",
    "vehicle": "vehicle",
    "车辆": "vehicle",
    "car": "vehicle",
    "车": "vehicle",
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

    for keyword, color in COLOR_KEYWORDS.items():
        if color in normalized:
            filters["color"] = color
            matched_terms.append(keyword)
            break
        if keyword in normalized:
            filters["color"] = color
            matched_terms.append(keyword)
            break

    for keyword, object_type in OBJECT_KEYWORDS.items():
        if keyword in normalized:
            filters["object_type"] = object_type
            matched_terms.append(keyword)
            break

    if "night" in normalized or "after hours" in normalized or "夜间" in normalized or "晚上" in normalized:
        filters["time_hint"] = "after_hours"
        matched_terms.append("night" if "night" in normalized else "夜间")
    elif "today" in normalized or "今天" in normalized:
        filters["time_hint"] = "today"
        matched_terms.append("today" if "today" in normalized else "今天")

    return {
        "query": query,
        "filters": filters,
        "matched_terms": matched_terms,
        "confidence": 0.65 if filters else 0.2,
        "note": "Rule-based parser for the C2 demo; replace with an LLM parser later if needed.",
    }
