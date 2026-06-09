from fastapi import APIRouter, HTTPException

from app.models import EventDispositionRequest, EventDispositionResponse
from app.services.event_service import archive_event_disposition, build_event_report, get_event_related_records


router = APIRouter(prefix="/events", tags=["events"])


@router.get("/{event_id}/related-records")
def event_related_records(event_id: str) -> dict:
    records = get_event_related_records(event_id)
    if not records:
        raise HTTPException(status_code=404, detail={"code": "EVENT_NOT_FOUND", "message": event_id})
    return records


@router.get("/{event_id}/report")
def event_report(event_id: str) -> dict:
    report = build_event_report(event_id)
    if not report:
        raise HTTPException(status_code=404, detail={"code": "EVENT_NOT_FOUND", "message": event_id})
    return report


@router.post("/{event_id}/disposition", response_model=EventDispositionResponse)
def event_disposition(event_id: str, request: EventDispositionRequest) -> EventDispositionResponse:
    disposition = archive_event_disposition(event_id, request)
    if not disposition:
        raise HTTPException(status_code=404, detail={"code": "EVENT_NOT_FOUND", "message": event_id})
    return disposition
