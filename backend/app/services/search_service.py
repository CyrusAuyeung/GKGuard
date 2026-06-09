from __future__ import annotations

from datetime import datetime
from typing import Any

from app.data_store import load_data


def _contains(value: Any, expected: str | None) -> bool:
    if not expected:
        return True
    return expected.lower() in str(value or "").lower()


def _matches_any(record: dict[str, Any], fields: list[str], keyword: str | None) -> bool:
    if not keyword:
        return True
    return any(_contains(record.get(field), keyword) for field in fields)


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def search_persons(
    keyword: str | None = None,
    name: str | None = None,
    student_id: str | None = None,
    phone: str | None = None,
    email: str | None = None,
    identity_type: str | None = None,
) -> list[dict[str, Any]]:
    persons = load_data()["persons"]
    results = []
    for person in persons:
        if not _matches_any(person, ["person_id", "name", "student_id", "phone", "email"], keyword):
            continue
        if not _contains(person.get("name"), name):
            continue
        if not _contains(person.get("student_id"), student_id):
            continue
        if not _contains(person.get("phone"), phone):
            continue
        if not _contains(person.get("email"), email):
            continue
        if identity_type and person.get("identity_type") != identity_type:
            continue
        results.append(person)
    return results


def search_vehicles(
    keyword: str | None = None,
    plate_number: str | None = None,
    color: str | None = None,
    brand: str | None = None,
    vehicle_type: str | None = None,
    owner_person_id: str | None = None,
) -> list[dict[str, Any]]:
    vehicles = load_data()["vehicles"]
    results = []
    for vehicle in vehicles:
        if not _matches_any(vehicle, ["vehicle_id", "plate_number", "brand", "color", "vehicle_type"], keyword):
            continue
        if not _contains(vehicle.get("plate_number"), plate_number):
            continue
        if not _contains(vehicle.get("color"), color):
            continue
        if not _contains(vehicle.get("brand"), brand):
            continue
        if vehicle_type and vehicle.get("vehicle_type") != vehicle_type:
            continue
        if owner_person_id and vehicle.get("owner_person_id") != owner_person_id:
            continue
        results.append(vehicle)
    return results


def search_snapshots(
    person_id: str | None = None,
    vehicle_id: str | None = None,
    camera_id: str | None = None,
    location: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    min_similarity: float | None = None,
) -> list[dict[str, Any]]:
    snapshots = load_data()["snapshots"]
    cameras = {camera["camera_id"]: camera for camera in load_data()["cameras"]}
    start_dt = _parse_time(start_time)
    end_dt = _parse_time(end_time)
    results = []
    for snapshot in snapshots:
        snapshot_dt = _parse_time(snapshot["time"])
        camera = cameras.get(snapshot["camera_id"], {})
        if person_id and snapshot.get("person_id") != person_id:
            continue
        if vehicle_id and snapshot.get("vehicle_id") != vehicle_id:
            continue
        if camera_id and snapshot.get("camera_id") != camera_id:
            continue
        if location and not _contains(camera.get("location_name"), location):
            continue
        if start_dt and snapshot_dt and snapshot_dt < start_dt:
            continue
        if end_dt and snapshot_dt and snapshot_dt > end_dt:
            continue
        if min_similarity is not None and float(snapshot.get("mock_similarity", 0)) < min_similarity:
            continue
        enriched = snapshot | {
            "camera_name": camera.get("name"),
            "location": camera.get("location_name"),
            "lat": camera.get("lat"),
            "lng": camera.get("lng"),
        }
        results.append(enriched)
    return sorted(results, key=lambda item: item["time"])


def get_person_profile(person_id: str) -> dict[str, Any] | None:
    data = load_data()
    person = next((item for item in data["persons"] if item["person_id"] == person_id), None)
    if not person:
        return None
    vehicles = [item for item in data["vehicles"] if item.get("owner_person_id") == person_id]
    access_records = [item for item in data["access_records"] if item.get("person_id") == person_id]
    alerts = [item for item in data["alerts"] if item.get("person_id") == person_id]
    return {
        "person": person,
        "vehicles": vehicles,
        "snapshots": search_snapshots(person_id=person_id),
        "access_records": sorted(access_records, key=lambda item: item["time"]),
        "alerts": sorted(alerts, key=lambda item: item["time"]),
    }
