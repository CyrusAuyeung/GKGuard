from pathlib import Path

import importlib
import httpx
import os
import time
from fastapi.testclient import TestClient

from app.main import app
from app.services import c1_service
from app.services.audit_service import clear_audit_logs


client = TestClient(app)
ROOT_DIR = Path(__file__).resolve().parents[2]


def setup_function() -> None:
    os.environ["GKGUARD_AUDIT_TOKEN"] = "test-audit-token"
    os.environ["GKGUARD_CASE_PACKAGE_EXPORT_TOKEN"] = "test-export-token"
    clear_audit_logs()
    c1_service._selected_base_url = None
    c1_service._connection_generation = 0
    c1_service._status_cache.clear()
    c1_service._clear_media_cache()


def audit_headers() -> dict[str, str]:
    return {"X-GKGuard-Audit-Token": os.environ["GKGUARD_AUDIT_TOKEN"]}


def export_headers() -> dict[str, str]:
    return {"X-GKGuard-Export-Token": os.environ["GKGUARD_CASE_PACKAGE_EXPORT_TOKEN"]}


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
    assert "mediaViewer" in response.text
    assert "newSearchBtn" in response.text
    assert "routeNewSearchBtn" in response.text
    assert "重新上传" in response.text
    assert "/static/styles.css?v=v0.1.37-ui" in response.text
    assert "/static/app.js?v=v0.1.37-ui" in response.text


def test_static_assets_render_real_thumbnails() -> None:
    script_response = client.get("/static/app.js")
    assert script_response.status_code == 200
    script = script_response.text
    assert "function recordThumbMarkup" in script
    assert "mini-face has-thumb" in script
    assert "record.thumbnailUrl || record.faceUrl || record.frameUrl" in script
    assert "record.frameUrl" in script
    assert "matchedPersonImageUrl" in script
    assert "selectedQueryFaceImageUrl || matchedPersonImageUrl || uploadedImageUrl" in script
    assert "function prepareQueryFaces" in script
    assert 'fetchWithTimeout("/c1/query-faces"' in script
    assert 'fetchWithTimeout(`/c1/search/person-by-image?' in script
    assert "localizedC1Notice" in script
    assert "CampusVision C1 响应超时" in script
    assert "CONFIDENT_QUERY_FACE_SCORE = 0.65" in script
    assert "MIN_VISIBLE_QUERY_FACE_SCORE = 0.45" in script
    assert "function preloadFrameImage" in script
    assert "function warmFrameImages" in script
    assert "function renderSelectedRecordFrame" in script
    assert "frameImagePreloadCache.delete(frameUrl);" in script
    assert "selectedRecordId !== nextRecordId" in script
    assert "is-frame-loading" in script
    assert "syncRecordActiveStates" in script
    assert "SEARCH_WATCHDOG_TIMEOUT_MS = 30000" in script
    assert "query_face_index" in script
    assert "data-query-face-box" in script
    assert "function frameFaceBoxMarkup" in script
    assert "data-frame-face-box" in script
    assert "function positionFrameFaceBoxes" in script
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
    assert "function openMediaViewer" in script
    assert "function closeMediaViewer" in script
    assert "function openQueryFaceModal" in script
    assert "function setQueryFaceModalZoom" in script
    assert "function syncUploadPreviewAction" in script
    assert "function openFaceFilePicker" in script
    assert "QUERY_FACE_MODAL_MIN_ZOOM = 0.5" in script
    assert "return Math.min(availableWidth / image.naturalWidth, availableHeight / image.naturalHeight)" in script
    assert "data-image-width" in script
    assert "function cropRectFromSelectedFaceElement" in script
    assert "function expandQueryFacePortraitCropRect" in script
    assert "TARGET_PORTRAIT_CROP_PADDING_TOP = 0.65" in script
    assert "const squareSide = Math.max(paddedWidth, paddedHeight)" in script
    assert "function queryFaceHitFromPoint" in script
    assert "sourceWidth = finiteNumber" in script
    assert "x1 / sourceWidth" in script
    assert "AbortController" in script
    assert "function selectRouteRecord" in script
    assert "function emptyStateMarkup" in script
    assert "data-route-index" in script

    style_response = client.get("/static/styles.css")
    assert style_response.status_code == 200
    style = style_response.text
    normalized_style = style.replace("\r\n", "\n")
    assert ".portrait-frame img" in style
    assert "object-fit: contain" in style
    assert "object-position: center center" in style
    assert ".target-frame img" in style
    assert "position: absolute" in style
    assert "inset: 8px" in style
    assert "width: calc(100% - 16px)" in style
    assert "height: calc(100% - 16px)" in style
    assert ".query-face-layer" in style
    assert ".face-box.is-pending" in style
    assert ".face-box.is-selected" in style
    assert ".frame-image-wrap" in style
    assert ".result-face-box" in style
    assert ".result-face-box .face-score-label" in style
    assert ".result-face-box.is-label-below .face-score-label" in style
    assert ".query-face-modal" in style
    assert ".upload-preview-action" in style
    assert "min-width: 0" in style
    assert ".face-box.is-low-confidence" in style
    assert ".mini-face img" in style
    assert ".scene-frame" in style
    assert "min-width: 0" in style
    assert "width: calc(100vw" in style
    assert ".result-screen," in style
    assert "grid-template-areas:" in style
    assert ".result-record-strip" in style
    assert "grid-auto-flow: row" in style
    assert "grid-auto-flow: column" in style
    assert "max-height: clamp(240px, calc(100vh - 430px), 520px)" in style
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
    assert ".media-viewer" in style
    assert ".media-viewer-frame img" in style
    assert ".media-viewer-frame .frame-image-wrap" in style
    assert ".empty-state" in style
    assert ".map-point.is-active" in style
    assert ".timeline-row.is-active" in style
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
    assert ".scene-frame,\n.media-frame-image { width: 100%; height: 100%; object-fit: contain" in normalized_style
    assert ".scene-frame { position: absolute; inset: 0; }" in style
    assert ".desktop-update" in style
    assert ".toast-success" in style
    assert ".toast-warning" in style
    assert ".toast-error" in style
    assert ".toast-loading" in style
    assert "[data-state=\"busy\"]" in style
    assert ".ui-icon" in style
    assert "stroke: currentColor" in style
    assert "background-image: url(\"/static/icons/search-action.png\")" not in style
    assert "min-width: 38px" not in style
    assert "min-height: 30px" not in style
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
    assert "mediaViewerTitle" in page
    assert "mediaViewerFrame" in page
    assert "queryFaceModal" in page
    assert "queryFaceModalFrame" in page
    assert "queryFaceModalConfirm" in page
    assert "openQueryFaceModalBtn" in page
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
    assert "STATIC_ASSET_VERSION = \"v0.1.37-ui\"" in main_script
    assert "asset=${encodeURIComponent(STATIC_ASSET_VERSION)}" in main_script
    assert "clearCache()" in main_script
    assert "swallowTunnelNetworkError" in main_script
    assert "prepareBackendPort" in main_script
    assert "existingBackendMatchesCurrentBuild" in main_script
    assert "getAvailablePort" in main_script
    assert "GKGUARD_PORT: String(activeBackendPort)" in main_script
    assert "ipcMain.handle(\"gkguard:check-for-updates\"" in main_script
    assert "ipcMain.handle(\"gkguard:install-update\"" in main_script
    assert "ipcMain.handle(\"gkguard:connect-c1\"" in main_script
    assert "C1_CANDIDATE_URLS: process.env.C1_CANDIDATE_URLS || DEFAULT_C1_TUNNEL_URL" in main_script
    assert "DEFAULT_C1_DIRECT_URL" not in main_script
    assert "hostHash: \"sha256\"" in main_script
    assert "hostVerifier" in main_script
    assert "hostFingerprint: \"SHA256:5JuxVHVX533OdD54f7RQFzUPeoHT2JhSy6oXnTIBl2w\"" in main_script
    assert "readyTimeout: 20000" in main_script
    assert "未配置 SSH 主机密钥固定指纹" in main_script
    assert "approvedFingerprint" not in main_script
    assert "connectWithPassword(submittedPassword, sendProgress, modal)" in main_script
    assert "return Boolean(status?.selectedBaseUrl)" in main_script
    assert "confirmSshHostKey" not in main_script
    assert "isC1TunnelConnected" in main_script
    assert "waitForC1TunnelReady" in main_script
    assert "probeC1Endpoint" in main_script
    assert 'reachable: health.status === "fulfilled"' in main_script
    assert 'if (endpointStatus.healthOk)' in main_script
    assert 'return { connected: true, verified: true, status: endpointStatus }' in main_script
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


