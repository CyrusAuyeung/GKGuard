from __future__ import annotations

import hmac
import os

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from app.services.audit_service import read_audit_logs


router = APIRouter(prefix="/audit", tags=["audit"])
AUDIT_TOKEN_ENV = "GKGUARD_AUDIT_TOKEN"


def require_audit_token(x_gkguard_audit_token: str | None = Header(default=None)) -> None:
    expected_token = os.getenv(AUDIT_TOKEN_ENV, "")
    if not expected_token or not x_gkguard_audit_token or not hmac.compare_digest(x_gkguard_audit_token, expected_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "AUDIT_FORBIDDEN", "message": "Audit logs require an authorized audit token."},
        )


@router.get("/logs")
def audit_logs(limit: int = Query(20, ge=1, le=100), _: None = Depends(require_audit_token)) -> dict:
    logs = read_audit_logs(limit)
    return {"items": logs, "count": len(logs)}
