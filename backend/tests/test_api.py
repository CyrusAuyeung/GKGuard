from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from app.main import app
from app.services.audit_service import clear_audit_logs


client = TestClient(app)
ROOT_DIR = Path(__file__).resolve().parents[2]


def setup_function() -> None:
    clear_audit_logs()


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_demo_page_available() -> None:
    response = client.get("/demo")
    assert response.status_code == 200
    assert "GKGuard 人脸检索" in response.text
    assert "人脸检索结果" in response.text
    assert "人物路线图" in response.text
    assert "desktopUpdatePanel" in response.text
    assert "newSearchBtn" in response.text
    assert "routeNewSearchBtn" in response.text
    assert "重新上传" in response.text
    assert "/static/styles.css?v=v0.1.22-ui" in response.text
    assert "/static/app.js?v=v0.1.22-ui" in response.text


def test_static_assets_render_real_thumbnails() -> None:
    script_response = client.get("/static/app.js")
    assert script_response.status_code == 200
    script = script_response.text
    assert "function recordThumbMarkup" in script
    assert "mini-face has-thumb" in script
    assert "record.thumbnailUrl || record.faceUrl || record.frameUrl" in script
    assert "record.frameUrl" in script
    assert "matchedPersonImageUrl" in script
    assert "uploadedImageUrl || matchedPersonImageUrl" in script
    assert "uploadedImageUrl = result.person.representativeFaceUrl" not in script
    assert "initDesktopUpdateEntry" in script
    assert "feedbackConfig" in script
    assert "loading: { title" in script
    assert "showToast(message, options = {})" in script
    assert "function hideToast" in script
    assert "normalizedMessage" in script
    assert "hideToast();\n\n  const resetScroll" in script.replace("\r\n", "\n")
    assert "let resultToast = null" in script
    assert "renderRouteCurrentSummary" in script
    assert "function setButtonBusy" in script
    assert "checkForUpdates" in script
    assert "installUpdate" in script
    assert "onUpdateEvent" in script
    assert "function resetSearchInput" in script
    assert "function renderRouteMap" in script
    assert "mapLabelClass" in script

    style_response = client.get("/static/styles.css")
    assert style_response.status_code == 200
    style = style_response.text
    normalized_style = style.replace("\r\n", "\n")
    assert ".portrait-frame img" in style
    assert "object-fit: contain" in style
    assert "object-position: center center" in style
    assert ".mini-face img" in style
    assert ".scene-frame" in style
    assert "min-width: 0" in style
    assert "width: calc(100vw" in style
    assert ".result-screen," in style
    assert "grid-template-areas:" in style
    assert ".result-record-strip" in style
    assert "grid-auto-flow: column" in style
    assert ".detail-toolbar" in style
    assert "position: sticky" in style
    assert ".route-overview" in style
    assert ".map-label.is-near-right" in style
    assert ".map-label.is-near-bottom" in style
    assert "grid-template-columns: repeat(4, minmax(0, 1fr))" in style
    assert ".upload-drop {\n    gap: 8px;" in normalized_style
    assert "min-height: 176px" in style
    assert ".button-cluster {\n    display: grid;" in normalized_style
    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in style
    assert ".record-panel::before" in style
    assert "content: attr(data-scroll-hint)" in style
    assert ".route-current-card" in style
    assert ".route-current-card { order: 3; }" in style
    assert ".toast[hidden] { display: none; }" in style
    assert "min-height: 42px" in style
    assert "left: min(62%, 242px)" in style
    assert "min-width: 56px" in style
    assert "height: clamp(320px, calc(100vh - 500px), 560px)" in style
    assert "#routeTimelineRows { display: grid; gap: 6px; max-height: 224px" in style
    assert ".route-record-list" in style
    assert "grid-template-columns: 96px minmax(0, 1fr)" in style
    assert ".mini-face { position: relative; overflow: hidden; width: 96px; height: 60px" in style
    assert ".mini-face img { width: 100%; height: 100%; object-fit: contain" in style
    assert "background: #eef4ff" in style
    assert ".scene-frame { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: contain" in style
    assert ".desktop-update" in style
    assert ".toast-success" in style
    assert ".toast-warning" in style
    assert ".toast-error" in style
    assert ".toast-loading" in style
    assert "[data-state=\"busy\"]" in style
    assert ".ui-icon" in style
    assert "stroke: currentColor" in style
    assert "background-image: url(\"/static/icons/search-action.png\")" not in style
    assert ".mini-face img { width: 100%; height: 100%; object-fit: cover" not in style
    assert ".scene-frame { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover" not in style

    page_response = client.get("/demo")
    assert page_response.status_code == 200
    page = page_response.text
    assert "icon-face-search" in page
    assert "icon-search" in page
    assert "icon-upload" in page
    assert "icon-back-upload" in page
    assert "icon-back-results" in page
    assert "icon-route" in page
    assert "icon-export" in page
    assert "icon-update" in page
    assert "icon-info" in page
    assert "resultSourceBadge" in page
    assert "resultCountBadge" in page
    assert "toastTitle" in page
    assert "toastMessage" in page
    assert "toastIconUse" in page
    assert "导出记录" in page
    assert "定位记录列表" in page
    assert "定位时间线" in page
    assert "routeOverviewPointCount" in page
    assert "routeOverviewDuration" in page
    assert "data-scroll-hint=\"横向滑动\"" in page
    assert "routeCurrentRecord" in page
    assert "routeCurrentSimilarity" in page
    assert 'id="toast" class="toast toast-info" role="status" aria-live="polite" aria-atomic="true" hidden' in page
    assert "导出截图" not in page
    assert "查看全部结果" not in page
    assert "查看完整轨迹" not in page
    assert page.index('id="routeNewSearchBtn"') < page.index('id="backToResultBtn"')
    assert page.index('id="backToResultBtn"') < page.index('id="exportRouteBtn"')
    assert page.index('id="exportRouteBtn"') < page.index('id="fullRouteBtn"')

    for icon_name in [
        "app-mark.png",
        "boot-mark.png",
    ]:
        icon_response = client.get(f"/static/icons/{icon_name}")
        assert icon_response.status_code == 200
        assert icon_response.headers["content-type"] == "image/png"