def test_c1_proxy_api_key_prefers_campusvision_api_key(monkeypatch) -> None:
    monkeypatch.setenv("CAMPUSVISION_API_KEY", "primary-token")
    monkeypatch.setenv("C1_API_KEY", "fallback-token")

    from app.services import c1_service

    try:
        reloaded = importlib.reload(c1_service)
        assert reloaded.C1_API_KEY == "primary-token"
    finally:
        monkeypatch.delenv("CAMPUSVISION_API_KEY", raising=False)
        monkeypatch.delenv("C1_API_KEY", raising=False)
        importlib.reload(c1_service)


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
    assert body["baseUrl"] == "http://127.0.0.1:9"
    assert body["reachable"] is False
    assert body["selectedBaseUrl"] is None


def test_c1_status_selects_first_healthy_candidate(monkeypatch) -> None:
    from app.services import c1_service

    def fake_status_for_url(base_url: str):
        return {
            "baseUrl": base_url,
            "reachable": base_url == "https://c1.example.test",
            "healthOk": base_url == "https://c1.example.test",
            "identityOk": base_url == "https://c1.example.test",
        }

    monkeypatch.setattr(c1_service, "_selected_base_url", None)
    monkeypatch.delenv("C1_BASE_URL", raising=False)
    monkeypatch.delenv("C1_CONFIG_PATH", raising=False)
    monkeypatch.setenv("C1_ALLOWED_HOSTS", "127.0.0.1,c1.example.test")
    monkeypatch.setenv("C1_CANDIDATE_URLS", "http://127.0.0.1:9,https://c1.example.test")
    monkeypatch.setattr(c1_service, "_status_for_url", fake_status_for_url)

    response = client.get("/c1/status")
    assert response.status_code == 200
    body = response.json()
    assert body["selectedBaseUrl"] == "https://c1.example.test"
    assert body["candidateUrls"][:2] == ["http://127.0.0.1:9", "https://c1.example.test"]


