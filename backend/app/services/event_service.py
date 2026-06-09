from __future__ import annotations

from typing import Any
from datetime import datetime

from app.data_store import load_data
from app.models import EventDispositionRequest, EventDispositionResponse
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


def build_event_report(event_id: str) -> dict[str, Any] | None:
    records = get_event_related_records(event_id)
    if not records:
        return None

    event = records["event"]
    timeline = records.get("timeline")
    snapshots = records["related_snapshots"]
    summary = timeline["summary"] if timeline else {}
    last_location = summary.get("last_location") or event["location"]
    first_seen = summary.get("first_seen") or event["time"]
    last_seen = summary.get("last_seen") or event["time"]
    status = event["status"]

    recommendations = [
        "Review the timeline points and source camera snapshots.",
        f"Prioritize field review around {last_location}.",
    ]
    if status == "open":
        recommendations.append("Create or continue a campusCar field-review task before closing the event.")
    if event["severity"] == "high":
        recommendations.append("Escalate to the duty officer if the subject is not confirmed on site.")

    return {
        "report_id": f"RPT-{event_id}",
        "event_id": event_id,
        "title": f"Case report for {event['alert_type']}",
        "status": status,
        "severity": event["severity"],
        "subject": {
            "person_id": event.get("person_id"),
            "vehicle_id": event.get("vehicle_id"),
        },
        "key_findings": [
            records["summary"],
            f"First related record: {first_seen}.",
            f"Last related record: {last_seen} at {last_location}.",
            f"Related snapshot count: {len(snapshots)}.",
        ],
        "recommended_actions": recommendations,
        "evidence": {
            "snapshot_ids": [snapshot["snapshot_id"] for snapshot in snapshots],
            "camera_ids": sorted({snapshot["camera_id"] for snapshot in snapshots}),
            "timeline_point_count": summary.get("point_count", 0),
            "last_location": last_location,
        },
        "disposition_template": {
            "result": "pending_confirmation",
            "handler": "security_desk_demo",
            "notes": "Replace this template with the duty officer's final handling result.",
        },
    }


def archive_event_disposition(event_id: str, request: EventDispositionRequest) -> EventDispositionResponse | None:
    report = build_event_report(event_id)
    if not report:
        return None

    archived_at = datetime.now().replace(microsecond=0).isoformat()
    return EventDispositionResponse(
        disposition_id=f"DSP-{event_id}",
        event_id=event_id,
        status_before=report["status"],
        status_after="closed",
        result=request.result,
        handler=request.handler,
        notes=request.notes,
        archived_at=archived_at,
        evidence_summary={
            "report_id": report["report_id"],
            "snapshot_count": len(report["evidence"]["snapshot_ids"]),
            "camera_count": len(report["evidence"]["camera_ids"]),
            "last_location": report["evidence"]["last_location"],
            "recommended_action_count": len(report["recommended_actions"]),
        },
    )
