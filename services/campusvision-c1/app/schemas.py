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


class LiveSourceCreate(BaseModel):
    source_id: str = Field(..., examples=["p2l_s5_c1"])
    camera_id: str = Field(..., examples=["p2l_s5_c1"])
    name: str = Field(..., examples=["P2L S5 Camera 1"])
    source_type: str = Field("rtsp", examples=["rtsp"])
    url: str = Field(..., examples=["rtsp://127.0.0.1:8554/p2l_s5_c1"])
    location: str | None = None
    lat: float | None = None
    lng: float | None = None
    enabled: bool = True


class LiveSourceOut(LiveSourceCreate):
    created_at: str | None = None
    updated_at: str | None = None


class LiveSourceStatus(BaseModel):
    source_id: str
    camera_id: str
    reachable: bool
    source_type: str
    url: str
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    message: str | None = None


class LiveCaptureResult(BaseModel):
    source_id: str
    camera_id: str
    video: VideoOut
    indexed_faces: int | None = None
    status: str


class LiveMonitorStart(BaseModel):
    segment_sec: float = Field(10.0, ge=1.0, le=300.0)
    frame_interval_sec: float = Field(1.0, ge=0.1, le=60.0)
    update_person_index: bool = True
    person_update_interval_segments: int = Field(3, ge=1)
    retention_hours: float | None = Field(24.0, ge=0.1)
    cleanup_interval_segments: int = Field(360, ge=1)
    merge_threshold: float | None = Field(0.80, ge=0.0, le=1.0)
    person_match_threshold: float = Field(0.82, ge=0.0, le=1.0)
    min_faces: int = Field(2, ge=1)
    min_face_area: float = Field(1800.0, ge=1.0)
    min_detection_score: float = Field(0.75, ge=0.0, le=1.0)


class LiveMonitorStatus(BaseModel):
    source_id: str
    camera_id: str | None = None
    running: bool
    segment_sec: float | None = None
    frame_interval_sec: float | None = None
    update_person_index: bool | None = None
    person_update_interval_segments: int | None = None
    retention_hours: float | None = None
    cleanup_interval_segments: int | None = None
    merge_threshold: float | None = None
    person_match_threshold: float | None = None
    min_faces: int | None = None
    min_face_area: float | None = None
    min_detection_score: float | None = None
    started_at: str | None = None
    stopped_at: str | None = None
    last_capture_at: str | None = None
    last_video_id: str | None = None
    last_indexed_faces: int | None = None
    last_status: str | None = None
    last_person_update_at: str | None = None
    last_person_update_result: dict | None = None
    last_cleanup_at: str | None = None
    last_cleanup_result: dict | None = None
    processed_segments: int = 0
    failed_segments: int = 0
    last_error: str | None = None


class IndexResult(BaseModel):
    video_id: str
    indexed_faces: int
    indexed_observations: int | None = None
    detected_bodies: int | None = None
    event_result: dict | None = None
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


class PersonEventOut(BaseModel):
    event_id: str
    person_id: str
    camera_id: str
    camera_name: str | None = None
    location: str | None = None
    video_id: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    start_timestamp_sec: float | None = None
    end_timestamp_sec: float | None = None
    start_time_display: str | None = None
    end_time_display: str | None = None
    duration_sec: float | None = None
    face_count: int
    representative_face_id: str
    representative_face_crop_url: str
    representative_frame_url: str
    representative_body_crop_url: str | None = None
    body_visibility: str | None = None
    upper_color: str | None = None
    upper_color_confidence: float | None = None
    upper_visible: bool | None = None
    raw_upper_color: str | None = None
    raw_upper_color_confidence: float | None = None
    raw_upper_visible: bool | None = None
    normalized_upper_color: str | None = None
    normalized_upper_color_confidence: float | None = None
    normalized_upper_visible: bool | None = None
    appearance_session_id: str | None = None
    clothing_normalization_version: str | None = None
    clothing_normalization_reason: dict | None = None


class PersonObservationOut(BaseModel):
    observation_id: str
    camera_id: str
    video_id: str | None = None
    live_source_id: str | None = None
    frame_index: int | None = None
    video_timestamp_sec: float | None = None
    captured_at: str | None = None
    frame_path: str
    frame_url: str | None = None
    body_crop_url: str | None = None
    track_id: str | None = None
    observation_type: str
    body_visibility: str
    person_bbox: dict | None = None
    person_detection_confidence: float | None = None
    face_record_id: str | None = None
    person_id: str | None = None
    upper_color: str | None = None
    upper_color_confidence: float | None = None
    upper_visible: bool = False
    upper_valid_pixel_ratio: float | None = None
    clothing_model_version: str | None = None
    body_model_version: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class EventOut(BaseModel):
    event_id: str
    camera_id: str
    video_id: str | None = None
    live_source_id: str | None = None
    track_id: str | None = None
    person_id: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    start_timestamp_sec: float | None = None
    end_timestamp_sec: float | None = None
    observation_count: int
    face_count: int
    representative_observation_id: str | None = None
    representative_face_id: str | None = None
    representative_frame_path: str | None = None
    representative_frame_url: str | None = None
    representative_face_crop_url: str | None = None
    representative_body_crop_url: str | None = None
    body_visibility: str | None = None
    upper_color: str | None = None
    upper_color_confidence: float | None = None
    upper_visible: bool | None = None
    raw_upper_color: str | None = None
    raw_upper_color_confidence: float | None = None
    raw_upper_visible: bool | None = None
    normalized_upper_color: str | None = None
    normalized_upper_color_confidence: float | None = None
    normalized_upper_visible: bool | None = None
    appearance_session_id: str | None = None
    clothing_normalization_version: str | None = None
    clothing_normalization_reason: dict | None = None
    identity_confidence: float | None = None
    event_status: str | None = None
    aggregation_version: str | None = None
    match_score: float | None = None
    match_reasons: list[str] = Field(default_factory=list)
    created_at: str | None = None
    updated_at: str | None = None


class AppearanceSessionOut(BaseModel):
    session_id: str
    person_id: str
    start_time: str | None = None
    end_time: str | None = None
    start_timestamp_sec: float | None = None
    end_timestamp_sec: float | None = None
    event_count: int
    upper_color: str | None = None
    upper_color_confidence: float | None = None
    upper_color_support: int = 0
    upper_visible: bool | None = None
    profile: dict = Field(default_factory=dict)
    session_status: str | None = None
    aggregation_version: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class PersonOut(BaseModel):
    person_id: str
    display_name: str | None = None
    representative_face_id: str | None = None
    representative_frame_path: str | None = None
    representative_frame_url: str | None = None
    representative_face_crop_url: str | None = None
    face_count: int
    event_count: int | None = None
    observation_count: int | None = None
    last_event_id: str | None = None
    last_seen_camera_id: str | None = None
    latest_event: EventOut | None = None
    latest_clothing: dict | None = None
    events: list[PersonEventOut] = Field(default_factory=list)
    first_seen_at: str | None = None
    last_seen_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