def test_desktop_update_bridge_wired() -> None:
    main_script = (ROOT_DIR / "desktop" / "main.js").read_text(encoding="utf-8")
    preload_script = (ROOT_DIR / "desktop" / "preload.js").read_text(encoding="utf-8")

    assert "preload.js" in main_script
    assert "APP_ICON_PATH" in main_script
    assert "app-mark.ico" in main_script
    assert "minWidth: 680" in main_script
    assert "minHeight: 640" in main_script
    assert "STATIC_ASSET_VERSION = \"v0.1.22-ui\"" in main_script
    assert "prepareBackendPort" in main_script
    assert "existingBackendMatchesCurrentBuild" in main_script
    assert "getAvailablePort" in main_script
    assert "GKGUARD_PORT: String(activeBackendPort)" in main_script
    assert "ipcMain.handle(\"gkguard:check-for-updates\"" in main_script
    assert "ipcMain.handle(\"gkguard:install-update\"" in main_script
    assert "ipcMain.handle(\"gkguard:connect-c1\"" in main_script
    assert "`${DEFAULT_C1_TUNNEL_URL},${DEFAULT_C1_DIRECT_URL}`" in main_script
    assert "isC1TunnelConnected" in main_script
    assert "waitForC1TunnelReady" in main_script
    assert "probeC1Endpoint" in main_script
    assert "gkguard:ssh-connect-progress" in main_script
    assert "autoUpdater.checkForUpdates" in main_script
    assert "autoUpdater.downloadUpdate" in main_script
    assert "autoUpdater.quitAndInstall" in main_script
    assert "startEmbeddedSshTunnel" in main_script
    assert "promptForSshPassword" in main_script
    assert "ssh-password.html" in main_script
    assert "width: 560" in main_script
    assert "height: 640" in main_script
    assert "recoverable: true" in main_script
    assert "setTimeout(() => done(result), 420)" in main_script
    assert "connecting = false" in main_script
    assert "lastProgressPercent" in main_script
    assert "Math.max(12, lastProgressPercent)" in main_script
    assert "new SshClient" in main_script
    assert "forwardOut" in main_script
    assert "contextBridge.exposeInMainWorld(\"gkguardDesktop\"" in preload_script
    assert "checkForUpdates" in preload_script
    assert "downloadUpdate" in preload_script
    assert "installUpdate" in preload_script
    assert "onUpdateEvent" in preload_script
    assert "connectC1" in preload_script
    assert "onSshConnectProgress" in preload_script
    assert "submitSshPassword" in preload_script
    assert "cancelSshPassword" in preload_script

    password_page = (ROOT_DIR / "desktop" / "ssh-password.html").read_text(encoding="utf-8")
    assert "服务器密码" in password_page
    assert "connection-icon" in password_page
    assert "connection-card" in password_page
    assert "connection-steps" in password_page
    assert "连接失败时请检查" in password_page
    assert "密码只用于本次 SSH 连接，不会保存到 GKGuard、配置文件、日志或仓库" in password_page
    assert "重新连接" in password_page
    assert "当前预览环境无法建立 SSH 连接" in password_page
    assert "submitSshPassword" in password_page
    assert "cancelSshPassword" in password_page
    assert "progressBar" in password_page
    assert "onSshConnectProgress" in password_page


