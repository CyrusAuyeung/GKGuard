from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import Response

from app.services import c1_service


router = APIRouter(prefix="/c1", tags=["c1"])


@router.get("/status")
def c1_status() -> dict:
    return c1_service.get_status()


@router.get("/persons")
def c1_persons() -> dict:
    try:
        return {"items": c1_service.list_people()}
    except c1_service.C1ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": "C1_UNAVAILABLE", "message": str(exc)}) from exc


@router.get("/videos")
def c1_videos() -> dict:
    try:
        return {"items": c1_service.list_videos()}
    except c1_service.C1ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": "C1_UNAVAILABLE", "message": str(exc)}) from exc


@router.post("/search/person-by-image")
async def c1_search_person_by_image(
    file: UploadFile = File(...),
    top_k: int = Query(5, ge=1, le=20),
    min_score: float | None = Query(None, ge=0, le=1),
    max_gap_sec: float = Query(3.0, ge=0),
) -> dict:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail={"code": "EMPTY_IMAGE", "message": "Uploaded file is empty"})
    try:
        return c1_service.search_person_by_image(
            filename=file.filename or "query.jpg",
            content=content,
            content_type=file.content_type,
            top_k=top_k,
            min_score=min_score,
            max_gap_sec=max_gap_sec,
        )
    except c1_service.C1ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": "C1_UNAVAILABLE", "message": str(exc)}) from exc


@router.get("/media/{kind}/{face_id}")
def c1_media(kind: str, face_id: str) -> Response:
    try:
        content, media_type = c1_service.fetch_media(kind, face_id)
    except c1_service.C1ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": "C1_MEDIA_UNAVAILABLE", "message": str(exc)}) from exc
    return Response(content=content, media_type=media_type)