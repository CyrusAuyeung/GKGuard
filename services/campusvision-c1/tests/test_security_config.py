from __future__ import annotations

import importlib


def test_api_key_prefers_campusvision_api_key(monkeypatch) -> None:
    monkeypatch.setenv("CAMPUSVISION_API_KEY", "primary-token")
    monkeypatch.setenv("C1_API_KEY", "fallback-token")

    import app.core.config as config

    reloaded = importlib.reload(config)

    assert reloaded.settings.api_key == "primary-token"


def test_api_key_falls_back_to_c1_api_key(monkeypatch) -> None:
    monkeypatch.delenv("CAMPUSVISION_API_KEY", raising=False)
    monkeypatch.setenv("C1_API_KEY", "fallback-token")

    import app.core.config as config

    reloaded = importlib.reload(config)

    assert reloaded.settings.api_key == "fallback-token"


def test_api_key_required_for_sensitive_read_paths() -> None:
    from app.api.security import c1_api_key_required_for_path

    for path in (
        "/api/v1/persons",
        "/api/v1/persons/gallery",
        "/api/v1/searches/search001",
        "/api/v1/media/frame/face001",
        "/api/v1/media/face/face001",
        "/api/v1/records",
    ):
        assert c1_api_key_required_for_path(path, "GET")


def test_api_key_required_for_camera_metadata_mutation() -> None:
    from app.api.security import c1_api_key_required_for_path

    assert c1_api_key_required_for_path("/api/v1/cameras", "POST")


def test_api_key_not_required_for_public_health() -> None:
    from app.api.security import c1_api_key_required_for_path

    assert not c1_api_key_required_for_path("/health", "GET")