def test_c1_status_handles_unavailable_service(monkeypatch) -> None:
    from app.services import c1_service

    monkeypatch.setattr(c1_service, "C1_BASE_URL", "http://127.0.0.1:9")
    monkeypatch.setattr(c1_service, "_selected_base_url", None)
    monkeypatch.delenv("C1_BASE_URL", raising=False)
    monkeypatch.delenv("C1_CANDIDATE_URLS", raising=False)
    monkeypatch.delenv("C1_CONFIG_PATH", raising=False)
    response = client.get("/c1/status")
    assert response.status_code == 200
    body = response.json()
    assert body["baseUrl"] == "http://10.4.167.122:8000"
    assert body["reachable"] is False
    assert body["selectedBaseUrl"] is None


def test_c1_status_selects_first_healthy_candidate(monkeypatch) -> None:
    from app.services import c1_service

    def fake_status_for_url(base_url: str):
        return {
            "baseUrl": base_url,
            "reachable": base_url.endswith(":8000"),
            "healthOk": base_url.endswith(":8000"),
        }

    monkeypatch.setattr(c1_service, "_selected_base_url", None)
    monkeypatch.delenv("C1_BASE_URL", raising=False)
    monkeypatch.delenv("C1_CONFIG_PATH", raising=False)
    monkeypatch.setenv("C1_CANDIDATE_URLS", "http://127.0.0.1:9,http://10.4.167.122:8000")
    monkeypatch.setattr(c1_service, "_status_for_url", fake_status_for_url)

    response = client.get("/c1/status")
    assert response.status_code == 200
    body = response.json()
    assert body["selectedBaseUrl"] == "http://10.4.167.122:8000"
    assert body["candidateUrls"][:2] == ["http://127.0.0.1:9", "http://10.4.167.122:8000"]


def test_c1_request_retries_tunnel_after_retryable_http_status(monkeypatch) -> None:
    from app.services import c1_service

    attempts = []

    class FakeResponse:
        def json(self):
            return {"ok": True}

    def fake_status_for_url(base_url: str):
        return {"baseUrl": base_url, "reachable": True, "healthOk": True}

    def fake_request_once(base_url: str, method: str, path: str, **kwargs):
        attempts.append(base_url)
        if base_url == "http://10.4.167.122:8000":
            request = httpx.Request(method, f"{base_url}{path}")
            response = httpx.Response(503, request=request)
            raise httpx.HTTPStatusError("Service unavailable", request=request, response=response)
        return FakeResponse()

    monkeypatch.setattr(c1_service, "_selected_base_url", None)
    monkeypatch.setenv("C1_CANDIDATE_URLS", "http://10.4.167.122:8000,http://127.0.0.1:18000")
    monkeypatch.setattr(c1_service, "_status_for_url", fake_status_for_url)
    monkeypatch.setattr(c1_service, "_request_once", fake_request_once)

    response = c1_service._request("POST", "/api/v1/search/person-by-image")

    assert response.json() == {"ok": True}
    assert attempts[:2] == ["http://10.4.167.122:8000", "http://127.0.0.1:18000"]
    assert c1_service._selected_base_url == "http://127.0.0.1:18000"


