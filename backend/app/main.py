from fastapi import FastAPI

from app.routers import ai, car_tasks, events, search, timeline


app = FastAPI(
    title="GKGuard C2 AI Search Demo",
    description="C2 backend for mock multi-source security search, image search, timeline, and campusCar review dispatch.",
    version="0.1.0",
)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "gkguard-c2-backend"}


app.include_router(search.router)
app.include_router(timeline.router)
app.include_router(events.router)
app.include_router(car_tasks.router)
app.include_router(ai.router)

