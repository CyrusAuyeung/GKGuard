from fastapi.testclient import TestClient

from app.main import app
from app.services.audit_service import clear_audit_logs


client = TestClient(app)


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


def test_c1_status_handles_unavailable_service(monkeypatch) -> None:
    from app.services import c1_service

    monkeypatch.setattr(c1_service, "C1_BASE_URL", "http://127.0.0.1:9")
    response = client.get("/c1/status")
    assert response.status_code == 200
    body = response.json()
    assert body["baseUrl"] == "http://127.0.0.1:9"
    assert body["reachable"] is False


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
                    "note": "来自 C1 CampusVision 的真实检索结果",
                    "sceneClass": "scene-1",
                    "progress": 21,
                    "frameUrl": "/c1/media/frame/face-1",
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
