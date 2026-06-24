from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services import event_service  # noqa: E402
from app.storage import db  # noqa: E402


def _person_lookup() -> dict[str, str]:
    with db.get_conn() as conn:
        rows = conn.execute("SELECT face_id, person_id FROM person_faces").fetchall()
    return {row["face_id"]: row["person_id"] for row in rows}


def main() -> None:
    db.init_db()
    face_to_person = _person_lookup()
    records = db.list_face_records()
    videos: set[str] = set()
    created = 0

    for record in records:
        observation_id = f"obs_face_{record['face_id']}"
        db.add_person_observation(
            {
                "observation_id": observation_id,
                "camera_id": record["camera_id"],
                "video_id": record["video_id"],
                "live_source_id": None,
                "frame_index": None,
                "video_timestamp_sec": record.get("video_timestamp_sec"),
                "captured_at": record.get("captured_at"),
                "frame_path": record["frame_path"],
                "track_id": None,
                "observation_type": "face_only",
                "body_visibility": "face_only",
                "person_bbox": None,
                "person_detection_confidence": None,
                "face_record_id": record["face_id"],
                "person_id": face_to_person.get(record["face_id"]),
                "upper_color": "unknown",
                "upper_color_confidence": None,
                "upper_visible": False,
                "upper_valid_pixel_ratio": None,
                "lower_color": "unknown",
                "lower_color_confidence": None,
                "lower_visible": False,
                "lower_valid_pixel_ratio": None,
                "clothing_model_version": "backfill_face_only_v1",
                "body_model_version": "none",
            }
        )
        db.update_face_record_observation(record["face_id"], observation_id)
        videos.add(record["video_id"])
        created += 1

    result = event_service.rebuild_events_for_videos(videos)
    print(
        {
            "face_records": len(records),
            "observations_upserted": created,
            "videos_rebuilt": result["videos"],
            "events": result["events"],
        }
    )


if __name__ == "__main__":
    main()
