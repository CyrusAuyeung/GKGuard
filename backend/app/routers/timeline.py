from fastapi import APIRouter, HTTPException

from app.services.timeline_service import build_person_timeline, summarize_timeline


router = APIRouter(prefix="/persons", tags=["timeline"])


@router.get("/{person_id}/timeline")
def get_timeline(
    person_id: str,
    start_time: str | None = None,
    end_time: str | None = None,
    min_similarity: float | None = None,
) -> dict:
    timeline = build_person_timeline(person_id, start_time, end_time, min_similarity)
    if not timeline:
        raise HTTPException(status_code=404, detail={"code": "PERSON_NOT_FOUND", "message": person_id})
    return timeline | {"text_summary": summarize_timeline(timeline)}
