from fastapi import APIRouter, HTTPException

from app.services.event_service import get_event_related_records


router = APIRouter(prefix="/events", tags=["events"])


@router.get("/{event_id}/related-records")
def event_related_records(event_id: str) -> dict:
    records = get_event_related_records(event_id)
    if not records:
        raise HTTPException(status_code=404, detail={"code": "EVENT_NOT_FOUND", "message": event_id})
    return records