def test_c1_request_retries_tunnel_after_retryable_http_status(monkeypatch) -> None:
    from app.services import c1_service

    attempts = []

    class FakeResponse:
        def json(self):
            return {"ok": True}

    def fake_status_for_url(base_url: str):
        return {"baseUrl": base_url, "reachable": True, "healthOk": True, "identityOk": True}

    def fake_request_once(base_url: str, method: str, path: str, **kwargs):
        attempts.append(base_url)
        if base_url == "https://c1.example.test":
            request = httpx.Request(method, f"{base_url}{path}")
            response = httpx.Response(503, request=request)
            raise httpx.HTTPStatusError("Service unavailable", request=request, response=response)
        return FakeResponse()

    monkeypatch.setattr(c1_service, "_selected_base_url", None)
    monkeypatch.delenv("C1_BASE_URL", raising=False)
    monkeypatch.setenv("C1_ALLOWED_HOSTS", "127.0.0.1,c1.example.test")
    monkeypatch.setenv("C1_CANDIDATE_URLS", "https://c1.example.test,http://127.0.0.1:18000")
    monkeypatch.setattr(c1_service, "_status_for_url", fake_status_for_url)
    monkeypatch.setattr(c1_service, "_request_once", fake_request_once)

    response = c1_service._request("POST", "/api/v1/search/person-by-image")

    assert response.json() == {"ok": True}
    assert attempts[:2] == ["https://c1.example.test", "http://127.0.0.1:18000"]
    assert c1_service._selected_base_url == "http://127.0.0.1:18000"


def test_c1_fetch_media_uses_in_memory_cache(monkeypatch) -> None:
    from app.services import c1_service

    request_paths = []

    class FakeResponse:
        content = b"frame-bytes"
        headers = {"content-type": "image/jpeg"}

    def fake_status_for_url(base_url: str):
        return {"baseUrl": base_url, "reachable": True, "healthOk": True, "identityOk": True}

    def fake_request_once(base_url: str, method: str, path: str, **kwargs):
        request_paths.append(path)
        return FakeResponse()

    monkeypatch.setattr(c1_service, "_selected_base_url", None)
    monkeypatch.setattr(c1_service, "C1_BASE_URL", "http://127.0.0.1:18000")
    monkeypatch.setattr(c1_service, "_status_for_url", fake_status_for_url)
    monkeypatch.setattr(c1_service, "_request_once", fake_request_once)
    monkeypatch.setattr(c1_service, "C1_MEDIA_CACHE_TTL", 300)

    first = c1_service.fetch_media("frame", "face-1")
    second = c1_service.fetch_media("frame", "face-1")

    assert first == (b"frame-bytes", "image/jpeg")
    assert second == first
    assert request_paths == ["/api/v1/media/frame/face-1"]


def test_c1_fetch_media_cache_is_scoped_by_base_url(monkeypatch) -> None:
    from app.services import c1_service

    request_base_urls = []
    payloads = {
        "http://127.0.0.1:18000": b"frame-from-first-c1",
        "http://127.0.0.1:18001": b"frame-from-second-c1",
    }

    class FakeResponse:
        headers = {"content-type": "image/jpeg"}

        def __init__(self, content: bytes):
            self.content = content

    def fake_status_for_url(base_url: str):
        return {"baseUrl": base_url, "reachable": True, "healthOk": True, "identityOk": True}

    def fake_request_once(base_url: str, method: str, path: str, **kwargs):
        request_base_urls.append(base_url)
        return FakeResponse(payloads[base_url])

    monkeypatch.setattr(c1_service, "C1_BASE_URL", "http://127.0.0.1:18000")
    monkeypatch.delenv("C1_BASE_URL", raising=False)
    monkeypatch.setenv("C1_CANDIDATE_URLS", "http://127.0.0.1:18000,http://127.0.0.1:18001")
    monkeypatch.setenv("C1_ALLOWED_HOSTS", "127.0.0.1")
    monkeypatch.setattr(c1_service, "_status_for_url", fake_status_for_url)
    monkeypatch.setattr(c1_service, "_request_once", fake_request_once)
    monkeypatch.setattr(c1_service, "C1_MEDIA_CACHE_TTL", 300)

    c1_service._selected_base_url = "http://127.0.0.1:18000"
    first = c1_service.fetch_media("frame", "face-1")
    c1_service._selected_base_url = "http://127.0.0.1:18001"
    second = c1_service.fetch_media("frame", "face-1")

    assert first == (b"frame-from-first-c1", "image/jpeg")
    assert second == (b"frame-from-second-c1", "image/jpeg")
    assert request_base_urls == ["http://127.0.0.1:18000", "http://127.0.0.1:18001"]


def test_c1_fetch_media_cache_write_does_not_use_competing_selected_base_url(monkeypatch) -> None:
    from app.services import c1_service

    response_base_url = "http://127.0.0.1:18000"
    competing_base_url = "http://127.0.0.1:18001"

    class FakeResponse:
        content = b"response-frame"
        headers = {"content-type": "image/jpeg"}

    def fake_status_for_url(base_url: str):
        return {"baseUrl": base_url, "reachable": True, "healthOk": True, "identityOk": True}

    def fake_request_once(base_url: str, method: str, path: str, **kwargs):
        assert base_url == response_base_url
        c1_service._selected_base_url = competing_base_url
        return FakeResponse()

    monkeypatch.setattr(c1_service, "C1_BASE_URL", response_base_url)
    monkeypatch.delenv("C1_BASE_URL", raising=False)
    monkeypatch.setenv("C1_CANDIDATE_URLS", response_base_url)
    monkeypatch.setenv("C1_ALLOWED_HOSTS", "127.0.0.1")
    monkeypatch.setattr(c1_service, "_status_for_url", fake_status_for_url)
    monkeypatch.setattr(c1_service, "_request_once", fake_request_once)
    monkeypatch.setattr(c1_service, "C1_MEDIA_CACHE_TTL", 300)

    media = c1_service.fetch_media("frame", "face-1")

    competing_key = c1_service._media_cache_key(competing_base_url, "frame", "face-1")
    assert media == (b"response-frame", "image/jpeg")
    assert competing_key not in c1_service._media_cache


