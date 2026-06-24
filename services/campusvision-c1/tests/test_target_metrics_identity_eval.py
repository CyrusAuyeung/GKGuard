from pathlib import Path
import json
import sqlite3
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.evaluate_c1_target_metrics import _manual_person_merge_current_db_report  # noqa: E402


def _init_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE face_records (
            face_id TEXT PRIMARY KEY,
            camera_id TEXT NOT NULL,
            video_timestamp_sec REAL NOT NULL,
            bbox_json TEXT NOT NULL
        );
        CREATE TABLE person_faces (
            person_id TEXT NOT NULL,
            face_id TEXT NOT NULL
        );
        """
    )
    conn.commit()
    conn.close()


def _add_face(path: Path, face_id: str, person_id: str, camera_id: str, timestamp: float, x1: int) -> None:
    bbox = {"x1": x1, "y1": 10, "x2": x1 + 20, "y2": 40, "score": 0.9}
    conn = sqlite3.connect(path)
    conn.execute(
        "INSERT INTO face_records(face_id, camera_id, video_timestamp_sec, bbox_json) VALUES (?, ?, ?, ?)",
        (face_id, camera_id, timestamp, json.dumps(bbox)),
    )
    conn.execute(
        "INSERT INTO person_faces(person_id, face_id) VALUES (?, ?)",
        (person_id, face_id),
    )
    conn.commit()
    conn.close()


def test_current_db_manual_merge_eval_projects_reference_fragments(tmp_path):
    reference_db = tmp_path / "reference.sqlite3"
    current_db = tmp_path / "current.sqlite3"
    manual_path = tmp_path / "manual_person_merge_result.json"
    _init_db(reference_db)
    _init_db(current_db)

    manual_path.write_text(
        json.dumps(
            {
                "groups": [[1, 2], [3, 4]],
                "merge_plan": [
                    {"source_number": 2, "source_person_id": "old_b", "target_number": 1, "target_person_id": "old_a"},
                    {"source_number": 4, "source_person_id": "old_d", "target_number": 3, "target_person_id": "old_c"},
                ],
            }
        ),
        encoding="utf-8",
    )
    for index, (old_person, current_person) in enumerate(
        [
            ("old_a", "current_1"),
            ("old_b", "current_1"),
            ("old_c", "current_2"),
            ("old_d", "current_2"),
        ],
        start=1,
    ):
        face_id = f"face_{index}"
        timestamp = float(index)
        x1 = index * 30
        _add_face(reference_db, face_id, old_person, "cam_a", timestamp, x1)
        _add_face(current_db, f"current_{face_id}", current_person, "cam_a", timestamp, x1)

    report = _manual_person_merge_current_db_report(
        current_db,
        reference_db=reference_db,
        manual_result_path=manual_path,
    )

    assert report["status"] == "evaluated"
    assert report["matched_face_count"] == 4
    assert report["tp"] == 2
    assert report["fp"] == 0
    assert report["fn"] == 0
    assert report["precision"] == 1.0
    assert report["f1"] == 1.0
