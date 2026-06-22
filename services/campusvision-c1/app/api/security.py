from __future__ import annotations

import secrets

from fastapi import Header, HTTPException, status
from starlette.datastructures import Headers

from app.core.config import settings


SENSITIVE_C1_PATHS = {
    "/api/v1/cameras",
    "/api/v1/persons",
    "/api/v1/records",
    "/api/v1/videos",
}

SENSITIVE_C1_PREFIXES = (
    "/api/v1/cameras/",
    "/api/v1/media/face/",
    "/api/v1/media/frame/",
    "/api/v1/persons/",
    "/api/v1/records/",
    "/api/v1/search/",
    "/api/v1/searches/",
    "/api/v1/videos/",
)


def c1_api_key_required_for_path(path: str, method: str) -> bool:
    if path.rstrip("/") in SENSITIVE_C1_PATHS:
        return True
    return any(path.startswith(prefix) for prefix in SENSITIVE_C1_PREFIXES)


def validate_c1_api_key(value: str | None) -> None:
    if not settings.exposed_requires_api_key:
        return
    if not settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "CAMPUSVISION_API_KEY_REQUIRED",
                "message": "CampusVision C1 is exposed or configured to require an API key, but CAMPUSVISION_API_KEY is not set.",
            },
        )
    if not value or not secrets.compare_digest(value, settings.api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "CAMPUSVISION_API_KEY_INVALID", "message": "Valid CampusVision API key is required."},
        )


def validate_c1_api_key_headers(headers: Headers) -> None:
    validate_c1_api_key(headers.get("x-campusvision-api-key"))


def require_c1_api_key(x_campusvision_api_key: str | None = Header(default=None)) -> None:
    validate_c1_api_key(x_campusvision_api_key)
