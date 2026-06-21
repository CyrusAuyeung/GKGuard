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
