from __future__ import annotations

from html import escape
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response

from app.schemas import CameraCreate, CameraOut, IndexResult, PersonIndexResult, PersonOut, VideoOut
from app.services import person_service, search_service, video_service
from app.storage import db

router = APIRouter()


@router.post("/cameras", response_model=CameraOut)
def create_camera(payload: CameraCreate):
    return db.upsert_camera(payload.model_dump())


@router.get("/cameras", response_model=list[CameraOut])
def list_cameras():
    return db.list_cameras()


@router.post("/videos/upload", response_model=VideoOut)
async def upload_video(
    file: UploadFile = File(...),
    camera_id: str = Form(...),
    recorded_at: Optional[str] = Form(None),
    frame_interval_sec: Optional[float] = Form(None),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename.")

    video = video_service.save_uploaded_video(
        file.file,
        filename=file.filename,
        camera_id=camera_id,
        recorded_at=recorded_at,
        frame_interval_sec=frame_interval_sec,
    )
    return video


@router.get("/videos", response_model=list[VideoOut])
def list_videos():
    return db.list_videos()


@router.post("/persons/rebuild-index", response_model=PersonIndexResult)
def rebuild_person_index(
    merge_threshold: Optional[float] = Form(None),
    min_faces: int = Form(2),
    min_face_area: float = Form(2500.0),
    min_detection_score: float = Form(0.85),
):
    return person_service.rebuild_person_index(
        merge_threshold=merge_threshold,
        min_faces=min_faces,
        min_face_area=min_face_area,
        min_detection_score=min_detection_score,
    )


@router.post("/persons/update-index", response_model=PersonIndexResult)
def update_person_index(
    merge_threshold: Optional[float] = Form(None),
    person_match_threshold: float = Form(0.68),
    min_faces: int = Form(2),
    min_face_area: float = Form(2500.0),
    min_detection_score: float = Form(0.85),
):
    return person_service.update_person_index(
        merge_threshold=merge_threshold,
        person_match_threshold=person_match_threshold,
        min_faces=min_faces,
        min_face_area=min_face_area,
        min_detection_score=min_detection_score,
    )


@router.get("/persons", response_model=list[PersonOut])
def list_persons():
    return person_service.list_persons()


@router.get("/persons/gallery", response_class=HTMLResponse)
def persons_gallery():
        persons = person_service.person_gallery_items()
        cards = []
        for person in persons:
                samples = "".join(
                        f'<img src="{escape(sample["face_crop_url"])}" alt="{escape(sample["face_id"])}">'
                        for sample in person.get("sample_faces", [])
                )
                cards.append(
                        f"""
                        <article class="person-card">
                            <img class="hero-face" src="{escape(person.get('representative_face_crop_url') or '')}" alt="representative face">
                            <div class="person-meta">
                                <h2>{escape(person['person_id'])}</h2>
                                <dl>
                                    <div><dt>face_count</dt><dd>{int(person.get('face_count') or 0)}</dd></div>
                                    <div><dt>representative_face_id</dt><dd>{escape(str(person.get('representative_face_id') or ''))}</dd></div>
                                    <div><dt>first_seen_at</dt><dd>{escape(str(person.get('first_seen_at') or ''))}</dd></div>
                                    <div><dt>last_seen_at</dt><dd>{escape(str(person.get('last_seen_at') or ''))}</dd></div>
                                </dl>
                            </div>
                            <div class="samples">{samples}</div>
                        </article>
                        """
                )

        body = "\n".join(cards) or '<p class="empty">No persons indexed yet.</p>'
        return HTMLResponse(
                f"""
                <!doctype html>
                <html lang="zh-CN">
                <head>
                    <meta charset="utf-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1">
                    <title>CampusVision 人物库</title>
                    <style>
                        body {{ margin: 0; font-family: Arial, sans-serif; background: #f6f7f9; color: #20242a; }}
                        main {{ max-width: 1180px; margin: 0 auto; padding: 24px; }}
                        header {{ display: flex; justify-content: space-between; align-items: baseline; gap: 16px; margin-bottom: 18px; }}
                        h1 {{ font-size: 24px; margin: 0; }}
                        .count {{ color: #69717d; }}
                        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; }}
                        .person-card {{ display: grid; grid-template-columns: 128px 1fr; gap: 14px; padding: 14px; background: #fff; border: 1px solid #dde1e7; border-radius: 8px; }}
                        .hero-face {{ width: 128px; height: 128px; object-fit: cover; background: #e9edf2; border-radius: 6px; }}
                        h2 {{ font-size: 16px; margin: 0 0 10px; word-break: break-all; }}
                        dl {{ margin: 0; display: grid; gap: 6px; }}
                        dl div {{ display: grid; grid-template-columns: 128px 1fr; gap: 8px; }}
                        dt {{ color: #69717d; }}
                        dd {{ margin: 0; word-break: break-all; }}
                        .samples {{ grid-column: 1 / -1; display: flex; gap: 8px; overflow-x: auto; padding-top: 4px; }}
                        .samples img {{ width: 54px; height: 54px; object-fit: cover; border-radius: 5px; background: #e9edf2; }}
                        .empty {{ color: #69717d; }}
                    </style>
                </head>
                <body>
                    <main>
                        <header><h1>CampusVision 人物库</h1><span class="count">{len(persons)} persons</span></header>
                        <section class="grid">{body}</section>
                    </main>
                </body>
                </html>
                """
        )


@router.post("/videos/{video_id}/index", response_model=IndexResult)
def index_video(video_id: str, frame_interval_sec: Optional[float] = None):
    try:
        return video_service.index_video(video_id, frame_interval_sec=frame_interval_sec)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Indexing failed: {exc}") from exc


@router.post("/search/by-image")
async def search_by_image(
    files: list[UploadFile] = File(...),
    top_k: int = Form(20),
    min_score: Optional[float] = Form(None),
    max_gap_sec: float = Form(3.0),
    camera_id: Optional[str] = Form(None),
    start_time: Optional[str] = Form(None),
    end_time: Optional[str] = Form(None),
):
    import uuid

    temp_search_id = "upload_" + uuid.uuid4().hex
    paths = []
    for f in files:
        if not f.filename:
            continue
        paths.append(search_service.save_query_image(f.file, f.filename, temp_search_id))

    if not paths:
        raise HTTPException(status_code=400, detail="No query image uploaded.")

    result = search_service.search_by_images(
        paths,
        top_k=top_k,
        min_score=min_score,
        max_gap_sec=max_gap_sec,
        camera_id=camera_id,
        start_time=start_time,
        end_time=end_time,
    )
    return result


@router.post("/search/person-by-image")
async def search_person_by_image(
    files: list[UploadFile] = File(...),
    top_k: int = Form(5),
    min_score: Optional[float] = Form(None),
    max_gap_sec: float = Form(3.0),
):
    import uuid

    temp_search_id = "upload_" + uuid.uuid4().hex
    paths = []
    for f in files:
        if not f.filename:
            continue
        paths.append(search_service.save_query_image(f.file, f.filename, temp_search_id))

    if not paths:
        raise HTTPException(status_code=400, detail="No query image uploaded.")

    return person_service.search_persons_by_images(
        paths,
        top_k=top_k,
        min_score=min_score,
        max_gap_sec=max_gap_sec,
    )


@router.get("/searches/{search_id}")
def get_search(search_id: str):
    result = db.get_search(search_id)
    if not result:
        raise HTTPException(status_code=404, detail="search_id not found")
    return result


@router.get("/media/frame/{face_id}")
def get_frame(face_id: str):
    record = db.get_face_record(face_id)
    if not record:
        raise HTTPException(status_code=404, detail="face_id not found")

    return FileResponse(record["frame_path"], media_type="image/jpeg")


@router.get("/media/face/{face_id}")
def get_face_crop(face_id: str):
    import cv2

    record = db.get_face_record(face_id)
    if not record:
        raise HTTPException(status_code=404, detail="face_id not found")

    image = cv2.imread(record["frame_path"])
    if image is None:
        raise HTTPException(status_code=404, detail="frame image not found")

    height, width = image.shape[:2]
    bbox = record["bbox"]
    x1 = max(0, min(width - 1, int(bbox["x1"])))
    y1 = max(0, min(height - 1, int(bbox["y1"])))
    x2 = max(x1 + 1, min(width, int(bbox["x2"])))
    y2 = max(y1 + 1, min(height, int(bbox["y2"])))

    crop = image[y1:y2, x1:x2]
    ok, encoded = cv2.imencode(".jpg", crop)
    if not ok:
        raise HTTPException(status_code=500, detail="failed to encode face crop")
    return Response(content=encoded.tobytes(), media_type="image/jpeg")


@router.get("/records")
def list_records(
    camera_id: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
):
    records = db.list_face_records(camera_id=camera_id, start_time=start_time, end_time=end_time)
    for rec in records:
        rec.pop("embedding", None)
        rec["frame_url"] = f"/api/v1/media/frame/{rec['face_id']}"
    return records