def test_c1_fetch_media_skips_cache_when_generation_changes_during_request(monkeypatch) -> None:
    from app.services import c1_service

    base_url = "http://127.0.0.1:18000"
    replacement_url = "http://127.0.0.1:18001"

    class FakeResponse:
        content = b"stale-in-flight-frame"
        headers = {"content-type": "image/jpeg"}

    def fake_status_for_url(url: str):
        return {"baseUrl": url, "reachable": True, "healthOk": True, "identityOk": True}

    def fake_request_once(base_url_arg: str, method: str, path: str, **kwargs):
        assert base_url_arg == base_url
        c1_service._set_selected_base_url(replacement_url, invalidate_media=True)
        return FakeResponse()

    monkeypatch.setattr(c1_service, "C1_BASE_URL", base_url)
    monkeypatch.delenv("C1_BASE_URL", raising=False)
    monkeypatch.delenv("C1_CANDIDATE_URLS", raising=False)
    monkeypatch.setenv("C1_ALLOWED_HOSTS", "127.0.0.1")
    monkeypatch.setattr(c1_service, "_status_for_url", fake_status_for_url)
    monkeypatch.setattr(c1_service, "_request_once", fake_request_once)
    monkeypatch.setattr(c1_service, "C1_MEDIA_CACHE_TTL", 300)
    c1_service._set_selected_base_url(base_url)
    generation_before = c1_service._connection_generation

    media = c1_service.fetch_media("frame", "face-1")

    assert media == (b"stale-in-flight-frame", "image/jpeg")
    assert c1_service._connection_generation == generation_before + 1
    assert c1_service._selected_base_url == replacement_url
    assert not c1_service._media_cache
    assert c1_service._media_cache_total_bytes == 0


def test_c1_fetch_media_failover_preserves_successful_fallback_cache(monkeypatch) -> None:
    from app.services import c1_service

    first_url = "http://127.0.0.1:18000"
    fallback_url = "http://127.0.0.1:18001"
    request_base_urls = []

    class FakeResponse:
        content = b"fallback-frame"
        headers = {"content-type": "image/jpeg"}

    def fake_status_for_url(url: str):
        return {"baseUrl": url, "reachable": True, "healthOk": True, "identityOk": True}

    def fake_request_once(base_url_arg: str, method: str, path: str, **kwargs):
        request_base_urls.append(base_url_arg)
        if base_url_arg == first_url:
            request = httpx.Request(method, f"{base_url_arg}{path}")
            response = httpx.Response(503, request=request)
            raise httpx.HTTPStatusError("Service unavailable", request=request, response=response)
        return FakeResponse()

    monkeypatch.setattr(c1_service, "C1_BASE_URL", first_url)
    monkeypatch.delenv("C1_BASE_URL", raising=False)
    monkeypatch.setenv("C1_CANDIDATE_URLS", f"{first_url},{fallback_url}")
    monkeypatch.setenv("C1_ALLOWED_HOSTS", "127.0.0.1")
    monkeypatch.setattr(c1_service, "_status_for_url", fake_status_for_url)
    monkeypatch.setattr(c1_service, "_request_once", fake_request_once)
    monkeypatch.setattr(c1_service, "C1_MEDIA_CACHE_TTL", 300)
    c1_service._set_selected_base_url(first_url)

    first = c1_service.fetch_media("frame", "face-1")
    second = c1_service.fetch_media("frame", "face-1")

    assert first == (b"fallback-frame", "image/jpeg")
    assert second == first
    assert request_base_urls == [first_url, fallback_url]
    assert c1_service._selected_base_url == fallback_url
    assert len(c1_service._media_cache) == 1


def test_c1_fetch_media_retries_when_generation_changes_during_resolve(monkeypatch) -> None:
    from app.services import c1_service

    stale_url = "http://127.0.0.1:18000"
    replacement_url = "http://127.0.0.1:18001"
    status_calls = []
    request_base_urls = []

    class FakeResponse:
        content = b"replacement-frame"
        headers = {"content-type": "image/jpeg"}

    def fake_status_for_url(url: str):
        status_calls.append(url)
        if url == stale_url and len(status_calls) == 1:
            c1_service._set_selected_base_url(replacement_url, invalidate_media=True)
        return {"baseUrl": url, "reachable": True, "healthOk": True, "identityOk": True}

    def fake_request_once(base_url_arg: str, method: str, path: str, **kwargs):
        request_base_urls.append(base_url_arg)
        return FakeResponse()

    monkeypatch.setattr(c1_service, "C1_BASE_URL", stale_url)
    monkeypatch.delenv("C1_BASE_URL", raising=False)
    monkeypatch.setenv("C1_CANDIDATE_URLS", f"{stale_url},{replacement_url}")
    monkeypatch.setenv("C1_ALLOWED_HOSTS", "127.0.0.1")
    monkeypatch.setattr(c1_service, "_status_for_url", fake_status_for_url)
    monkeypatch.setattr(c1_service, "_request_once", fake_request_once)
    monkeypatch.setattr(c1_service, "C1_MEDIA_CACHE_TTL", 300)
    c1_service._set_selected_base_url(stale_url)

    media = c1_service.fetch_media("frame", "face-1")

    assert media == (b"replacement-frame", "image/jpeg")
    assert request_base_urls == [replacement_url]
    assert c1_service._selected_base_url == replacement_url
    assert len(c1_service._media_cache) == 1


