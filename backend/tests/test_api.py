from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_demo_page_available() -> None:
    response = client.get("/demo")
    assert response.status_code == 200
    assert "AI Security Search Console" in response.text


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


def test_mock_car_dispatch() -> None:
    response = client.post(
        "/car-tasks/mock-dispatch",
        json={"event_id": "ALT-001", "target_location": "Dorm East Gate", "reason": "field review"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "arrived_mock"
    assert body["event_id"] == "ALT-001"


def test_natural_query_parser() -> None:
    response = client.post("/ai/parse-query", json={"query": "find red car near parking at night"})
    assert response.status_code == 200
    filters = response.json()["filters"]
    assert filters["object_type"] == "vehicle"
    assert filters["color"] == "red"
    assert filters["location"] == "Parking Lot East"
    assert filters["time_hint"] == "after_hours"
