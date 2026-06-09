from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.services.image_search_service import search_by_image
from app.services.search_service import get_person_profile, search_persons, search_snapshots, search_vehicles


router = APIRouter(prefix="/search", tags=["search"])


@router.get("/persons")
def find_persons(
    keyword: str | None = None,
    name: str | None = None,
    student_id: str | None = None,
    phone: str | None = None,
    email: str | None = None,
    identity_type: str | None = None,
) -> dict:
    return {
        "items": search_persons(keyword, name, student_id, phone, email, identity_type),
    }


@router.get("/persons/{person_id}/profile")
def find_person_profile(person_id: str) -> dict:
    profile = get_person_profile(person_id)
    if not profile:
        raise HTTPException(status_code=404, detail={"code": "PERSON_NOT_FOUND", "message": person_id})
    return profile


@router.get("/vehicles")
def find_vehicles(
    keyword: str | None = None,
    plate_number: str | None = None,
    color: str | None = None,
    brand: str | None = None,
    vehicle_type: str | None = None,
    owner_person_id: str | None = None,
) -> dict:
    return {
        "items": search_vehicles(keyword, plate_number, color, brand, vehicle_type, owner_person_id),
    }


@router.get("/records")
def find_records(
    person_id: str | None = None,
    vehicle_id: str | None = None,
    camera_id: str | None = None,
    location: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    min_similarity: float | None = None,
) -> dict:
    return {
        "items": search_snapshots(person_id, vehicle_id, camera_id, location, start_time, end_time, min_similarity),
    }


@router.post("/image")
async def find_by_image(
    file: UploadFile = File(...),
    top_k: int = Query(5, ge=1, le=20),
    min_similarity: float = Query(0.72, ge=0, le=1),
) -> dict:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail={"code": "EMPTY_IMAGE", "message": "Uploaded file is empty"})
    return search_by_image(file.filename or "query.jpg", content, top_k, min_similarity)