def test_c1_fetch_media_does_not_rebind_resolved_url_to_new_generation(monkeypatch) -> None:
    from app.services import c1_service

    stale_url = "http://127.0.0.1:18000"
    replacement_url = "http://127.0.0.1:18001"
    request_base_urls = []
    original_resolve_base_url_state = c1_service._resolve_base_url_state
    original_media_cache_key = c1_service._media_cache_key
    resolved_once = False
    switched = False

    class FakeResponse:
        content = b"stale-after-resolve-frame"
        headers = {"content-type": "image/jpeg"}

    def fake_status_for_url(url: str):
        return {"baseUrl": url, "reachable": True, "healthOk": True, "identityOk": True}

    def fake_resolve_base_url_state(required_generation=None):
        nonlocal resolved_once
        result = original_resolve_base_url_state(required_generation)
        resolved_once = True
        return result

    def fake_media_cache_key(base_url: str, kind: str, face_id: str, candidate_urls=None, generation=None):
        nonlocal switched
        if resolved_once and not switched and base_url == stale_url and generation == initial_generation:
            switched = True
            c1_service._set_selected_base_url(replacement_url, invalidate_media=True)
        return original_media_cache_key(base_url, kind, face_id, candidate_urls, generation)

    def fake_request_once(base_url_arg: str, method: str, path: str, **kwargs):
        request_base_urls.append(base_url_arg)
        return FakeResponse()

    monkeypatch.setattr(c1_service, "C1_BASE_URL", stale_url)
    monkeypatch.delenv("C1_BASE_URL", raising=False)
    monkeypatch.setenv("C1_CANDIDATE_URLS", f"{stale_url},{replacement_url}")
    monkeypatch.setenv("C1_ALLOWED_HOSTS", "127.0.0.1")
    monkeypatch.setattr(c1_service, "_status_for_url", fake_status_for_url)
    monkeypatch.setattr(c1_service, "_resolve_base_url_state", fake_resolve_base_url_state)
    monkeypatch.setattr(c1_service, "_media_cache_key", fake_media_cache_key)
    monkeypatch.setattr(c1_service, "_request_once", fake_request_once)
    monkeypatch.setattr(c1_service, "C1_MEDIA_CACHE_TTL", 300)
    c1_service._set_selected_base_url(stale_url)
    initial_generation = c1_service._connection_generation

    media = c1_service.fetch_media("frame", "face-1")

    assert media == (b"stale-after-resolve-frame", "image/jpeg")
    assert request_base_urls == [stale_url]
    assert c1_service._selected_base_url == replacement_url
    assert not c1_service._media_cache


def test_c1_status_probe_evicts_stale_healthy_cache(monkeypatch) -> None:
    from app.services import c1_service

    base_url = "http://127.0.0.1:18000"

    def fake_status_for_url(url: str):
        return {"baseUrl": url, "reachable": True, "healthOk": False, "identityOk": False}

    monkeypatch.setattr(c1_service, "C1_BASE_URL", base_url)
    monkeypatch.delenv("C1_BASE_URL", raising=False)
    monkeypatch.delenv("C1_CANDIDATE_URLS", raising=False)
    monkeypatch.setenv("C1_ALLOWED_HOSTS", "127.0.0.1")
    monkeypatch.setattr(c1_service, "C1_STATUS_CACHE_TTL", 15)
    monkeypatch.setattr(c1_service, "_status_for_url", fake_status_for_url)
    c1_service._status_cache[base_url] = (
        time.monotonic() + 15,
        {"baseUrl": base_url, "reachable": True, "healthOk": True, "identityOk": True},
    )

    status = c1_service.get_status()

    assert status["selectedBaseUrl"] is None
    assert base_url not in c1_service._status_cache


def test_c1_fetch_media_returns_valid_cache_before_status_probe(monkeypatch) -> None:
    from app.services import c1_service

    base_url = "http://127.0.0.1:18000"

    def fail_resolve_base_url():
        raise AssertionError("cached media should be returned before status probing")

    monkeypatch.setattr(c1_service, "C1_BASE_URL", base_url)
    monkeypatch.delenv("C1_BASE_URL", raising=False)
    monkeypatch.delenv("C1_CANDIDATE_URLS", raising=False)
    monkeypatch.setenv("C1_ALLOWED_HOSTS", "127.0.0.1")
    monkeypatch.setattr(c1_service, "C1_MEDIA_CACHE_TTL", 300)
    monkeypatch.setattr(c1_service, "_resolve_base_url", fail_resolve_base_url)
    c1_service._selected_base_url = base_url
    cache_key = c1_service._media_cache_key(base_url, "frame", "face-1")
    c1_service._media_cache[cache_key] = (
        time.monotonic() + 300,
        b"cached-frame",
        "image/jpeg",
        len(b"cached-frame"),
    )
    c1_service._media_cache_total_bytes = len(b"cached-frame")

    media = c1_service.fetch_media("frame", "face-1")

    assert media == (b"cached-frame", "image/jpeg")


def test_c1_fetch_media_cache_is_scoped_by_api_key(monkeypatch) -> None:
    from app.services import c1_service

    request_count = 0

    class FakeResponse:
        headers = {"content-type": "image/jpeg"}

        def __init__(self, content: bytes):
            self.content = content

    def fake_status_for_url(base_url: str):
        return {"baseUrl": base_url, "reachable": True, "healthOk": True, "identityOk": True}

    def fake_request_once(base_url: str, method: str, path: str, **kwargs):
        nonlocal request_count
        request_count += 1
        return FakeResponse(f"frame-{request_count}".encode("utf-8"))

    monkeypatch.setattr(c1_service, "C1_BASE_URL", "http://127.0.0.1:18000")
    monkeypatch.delenv("C1_BASE_URL", raising=False)
    monkeypatch.delenv("C1_CANDIDATE_URLS", raising=False)
    monkeypatch.setenv("C1_ALLOWED_HOSTS", "127.0.0.1")
    monkeypatch.setattr(c1_service, "_status_for_url", fake_status_for_url)
    monkeypatch.setattr(c1_service, "_request_once", fake_request_once)
    monkeypatch.setattr(c1_service, "C1_MEDIA_CACHE_TTL", 300)

    monkeypatch.setattr(c1_service, "C1_API_KEY", "first-key")
    first = c1_service.fetch_media("frame", "face-1")
    monkeypatch.setattr(c1_service, "C1_API_KEY", "second-key")
    second = c1_service.fetch_media("frame", "face-1")

    assert first == (b"frame-1", "image/jpeg")
    assert second == (b"frame-2", "image/jpeg")
    assert request_count == 2


