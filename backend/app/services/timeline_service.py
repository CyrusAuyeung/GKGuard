from __future__ import annotations

from datetime import datetime
from typing import Any

from app.data_store import load_data
from app.services.search_service import search_snapshots


def _minutes_between(start: str | None, end: str | None) -> int | None:
    if not start or not end:
        return None
    start_dt = datetime.fromisoformat(start)
    end_dt = datetime.fromisoformat(end)
    return int((end_dt - start_dt).total_seconds() // 60)


def build_person_timeline(
    person_id: str,
    start_time: str | None = None,
    end_time: str | None = None,
    min_similarity: float | None = None,
) -> dict[str, Any] | None:
    persons = load_data()["persons"]
    if not any(person["person_id"] == person_id for person in persons):
        return None
    snapshots = search_snapshots(
        person_id=person_id,
        start_time=start_time,
        end_time=end_time,
        min_similarity=min_similarity,
    )
    points = [
        {
            "time": snapshot["time"],
            "location": snapshot["location"],
            "camera_id": snapshot["camera_id"],
            "camera_name": snapshot["camera_name"],
            "lat": snapshot["lat"],
            "lng": snapshot["lng"],
            "image_url": snapshot["image_url"],
            "similarity": snapshot.get("mock_similarity"),
            "source_type": "snapshot",
            "source_id": snapshot["snapshot_id"],
        }
        for snapshot in snapshots
    ]
    alerts = [alert for alert in load_data()["alerts"] if alert.get("person_id") == person_id]
    first_seen = points[0]["time"] if points else None
    last_seen = points[-1]["time"] if points else None
    summary = {
        "first_seen": first_seen,
        "last_seen": last_seen,
        "last_location": points[-1]["location"] if points else None,
        "point_count": len(points),
        "camera_count": len({point["camera_id"] for point in points}),
        "related_alert_count": len(alerts),
        "duration_minutes": _minutes_between(first_seen, last_seen),
    }
    return {"person_id": person_id, "summary": summary, "points": points}


def summarize_timeline(timeline: dict[str, Any]) -> str:
    summary = timeline["summary"]
    if summary["point_count"] == 0:
        return "No campus appearance records found in the selected range."
    return (
        f"Found {summary['point_count']} appearance records across "
        f"{summary['camera_count']} cameras. Last seen at {summary['last_location']} "
        f"at {summary['last_seen']}."
    )
