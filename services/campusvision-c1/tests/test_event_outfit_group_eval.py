from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.evaluate_event_outfit_grouping import (  # noqa: E402
    _load_manual_assignment_rows,
    _remap_assignments_to_current_events,
)
from scripts import evaluate_c1_target_metrics  # noqa: E402


def _init_eval_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE videos (
            video_id TEXT PRIMARY KEY,
            filename TEXT,
            camera_id TEXT,
            recorded_at TEXT,
            path TEXT,
            status TEXT,
            frame_interval_sec REAL
        );
        CREATE TABLE events (
            event_id TEXT PRIMARY KEY,
            camera_id TEXT NOT NULL,
            video_id TEXT,
            live_source_id TEXT,
            track_id TEXT,
            person_id TEXT,
            start_time TEXT,
            end_time TEXT,
            start_timestamp_sec REAL,
            end_timestamp_sec REAL,
            observation_count INTEGER,
            face_count INTEGER,
            representative_observation_id TEXT,
            representative_face_id TEXT,
            representative_frame_path TEXT
        );
        CREATE TABLE person_observations (
            observation_id TEXT PRIMARY KEY,
            camera_id TEXT NOT NULL,
            video_id TEXT,
            live_source_id TEXT,
            frame_index INTEGER,
            video_timestamp_sec REAL,
            captured_at TEXT,
            frame_path TEXT,
            track_id TEXT,
            body_visibility TEXT,
            person_bbox_json TEXT,
            person_detection_confidence REAL,
            face_record_id TEXT,
            person_id TEXT
        );
        CREATE TABLE event_observations (
            event_id TEXT NOT NULL,
            observation_id TEXT NOT NULL
        );
        """
    )
    conn.commit()
    conn.close()


def _insert_event_observation(
    path: Path,
    *,
    event_id: str,
    observation_id: str,
    person_id: str,
    timestamp: float,
    x1: int,
) -> None:
    bbox = {"x1": x1, "y1": 10, "x2": x1 + 20, "y2": 60}
    conn = sqlite3.connect(path)
    conn.execute(
        """
        INSERT INTO events(
            event_id, camera_id, video_id, person_id, start_timestamp_sec, end_timestamp_sec,
            observation_count, face_count, representative_observation_id
        )
        VALUES (?, 'cam_a', 'video_a', ?, ?, ?, 1, 1, ?)
        """,
        (event_id, person_id, timestamp, timestamp, observation_id),
    )
    conn.execute(
        """
        INSERT INTO person_observations(
            observation_id, camera_id, video_id, video_timestamp_sec, frame_path,
            body_visibility, person_bbox_json, person_id
        )
        VALUES (?, 'cam_a', 'video_a', ?, '/tmp/frame.jpg', 'full_body', ?, ?)
        """,
        (observation_id, timestamp, json.dumps(bbox), person_id),
    )
    conn.execute(
        "INSERT INTO event_observations(event_id, observation_id) VALUES (?, ?)",
        (event_id, observation_id),
    )
    conn.commit()
    conn.close()


def test_event_outfit_group_eval_remaps_legacy_observation_by_bbox_time(tmp_path):
    reference_db = tmp_path / "reference.sqlite3"
    current_db = tmp_path / "current.sqlite3"
    labels = tmp_path / "event_outfit_groups.json"
    _init_eval_db(reference_db)
    _init_eval_db(current_db)
    _insert_event_observation(
        reference_db,
        event_id="old_event_1",
        observation_id="old_obs_1",
        person_id="old_person",
        timestamp=1.0,
        x1=10,
    )
    _insert_event_observation(
        current_db,
        event_id="new_event_1",
        observation_id="new_obs_1",
        person_id="new_person",
        timestamp=1.0,
        x1=10,
    )
    labels.write_text(
        json.dumps(
            {
                "schema_version": "manual_event_outfit_groups_v1",
                "labels": {
                    "label_1": {
                        "person_id": "old_person",
                        "manual_assignments": [
                            {
                                "event_id": "old_event_1",
                                "observation_id": "old_obs_1",
                                "camera_id": "cam_a",
                                "time_label": "1.0s-1.0s",
                                "manual_group": "A",
                            }
                        ],
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    assignments = _load_manual_assignment_rows(labels, reference_db=reference_db)
    remap = _remap_assignments_to_current_events(assignments, current_db=current_db)

    assert remap["summary"]["matched_assignment_count"] == 1
    assert remap["assignments"][0]["remap_status"] == "matched"
    assert remap["assignments"][0]["match_strategy"] == "reference_observation_bbox_time"
    assert remap["assignments"][0]["current_event_id"] == "new_event_1"


def test_target_metrics_marks_zero_event_outfit_eval_not_replayable(tmp_path, monkeypatch):
    report_path = tmp_path / "evals" / "manual_event_outfit_groups" / "event_outfit_group_eval.json"
    report_path.parent.mkdir(parents=True)
    report_path.write_text(
        json.dumps(
            {
                "schema_version": "event_outfit_group_eval_v1",
                "events": 0,
                "pairwise": {"pair_count": 0, "f1": 0.0},
                "purity": {"purity_total": 0, "purity_accuracy": 0.0},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(evaluate_c1_target_metrics, "settings", SimpleNamespace(data_dir=tmp_path))

    report = evaluate_c1_target_metrics._outfit_grouping_report()

    assert report["status"] == "not_replayable"
    assert report["metric_available"] is False
    assert report["target_metric_eligible"] is False
    assert report["passes_f1_target"] is False
    assert report["passes_purity_target"] is False
