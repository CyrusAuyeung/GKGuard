import desktop_server


def test_desktop_server_ignores_inherited_host(monkeypatch) -> None:
    calls = []
    monkeypatch.setenv("GKGUARD_HOST", "0.0.0.0")
    monkeypatch.setenv("GKGUARD_PORT", "8787")
    monkeypatch.setattr(desktop_server.uvicorn, "run", lambda *args, **kwargs: calls.append((args, kwargs)))

    desktop_server.main()

    assert calls
    assert calls[0][1]["host"] == "127.0.0.1"
    assert calls[0][1]["port"] == 8787
