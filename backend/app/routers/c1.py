from typing import Any

from fastapi import APIRouter, Body, File, HTTPException, Query, UploadFile
from fastapi.responses import Response

from app.services import c1_service


router = APIRouter(prefix="/c1", tags=["c1"])


def _raise_c1_unavailable(exc: c1_service.C1ServiceError, code: str | None = None) -> None:
    raise HTTPException(status_code=exc.status_code, detail={"code": code or exc.code, "message": str(exc)}) from exc


@router.get("/status")
def c1_status() -> dict:
    return c1_service.get_status()


@router.get("/persons")
def c1_persons() -> dict:
    try:
        return {"items": c1_service.list_people()}
    except c1_service.C1ServiceError as exc:
        _raise_c1_unavailable(exc)


@router.get("/videos")
def c1_videos() -> dict:
    try:
        return {"items": c1_service.list_videos()}
    except c1_service.C1ServiceError as exc:
        _raise_c1_unavailable(exc)


@router.get("/events")
def c1_events(
    person_id: str | None = Query(None),
    camera_id: str | None = Query(None),
    upper_color: str | None = Query(None),
    identified: bool | None = Query(None),
    start_time: str | None = Query(None),
    end_time: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict:
    try:
        return {
            "items": c1_service.list_events(
                person_id=person_id,
                camera_id=camera_id,
                upper_color=upper_color,
                identified=identified,
                start_time=start_time,
                end_time=end_time,
                limit=limit,
                offset=offset,
            ),
        }
    except c1_service.C1ServiceError as exc:
        _raise_c1_unavailable(exc)


@router.get("/persons/{person_id}/events")
def c1_person_events(person_id: str, limit: int = Query(100, ge=1, le=500)) -> dict:
    try:
        return {"items": c1_service.list_person_events(person_id, limit=limit)}
    except c1_service.C1ServiceError as exc:
        _raise_c1_unavailable(exc)


@router.get("/events/{event_id}/observations")
def c1_event_observations(event_id: str) -> dict:
    try:
        return {"items": c1_service.list_event_observations(event_id)}
    except c1_service.C1ServiceError as exc:
        _raise_c1_unavailable(exc)


@router.post("/query-faces")
async def c1_query_faces(file: UploadFile = File(...)) -> dict:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail={"code": "EMPTY_IMAGE", "message": "Uploaded file is empty"})
    try:
        return c1_service.detect_query_faces(
            filename=file.filename or "query.jpg",
            content=content,
            content_type=file.content_type,
        )
    except c1_service.C1ServiceError as exc:
        _raise_c1_unavailable(exc)


@router.post("/search/person-by-image")
async def c1_search_person_by_image(
    file: UploadFile = File(...),
    top_k: int = Query(5, ge=1, le=20),
    min_score: float | None = Query(None, ge=0, le=1),
    max_gap_sec: float = Query(3.0, ge=0),
    query_face_index: int | None = Query(None, ge=0),
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
            query_face_index=query_face_index,
        )
    except c1_service.C1ServiceError as exc:
        _raise_c1_unavailable(exc)


@router.post("/query/face-image")
async def c1_query_face_image(
    file: UploadFile = File(...),
    top_k: int = Query(5, ge=1, le=20),
    min_score: float | None = Query(None, ge=0, le=1),
    max_gap_sec: float = Query(3.0, ge=0),
    query_face_index: int | None = Query(None, ge=0),
    include_candidates: bool = Query(False),
    event_limit_per_person: int = Query(20, ge=1, le=100),
    match_limit_per_person: int = Query(10, ge=1, le=100),
    include_events: bool = Query(True),
    include_matches: bool = Query(True),
    camera_id: str | None = Query(None),
    start_time: str | None = Query(None),
    end_time: str | None = Query(None),
) -> dict:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail={"code": "EMPTY_IMAGE", "message": "Uploaded file is empty"})
    try:
        return c1_service.query_face_image_candidates(
            filename=file.filename or "query.jpg",
            content=content,
            content_type=file.content_type,
            top_k=top_k,
            min_score=min_score,
            max_gap_sec=max_gap_sec,
            query_face_index=query_face_index,
            include_candidates=include_candidates,
            event_limit_per_person=event_limit_per_person,
            match_limit_per_person=match_limit_per_person,
            include_events=include_events,
            include_matches=include_matches,
            camera_id=camera_id,
            start_time=start_time,
            end_time=end_time,
        )
    except c1_service.C1ServiceError as exc:
        _raise_c1_unavailable(exc)


@router.post("/query/person-attributes")
def c1_query_person_attributes(payload: dict[str, Any] = Body(...)) -> dict:
    try:
        return c1_service.query_person_attributes(payload)
    except c1_service.C1ServiceError as exc:
        _raise_c1_unavailable(exc)


@router.get("/media/{media_path:path}")
def c1_media(media_path: str) -> Response:
    try:
        content, media_type = c1_service.fetch_media_path(media_path)
    except c1_service.C1ServiceError as exc:
        _raise_c1_unavailable(exc, code="C1_MEDIA_UNAVAILABLE")
    return Response(content=content, media_type=media_type)
