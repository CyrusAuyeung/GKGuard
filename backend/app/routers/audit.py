from fastapi import APIRouter, Query

from app.services.audit_service import read_audit_logs


router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/logs")
def audit_logs(limit: int = Query(20, ge=1, le=100)) -> dict:
    logs = read_audit_logs(limit)
    return {"items": logs, "count": len(logs)}