def test_c1_fetch_media_cache_is_scoped_by_candidate_config(monkeypatch) -> None:
    from app.services import c1_service

    request_count = 0

    class FakeResponse:
        headers = {"content-type": "image/jpeg"}

        def __init__(self, content: bytes):
            self.content = content

    def fake_status_for_url(base_url: str):
        return {"baseUrl": base_url, "reachable": True, "healthOk": True, "identityOk": True}

    def fake_request_once(base_url: str, method: str, path: str, **kwargs):
        nonlocal request_count
        request_count += 1
        return FakeResponse(f"candidate-frame-{request_count}".encode("utf-8"))

    monkeypatch.setattr(c1_service, "C1_BASE_URL", "http://127.0.0.1:18000")
    monkeypatch.delenv("C1_BASE_URL", raising=False)
    monkeypatch.setenv("C1_ALLOWED_HOSTS", "127.0.0.1")
    monkeypatch.setenv("C1_CANDIDATE_URLS", "http://127.0.0.1:18000")
    monkeypatch.setattr(c1_service, "_status_for_url", fake_status_for_url)
    monkeypatch.setattr(c1_service, "_request_once", fake_request_once)
    monkeypatch.setattr(c1_service, "C1_MEDIA_CACHE_TTL", 300)

    first = c1_service.fetch_media("frame", "face-1")
    monkeypatch.setenv("C1_CANDIDATE_URLS", "http://127.0.0.1:18000,http://127.0.0.1:18001")
    second = c1_service.fetch_media("frame", "face-1")

    assert first == (b"candidate-frame-1", "image/jpeg")
    assert second == (b"candidate-frame-2", "image/jpeg")
    assert request_count == 2


def test_c1_fetch_media_skips_oversized_cache_items(monkeypatch) -> None:
    from app.services import c1_service

    request_count = 0

    class FakeResponse:
        content = b"large-frame"
        headers = {"content-type": "image/jpeg"}

    def fake_status_for_url(base_url: str):
        return {"baseUrl": base_url, "reachable": True, "healthOk": True, "identityOk": True}

    def fake_request_once(base_url: str, method: str, path: str, **kwargs):
        nonlocal request_count
        request_count += 1
        return FakeResponse()

    monkeypatch.setattr(c1_service, "_selected_base_url", None)
    monkeypatch.setattr(c1_service, "C1_BASE_URL", "http://127.0.0.1:18000")
    monkeypatch.setattr(c1_service, "_status_for_url", fake_status_for_url)
    monkeypatch.setattr(c1_service, "_request_once", fake_request_once)
    monkeypatch.setattr(c1_service, "C1_MEDIA_CACHE_TTL", 300)
    monkeypatch.setattr(c1_service, "C1_MEDIA_CACHE_MAX_ITEM_BYTES", len(FakeResponse.content) - 1)

    first = c1_service.fetch_media("frame", "large-face")
    second = c1_service.fetch_media("frame", "large-face")

    assert first == (b"large-frame", "image/jpeg")
    assert second == first
    assert request_count == 2
    assert not c1_service._media_cache


def test_c1_status_revalidation_clears_same_url_media_cache(monkeypatch) -> None:
    from app.services import c1_service

    base_url = "http://127.0.0.1:18000"

    def fake_status_for_url(url: str):
        return {"baseUrl": url, "reachable": True, "healthOk": True, "identityOk": True}

    monkeypatch.setattr(c1_service, "C1_BASE_URL", base_url)
    monkeypatch.delenv("C1_BASE_URL", raising=False)
    monkeypatch.delenv("C1_CANDIDATE_URLS", raising=False)
    monkeypatch.setenv("C1_ALLOWED_HOSTS", "127.0.0.1")
    monkeypatch.setattr(c1_service, "_status_for_url", fake_status_for_url)
    c1_service._selected_base_url = base_url
    cache_key = c1_service._media_cache_key(base_url, "frame", "face-1")
    c1_service._media_cache[cache_key] = (
        time.monotonic() + 300,
        b"old-frame",
        "image/jpeg",
        len(b"old-frame"),
    )
    c1_service._media_cache_total_bytes = len(b"old-frame")
    generation_before = c1_service._connection_generation

    status = c1_service.get_status()

    assert status["selectedBaseUrl"] == base_url
    assert c1_service._connection_generation == generation_before + 1
    assert not c1_service._media_cache
    assert c1_service._media_cache_total_bytes == 0


