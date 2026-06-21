from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.routers import ai, audit, c1, car_tasks, events, search, timeline


STATIC_DIR = Path(__file__).resolve().parent / "static"


app = FastAPI(
    title="GKGuard C2 AI Search Demo",
    description="C2 backend for mock multi-source security search, image search, timeline, and campusCar review dispatch.",
    version="0.1.0",
)


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.middleware("http")
async def guard_legacy_image_search_upload_size(request: Request, call_next):
    if request.method.upper() == "POST" and request.url.path == "/search/image":
        content_length = request.headers.get("content-length")
        max_request_bytes = search.MAX_IMAGE_UPLOAD_BYTES + search.MAX_IMAGE_MULTIPART_OVERHEAD_BYTES
        if not content_length:
            return JSONResponse(
                status_code=411,
                content={
                    "detail": {
                        "code": "CONTENT_LENGTH_REQUIRED",
                        "message": "Content-Length is required for image uploads.",
                    }
                },
            )
        try:
            request_size = int(content_length)
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={
                    "detail": {
                        "code": "INVALID_CONTENT_LENGTH",
                        "message": "Content-Length must be an integer.",
                    }
                },
            )
        if request_size > max_request_bytes:
            return JSONResponse(
                status_code=413,
                content={
                    "detail": {
                        "code": "IMAGE_TOO_LARGE",
                        "message": f"Image upload request exceeds the {max_request_bytes} byte request limit.",
                        "max_bytes": search.MAX_IMAGE_UPLOAD_BYTES,
                    }
                },
            )
    return await call_next(request)


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/demo")


@app.get("/demo", include_in_schema=False)
def demo_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "gkguard-c2-backend"}


app.include_router(search.router)
app.include_router(timeline.router)
app.include_router(events.router)
app.include_router(car_tasks.router)
app.include_router(ai.router)
app.include_router(audit.router)
app.include_router(c1.router)