def test_c1_candidate_urls_reads_config_file(monkeypatch, tmp_path) -> None:
    from app.services import c1_service

    config_path = tmp_path / "c1-connection.json"
    config_path.write_text('{"candidateUrls":["http://10.4.167.122:8000","http://127.0.0.1:18000"]}', encoding="utf-8")
    monkeypatch.delenv("C1_BASE_URL", raising=False)
    monkeypatch.delenv("C1_CANDIDATE_URLS", raising=False)
    monkeypatch.setenv("C1_CONFIG_PATH", str(config_path))
    monkeypatch.setattr(c1_service, "C1_BASE_URL", "http://127.0.0.1:18000")

    urls = c1_service._candidate_urls()
    assert urls[:2] == ["http://10.4.167.122:8000", "http://127.0.0.1:18000"]


def test_c1_candidate_urls_include_builtin_defaults(monkeypatch) -> None:
    from app.services import c1_service

    monkeypatch.delenv("C1_BASE_URL", raising=False)
    monkeypatch.delenv("C1_CANDIDATE_URLS", raising=False)
    monkeypatch.delenv("C1_CONFIG_PATH", raising=False)
    monkeypatch.setattr(c1_service, "C1_BASE_URL", "http://127.0.0.1:18000")

    urls = c1_service._candidate_urls()
    assert urls[:2] == ["http://10.4.167.122:8000", "http://127.0.0.1:18000"]


