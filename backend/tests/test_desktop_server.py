from __future__ import annotations

import desktop_server


def test_desktop_server_ignores_external_host_env(monkeypatch) -> None:
    captured = {}

    def fake_run(app, **kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(desktop_server.uvicorn, "run", fake_run)
    monkeypatch.setenv("GKGUARD_HOST", "0.0.0.0")
    monkeypatch.setenv("GKGUARD_PORT", "8765")

    desktop_server.main()

    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 8765
