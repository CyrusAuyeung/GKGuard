from __future__ import annotations

from fastapi import FastAPI

from app.api.routes import router
from app.core.config import settings
from app.services import live_service
from app.storage.db import init_db
from app.vision.face_engine import get_face_engine

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="CampusVision C1: image-to-video person search and trajectory timeline API.",
)


@app.on_event("startup")
def startup():
    settings.ensure_dirs()
    init_db()


@app.on_event("shutdown")
def shutdown():
    live_service.stop_all_live_monitors()


@app.get("/health")
def health():
    engine = get_face_engine()
    return {
        "status": "ok",
        "app": settings.app_name,
        "face_engine": engine.name,
        "data_dir": str(settings.data_dir),
        "db_path": str(settings.db_path),
    }


app.include_router(router, prefix="/api/v1")