def test_c1_media_requests_reuse_cached_status_probe(monkeypatch) -> None:
    from app.services import c1_service

    status_calls = []

    class FakeResponse:
        content = b"frame-bytes"
        headers = {"content-type": "image/jpeg"}

    def fake_status_for_url(base_url: str):
        status_calls.append(base_url)
        return {"baseUrl": base_url, "reachable": True, "healthOk": True, "identityOk": True}

    def fake_request_once(base_url: str, method: str, path: str, **kwargs):
        return FakeResponse()

    monkeypatch.setattr(c1_service, "_selected_base_url", None)
    monkeypatch.setattr(c1_service, "C1_BASE_URL", "http://127.0.0.1:18000")
    monkeypatch.setattr(c1_service, "_status_for_url", fake_status_for_url)
    monkeypatch.setattr(c1_service, "_request_once", fake_request_once)
    monkeypatch.setattr(c1_service, "C1_STATUS_CACHE_TTL", 15)
    monkeypatch.setattr(c1_service, "C1_MEDIA_CACHE_TTL", 300)

    c1_service.fetch_media("frame", "face-1")
    c1_service.fetch_media("frame", "face-2")

    assert status_calls == ["http://127.0.0.1:18000"]


def test_c1_candidate_urls_reads_config_file(monkeypatch, tmp_path) -> None:
    from app.services import c1_service

    config_path = tmp_path / "c1-connection.json"
    config_path.write_text('{"candidateUrls":["https://c1.example.test","http://127.0.0.1:18000"]}', encoding="utf-8")
    monkeypatch.delenv("C1_BASE_URL", raising=False)
    monkeypatch.delenv("C1_CANDIDATE_URLS", raising=False)
    monkeypatch.setenv("C1_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("C1_ALLOWED_HOSTS", "127.0.0.1,c1.example.test")
    monkeypatch.setattr(c1_service, "C1_BASE_URL", "http://127.0.0.1:18000")

    urls = c1_service._candidate_urls()
    assert urls == ["https://c1.example.test", "http://127.0.0.1:18000"]


def test_c1_candidate_urls_include_loopback_default(monkeypatch) -> None:
    from app.services import c1_service

    monkeypatch.delenv("C1_BASE_URL", raising=False)
    monkeypatch.delenv("C1_CANDIDATE_URLS", raising=False)
    monkeypatch.delenv("C1_CONFIG_PATH", raising=False)
    monkeypatch.setattr(c1_service, "C1_BASE_URL", "http://127.0.0.1:18000")

    urls = c1_service._candidate_urls()
    assert urls == ["http://127.0.0.1:18000"]


def test_c1_candidate_urls_fail_closed_when_disallowed(monkeypatch) -> None:
    from app.services import c1_service

    monkeypatch.delenv("C1_BASE_URL", raising=False)
    monkeypatch.delenv("C1_CANDIDATE_URLS", raising=False)
    monkeypatch.delenv("C1_CONFIG_PATH", raising=False)
    monkeypatch.setenv("C1_ALLOWED_HOSTS", "c1.example.test")
    monkeypatch.setattr(c1_service, "C1_BASE_URL", "http://127.0.0.1:18000")

    assert c1_service._candidate_urls() == []
    response = client.get("/c1/status")
    assert response.status_code == 200
    body = response.json()
    assert body["selectedBaseUrl"] is None
    assert body["candidateUrls"] == []


def test_c1_status_requires_campusvision_identity(monkeypatch) -> None:
    from app.services import c1_service

    statuses = {
        "http://127.0.0.1:18000": {
            "baseUrl": "http://127.0.0.1:18000",
            "reachable": True,
            "healthOk": True,
            "identityOk": False,
        }
    }

    monkeypatch.setattr(c1_service, "_selected_base_url", None)
    monkeypatch.delenv("C1_BASE_URL", raising=False)
    monkeypatch.delenv("C1_CONFIG_PATH", raising=False)
    monkeypatch.setenv("C1_CANDIDATE_URLS", "http://127.0.0.1:18000")
    monkeypatch.setattr(c1_service, "_status_for_url", lambda base_url: statuses[base_url])

    response = client.get("/c1/status")
    assert response.status_code == 200
    body = response.json()
    assert body["selectedBaseUrl"] is None
    assert body["reachable"] is False
    assert body["candidates"][0]["identityOk"] is False


def test_c1_person_search_maps_adapter_response(monkeypatch) -> None:
    from app.services import c1_service

    def fake_search_person_by_image(**kwargs):
        assert kwargs["filename"] == "target.jpg"
        assert kwargs["query_face_index"] == 1
        return {
            "source": "c1",
            "queryFaces": [
                {
                    "index": 0,
                    "bbox": {"x1": 6, "y1": 8, "x2": 28, "y2": 38, "width": 22, "height": 30},
                },
                {
                    "index": 1,
                    "bbox": {"x1": 42, "y1": 10, "x2": 70, "y2": 44, "width": 28, "height": 34},
                },
            ],
            "selectedQueryFace": {
                "index": 1,
                "bbox": {"x1": 42, "y1": 10, "x2": 70, "y2": 44, "width": 28, "height": 34},
            },
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
                    "faceBox": {"x1": 20, "y1": 30, "x2": 68, "y2": 90, "width": 48, "height": 60},
                }
            ],
            "routePoints": [],
        }

    monkeypatch.setattr(c1_service, "search_person_by_image", fake_search_person_by_image)
    response = client.post(
        "/c1/search/person-by-image",
        params={"query_face_index": 1},
        files={"file": ("target.jpg", b"fake image", "image/jpeg")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "c1"
    assert body["queryFaces"][1]["index"] == 1
    assert body["selectedQueryFace"]["index"] == 1
    assert body["records"][0]["frameUrl"] == "/c1/media/frame/face-1"
    assert body["records"][0]["faceUrl"] == "/c1/media/face/face-1"
    assert body["records"][0]["faceBox"]["width"] == 48


def test_c1_query_faces_proxy_maps_query_metadata(monkeypatch) -> None:
    from app.services import c1_service

    def fake_detect_query_faces(**kwargs):
        assert kwargs["filename"] == "target.jpg"
        return {
            "source": "c1",
            "engine": "mock-face",
            "faceCount": 2,
            "queryFaces": [
                {
                    "index": 0,
                    "score": 0.92,
                    "bbox": {
                        "x1": 8,
                        "y1": 10,
                        "x2": 36,
                        "y2": 52,
                        "width": 28,
                        "height": 42,
                        "leftPct": 8,
                        "topPct": 10,
                        "widthPct": 28,
                        "heightPct": 42,
                    },
                },
                {
                    "index": 1,
                    "score": 0.88,
                    "bbox": {
                        "x1": 44,
                        "y1": 14,
                        "x2": 72,
                        "y2": 56,
                        "width": 28,
                        "height": 42,
                        "leftPct": 44,
                        "topPct": 14,
                        "widthPct": 28,
                        "heightPct": 42,
                    },
                },
            ],
        }

    monkeypatch.setattr(c1_service, "detect_query_faces", fake_detect_query_faces)
    response = client.post(
        "/c1/query-faces",
        files={"file": ("target.jpg", b"fake image", "image/jpeg")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["faceCount"] == 2
    assert body["queryFaces"][0]["bbox"]["leftPct"] == 8
    assert body["queryFaces"][1]["score"] == 0.88


def test_static_assets_avoid_c1_xss_sinks() -> None:
    script_response = client.get("/static/app.js")
    assert script_response.status_code == 200
    script = script_response.text
    assert "function safeImageUrl" in script
    assert "new URL(raw, window.location.origin)" in script
    assert "function renderTargetPortrait" in script
    assert "image.src = safeUrl" in script
    assert 'src="${portraitUrl}"' not in script
    assert 'src="${uploadedImageUrl}"' not in script
    assert 'querySelector(".scene-time").textContent' in script
    assert 'querySelector(".scene-time").innerHTML = record.fullTime.replace' not in script


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
            "bbox": {"x1": 12, "y1": 18, "x2": 42, "y2": 58, "score": 0.97},
        },
        1,
    )

    assert record["frameUrl"] == "/c1/media/frame/face-1"
    assert record["faceUrl"] == "/c1/media/face/face-1"
    assert record["faceBox"]["width"] == 30
    assert record["faceBox"]["score"] == 0.97


def test_c1_record_mapping_accepts_normalized_face_box(monkeypatch) -> None:
    from app.services import c1_service

    monkeypatch.setattr(c1_service, "_selected_base_url", "http://127.0.0.1:18000")
    record = c1_service._record_from_match(
        {
            "face_id": "face-normalized",
            "frame_url": "/api/v1/media/frame/face-normalized",
            "captured_at": "2026-06-14T10:00:00",
            "camera_id": "cam02",
            "score": 0.91,
            "frame_width": 200,
            "frame_height": 100,
            "bbox": {"x1": 0.25, "y1": 0.2, "x2": 0.55, "y2": 0.7, "score": 0.97},
        },
        1,
    )

    assert record["faceBox"]["x1"] == 50
    assert record["faceBox"]["y1"] == 20
    assert record["faceBox"]["width"] == 60
    assert record["faceBox"]["height"] == 50
    assert record["faceBox"]["leftPct"] == 25
    assert record["faceBox"]["heightPct"] == 50


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
    audit_response = client.get("/audit/logs", headers=audit_headers())
    assert audit_response.status_code == 200
    assert audit_response.json()["items"][-1]["action"] == "image_search"


def test_image_search_rejects_oversized_upload() -> None:
    response = client.post(
        "/search/image",
        files={"file": ("large.jpg", b"x" * (2 * 1024 * 1024 + 1), "image/jpeg")},
    )
    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "IMAGE_TOO_LARGE"


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
    audit_response = client.get("/audit/logs", headers=audit_headers())
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
    audit_response = client.get("/audit/logs", headers=audit_headers())
    assert audit_response.json()["items"][-1]["action"] == "event_disposition_archived"


def test_audit_logs_limit() -> None:
    client.get("/events/ALT-001/report")
    client.post(
        "/events/ALT-001/disposition",
        json={"result": "confirmed_safe", "handler": "security_desk_demo", "notes": "closed in demo"},
    )
    response = client.get("/audit/logs", params={"limit": 1}, headers=audit_headers())
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["items"][0]["action"] == "event_disposition_archived"


def test_audit_logs_require_token() -> None:
    client.post(
        "/events/ALT-001/disposition",
        json={"result": "confirmed_safe", "handler": "security_desk_demo", "notes": "closed in demo"},
    )
    response = client.get("/audit/logs")
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "AUDIT_FORBIDDEN"


def test_case_package_export_requires_token() -> None:
    denied_response = client.get("/events/ALT-001/case-package")
    assert denied_response.status_code == 401
    assert denied_response.json()["detail"]["code"] == "CASE_PACKAGE_EXPORT_UNAUTHORIZED"


def test_case_package_export() -> None:
    client.get("/events/ALT-001/report")
    client.post(
        "/events/ALT-001/disposition",
        json={"result": "confirmed_safe", "handler": "security_desk_demo", "notes": "closed in demo"},
    )
    response = client.get("/events/ALT-001/case-package", headers=export_headers())
    assert response.status_code == 200
    body = response.json()
    assert body["package_id"] == "PKG-ALT-001"
    assert body["report"]["report_id"] == "RPT-ALT-001"
    assert body["subject"]["person"]["person_id"] == "P001"
    assert body["timeline_summary"]["last_location"] == "Dorm East Gate"
    assert len(body["evidence_snapshots"]) >= 5
    assert body["handoff_checklist"]

    audit_response = client.get("/audit/logs", params={"limit": 1}, headers=audit_headers())
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
