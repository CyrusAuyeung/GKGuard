import hmac
import os

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.models import EventDispositionRequest, EventDispositionResponse
from app.services.audit_service import record_audit
from app.services.event_service import archive_event_disposition, build_case_package, build_event_report, get_event_related_records


router = APIRouter(prefix="/events", tags=["events"])
CASE_PACKAGE_EXPORT_TOKEN_ENV = "GKGUARD_CASE_PACKAGE_EXPORT_TOKEN"


def require_case_package_export_token(x_gkguard_export_token: str | None = Header(default=None)) -> None:
    expected_token = os.getenv(CASE_PACKAGE_EXPORT_TOKEN_ENV, "")
    if not expected_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "CASE_PACKAGE_EXPORT_DISABLED",
                "message": "Set GKGUARD_CASE_PACKAGE_EXPORT_TOKEN before exporting case packages.",
            },
        )
    if not x_gkguard_export_token or not hmac.compare_digest(x_gkguard_export_token, expected_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "CASE_PACKAGE_EXPORT_UNAUTHORIZED", "message": "Valid export authorization is required."},
        )


@router.get("/{event_id}/related-records")
def event_related_records(event_id: str) -> dict:
    records = get_event_related_records(event_id)
    if not records:
        raise HTTPException(status_code=404, detail={"code": "EVENT_NOT_FOUND", "message": event_id})
    return records


@router.get("/{event_id}/report")
def event_report(event_id: str) -> dict:
    report = build_event_report(event_id)
    if not report:
        raise HTTPException(status_code=404, detail={"code": "EVENT_NOT_FOUND", "message": event_id})
    record_audit(
        action="event_report_generated",
        target={"event_id": event_id, "report_id": report["report_id"]},
        metadata={"severity": report["severity"], "status": report["status"]},
    )
    return report


@router.post("/{event_id}/disposition", response_model=EventDispositionResponse)
def event_disposition(event_id: str, request: EventDispositionRequest) -> EventDispositionResponse:
    disposition = archive_event_disposition(event_id, request)
    if not disposition:
        raise HTTPException(status_code=404, detail={"code": "EVENT_NOT_FOUND", "message": event_id})
    record_audit(
        action="event_disposition_archived",
        actor=request.handler,
        target={"event_id": event_id, "disposition_id": disposition.disposition_id},
        metadata={"result": request.result, "status_after": disposition.status_after},
    )
    return disposition


@router.get("/{event_id}/case-package")
def event_case_package(event_id: str, _: None = Depends(require_case_package_export_token)) -> dict:
    package = build_case_package(event_id)
    if not package:
        raise HTTPException(status_code=404, detail={"code": "EVENT_NOT_FOUND", "message": event_id})
    record_audit(
        action="case_package_exported",
        target={"event_id": event_id, "package_id": package["package_id"]},
        metadata={"snapshot_count": len(package["evidence_snapshots"]), "audit_log_count": len(package["audit_logs"])},
    )
    return package
