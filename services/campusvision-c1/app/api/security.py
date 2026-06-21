from __future__ import annotations

import secrets

from fastapi import Header, HTTPException, status

from app.core.config import settings


def require_c1_api_key(x_campusvision_api_key: str | None = Header(default=None)) -> None:
    """Require an API key when C1 is explicitly exposed or configured to require one."""
    if not settings.exposed_requires_api_key:
        return

    if not settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="CampusVision API key is required when the service is exposed; set CAMPUSVISION_API_KEY.",
        )

    if not x_campusvision_api_key or not secrets.compare_digest(x_campusvision_api_key, settings.api_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid CampusVision API key.")