def test_c1_person_search_maps_adapter_response(monkeypatch) -> None:
    from app.services import c1_service

    def fake_search_person_by_image(**kwargs):
        assert kwargs["filename"] == "target.jpg"
        return {
            "source": "c1",
            "records": [
                {
                    "id": 1,
                    "title": "记录1",
                    "time": "10:00:00",
                    "fullTime": "2026-06-14 10:00:00",
                    "location": "cam02",
                    "camera": "cam02",
                    "cameraId": "cam02",
                    "similarity": 0.88,
                    "note": "来自 CampusVision C1 的真实检索结果",
                    "sceneClass": "scene-1",
                    "progress": 21,
                    "frameUrl": "/c1/media/frame/face-1",
                    "faceUrl": "/c1/media/face/face-1",
                }
            ],
            "routePoints": [],
        }

    monkeypatch.setattr(c1_service, "search_person_by_image", fake_search_person_by_image)
    response = client.post(
        "/c1/search/person-by-image",
        files={"file": ("target.jpg", b"fake image", "image/jpeg")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "c1"
    assert body["records"][0]["frameUrl"] == "/c1/media/frame/face-1"
    assert body["records"][0]["faceUrl"] == "/c1/media/face/face-1"


def test_c1_record_mapping_exposes_face_thumbnail_url(monkeypatch) -> None:
    from app.services import c1_service

    monkeypatch.setattr(c1_service, "_selected_base_url", "http://127.0.0.1:18000")
    record = c1_service._record_from_match(
        {
            "face_id": "face-1",
            "frame_url": "/api/v1/media/frame/face-1",
            "captured_at": "2026-06-14T10:00:00",
            "camera_id": "cam02",
            "score": 0.91,
        },
        1,
    )

    assert record["frameUrl"] == "/c1/media/frame/face-1"
    assert record["faceUrl"] == "/c1/media/face/face-1"


def test_root_redirects_to_demo() -> None:
    response = client.get("/", follow_redirects=False)
    assert response.status_code in {307, 308}
    assert response.headers["location"] == "/demo"


def test_person_search_by_student_id() -> None:
    response = client.get("/search/persons", params={"student_id": "S2026001"})
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["person_id"] == "P001"


def test_vehicle_search_by_color() -> None:
    response = client.get("/search/vehicles", params={"color": "red"})
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["vehicle_id"] == "V004"


def test_person_timeline_summary() -> None:
    response = client.get("/persons/P001/timeline", params={"min_similarity": 0.9})
    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["point_count"] >= 5
    assert body["summary"]["last_location"] == "Dorm East Gate"
    assert body["points"] == sorted(body["points"], key=lambda point: point["time"])


def test_image_search_uses_demo_hint() -> None:
    response = client.post(
        "/search/image",
        params={"top_k": 3, "min_similarity": 0.8},
        files={"file": ("p001_target.jpg", b"p001 target demo image", "image/jpeg")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["query_hint_person_id"] == "P001"
    assert len(body["matches"]) == 3
    assert all(match["person_id"] == "P001" for match in body["matches"])
    audit_response = client.get("/audit/logs")
    assert audit_response.status_code == 200
    assert audit_response.json()["items"][-1]["action"] == "image_search"


def test_event_related_records() -> None:
    response = client.get("/events/ALT-001/related-records")
    assert response.status_code == 200
    body = response.json()
    assert body["event"]["alert_id"] == "ALT-001"
    assert body["timeline"]["person_id"] == "P001"


def test_event_report() -> None:
    response = client.get("/events/ALT-001/report")
    assert response.status_code == 200
    body = response.json()
    assert body["report_id"] == "RPT-ALT-001"
    assert body["severity"] == "high"
    assert body["evidence"]["timeline_point_count"] >= 5
    assert body["recommended_actions"]
    audit_response = client.get("/audit/logs")
    assert audit_response.json()["items"][-1]["action"] == "event_report_generated"


def test_event_disposition_archive() -> None:
    response = client.post(
        "/events/ALT-001/disposition",
        json={"result": "confirmed_safe", "handler": "security_desk_demo", "notes": "closed in demo"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["disposition_id"] == "DSP-ALT-001"
    assert body["status_before"] == "open"
    assert body["status_after"] == "closed"
    assert body["evidence_summary"]["last_location"] == "Dorm East Gate"
    audit_response = client.get("/audit/logs")
    assert audit_response.json()["items"][-1]["action"] == "event_disposition_archived"


def test_audit_logs_limit() -> None:
    client.get("/events/ALT-001/report")
    client.post(
        "/events/ALT-001/disposition",
        json={"result": "confirmed_safe", "handler": "security_desk_demo", "notes": "closed in demo"},
    )
    response = client.get("/audit/logs", params={"limit": 1})
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["items"][0]["action"] == "event_disposition_archived"


def test_case_package_export() -> None:
    client.get("/events/ALT-001/report")
    client.post(
        "/events/ALT-001/disposition",
        json={"result": "confirmed_safe", "handler": "security_desk_demo", "notes": "closed in demo"},
    )
    response = client.get("/events/ALT-001/case-package")
    assert response.status_code == 200
    body = response.json()
    assert body["package_id"] == "PKG-ALT-001"
    assert body["report"]["report_id"] == "RPT-ALT-001"
    assert body["subject"]["person"]["person_id"] == "P001"
    assert body["timeline_summary"]["last_location"] == "Dorm East Gate"
    assert len(body["evidence_snapshots"]) >= 5
    assert body["handoff_checklist"]

    audit_response = client.get("/audit/logs", params={"limit": 1})
    assert audit_response.json()["items"][0]["action"] == "case_package_exported"


def test_mock_car_dispatch() -> None:
    response = client.post(
        "/car-tasks/mock-dispatch",
        json={
            "event_id": "ALT-001",
            "target_location": "Dorm East Gate",
            "reason": "field review",
            "robot_id": "CAR-DEMO-01",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "arrived_mock"
    assert body["event_id"] == "ALT-001"
    assert body["bridge_contract"]["command_topic"] == "/U2RTopic_Command"
    assert body["bridge_contract"]["position_topic"] == "/R2UTopic_Pos"
    assert body["video_hls_url"].endswith("/campuscar/index.m3u8")


def test_ue_bridge_status_contract() -> None:
    response = client.get("/car-tasks/ue-bridge-status")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "mock_ready"
    assert body["rosbridge_url"] == "ws://127.0.0.1:9090"
    assert body["command_topic"] == "/U2RTopic_Command"
    assert body["position_topic"] == "/R2UTopic_Pos"
    assert body["status_topic"] == "/R2UTopic_Text"
    assert body["external_test_app"] == "GKD_Station_Qiyi.exe"


def test_natural_query_parser() -> None:
    response = client.post("/ai/parse-query", json={"query": "find red car near parking at night"})
    assert response.status_code == 200
    filters = response.json()["filters"]
    assert filters["object_type"] == "vehicle"
    assert filters["color"] == "red"
    assert filters["location"] == "Parking Lot East"
    assert filters["time_hint"] == "after_hours"


def test_natural_query_parser_supports_chinese() -> None:
    response = client.post("/ai/parse-query", json={"query": "夜间停车场附近的红色车辆"})
    assert response.status_code == 200
    filters = response.json()["filters"]
    assert filters["object_type"] == "vehicle"
    assert filters["color"] == "red"
    assert filters["location"] == "Parking Lot East"
    assert filters["time_hint"] == "after_hours"
