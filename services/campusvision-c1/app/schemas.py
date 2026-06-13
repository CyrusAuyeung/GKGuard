from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class CameraCreate(BaseModel):
    camera_id: str = Field(..., examples=["cam_dorm_gate_01"])
    name: str = Field(..., examples=["宿舍区东门摄像头01"])
    location: Optional[str] = Field(None, examples=["宿舍区东门"])
    lat: Optional[float] = Field(None, examples=[31.0001])
    lng: Optional[float] = Field(None, examples=[121.0001])


class CameraOut(CameraCreate):
    created_at: str | None = None
    updated_at: str | None = None


class VideoOut(BaseModel):
    video_id: str
    filename: str
    camera_id: str
    recorded_at: str | None = None
    path: str
    status: str
    frame_interval_sec: float | None = None
    created_at: str | None = None
    updated_at: str | None = None


class IndexResult(BaseModel):
    video_id: str
    indexed_faces: int
    status: str


class MatchOut(BaseModel):
    face_id: str
    score: float
    camera_id: str
    camera_name: str | None = None
    location: str | None = None
    lat: float | None = None
    lng: float | None = None
    video_id: str
    video_timestamp_sec: float
    captured_at: str | None = None
    frame_url: str


class SearchResult(BaseModel):
    search_id: str
    engine: str
    matches: list[MatchOut]
    trajectory: list[dict]
    appearance_events: list[dict] = Field(default_factory=list)


class PersonIndexResult(BaseModel):
    persons: int
    linked_faces: int
    source_faces: int
    merge_threshold: float | None = None
    min_faces: int
    min_face_area: float
    min_detection_score: float
    low_quality_faces: int
    noise_faces: int
    cluster_quality: dict
    algorithm: str


class PersonOut(BaseModel):
    person_id: str
    display_name: str | None = None
    representative_face_id: str | None = None
    representative_frame_path: str | None = None
    representative_frame_url: str | None = None
    representative_face_crop_url: str | None = None
    face_count: int
    first_seen_at: str | None = None
    last_seen_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
