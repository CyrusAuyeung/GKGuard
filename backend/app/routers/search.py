from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.services.audit_service import record_audit
from app.services.image_search_service import search_by_image
from app.services.search_service import get_person_profile, search_persons, search_snapshots, search_vehicles


router = APIRouter(prefix="/search", tags=["search"])
MAX_IMAGE_UPLOAD_BYTES = 2 * 1024 * 1024
MAX_IMAGE_MULTIPART_OVERHEAD_BYTES = 64 * 1024
IMAGE_UPLOAD_READ_LIMIT_BYTES = MAX_IMAGE_UPLOAD_BYTES + 1


def image_too_large_error() -> HTTPException:
    return HTTPException(
        status_code=413,
        detail={
            "code": "IMAGE_TOO_LARGE",
            "message": f"Uploaded image exceeds the {MAX_IMAGE_UPLOAD_BYTES} byte limit.",
            "max_bytes": MAX_IMAGE_UPLOAD_BYTES,
        },
    )


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
    content = await file.read(IMAGE_UPLOAD_READ_LIMIT_BYTES)
    if len(content) > MAX_IMAGE_UPLOAD_BYTES:
        raise image_too_large_error()
    if not content:
        raise HTTPException(status_code=400, detail={"code": "EMPTY_IMAGE", "message": "Uploaded file is empty"})
    result = search_by_image(file.filename or "query.jpg", content, top_k, min_similarity)
    record_audit(
        action="image_search",
        target={"query_filename": result["query_filename"], "hint_person_id": result["query_hint_person_id"]},
        metadata={"match_count": len(result["matches"]), "top_k": top_k, "min_similarity": min_similarity},
    )
    return result
