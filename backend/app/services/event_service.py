from __future__ import annotations

from typing import Any

from app.data_store import load_data
from app.services.search_service import search_snapshots
from app.services.timeline_service import build_person_timeline, summarize_timeline


def get_event_related_records(event_id: str) -> dict[str, Any] | None:
    data = load_data()
    event = next((item for item in data["alerts"] if item["alert_id"] == event_id), None)
    if not event:
        return None
    snapshots = []
    if event.get("person_id"):
        snapshots = search_snapshots(person_id=event["person_id"])
    elif event.get("vehicle_id"):
        snapshots = search_snapshots(vehicle_id=event["vehicle_id"])
    timeline = build_person_timeline(event["person_id"]) if event.get("person_id") else None
    return {
        "event": event,
        "related_snapshots": snapshots,
        "timeline": timeline,
        "summary": summarize_timeline(timeline) if timeline else "Vehicle event linked to patrol and snapshot records.",
    }
