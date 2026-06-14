from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.routers import ai, audit, c1, car_tasks, events, search, timeline


STATIC_DIR = Path(__file__).resolve().parent / "static"


app = FastAPI(
    title="GKGuard C2 AI Search Demo",
    description="C2 backend for mock multi-source security search, image search, timeline, and campusCar review dispatch.",
    version="0.1.0",
)


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


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

