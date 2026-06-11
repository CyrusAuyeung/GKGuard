from pydantic import BaseModel, Field


class ApiError(BaseModel):
    code: str
    message: str


class TimelinePoint(BaseModel):
    time: str
    location: str
    camera_id: str
    camera_name: str
    lat: float
    lng: float
    image_url: str
    similarity: float | None = None
    source_type: str = "snapshot"
    source_id: str


class TimelineSummary(BaseModel):
    first_seen: str | None = None
    last_seen: str | None = None
    last_location: str | None = None
    point_count: int = 0
    camera_count: int = 0
    related_alert_count: int = 0
    duration_minutes: int | None = None


class TimelineResponse(BaseModel):
    person_id: str
    summary: TimelineSummary
    points: list[TimelinePoint]


class CarDispatchRequest(BaseModel):
    event_id: str | None = None
    target_location: str
    route_id: str = "ROUTE-DEMO-01"
    reason: str = "field_review"
    robot_id: str = "CAR-DEMO-01"
    robot_type: str = "campusCar"
    speed_mps: float = 0.8
    command_topic: str = "/U2RTopic_Command"
    position_topic: str = "/R2UTopic_Pos"
    status_topic: str = "/R2UTopic_Text"


class UeBridgeContract(BaseModel):
    integration_id: str = "ue-campuscar"
    mode: str = "mock"
    rosbridge_url: str = "ws://127.0.0.1:9090"
    command_topic: str = "/U2RTopic_Command"
    position_topic: str = "/R2UTopic_Pos"
    status_topic: str = "/R2UTopic_Text"
    video_hls_url: str = "http://127.0.0.1:8888/campuscar/index.m3u8"
    video_rtsp_url: str = "rtsp://127.0.0.1:8554/campuscar"
    notes: list[str] = Field(default_factory=list)


class CarDispatchResponse(BaseModel):
    task_id: str
    car_id: str
    event_id: str | None
    route_id: str
    location: str
    status: str
    start_time: str
    end_time: str | None = None
    snapshot_url: str | None = None
    exception_code: str | None = None
    bridge_contract: UeBridgeContract = Field(default_factory=UeBridgeContract)
    video_hls_url: str | None = "http://127.0.0.1:8888/campuscar/index.m3u8"
    video_rtsp_url: str | None = "rtsp://127.0.0.1:8554/campuscar"
    message: str = Field(default="mock campusCar task accepted")


class UeBridgeStatusResponse(BaseModel):
    integration_id: str = "ue-campuscar"
    status: str = "mock_ready"
    mode: str = "mock"
    rosbridge_url: str = "ws://127.0.0.1:9090"
    command_topic: str = "/U2RTopic_Command"
    position_topic: str = "/R2UTopic_Pos"
    status_topic: str = "/R2UTopic_Text"
    video_hls_url: str = "http://127.0.0.1:8888/campuscar/index.m3u8"
    video_rtsp_url: str = "rtsp://127.0.0.1:8554/campuscar"
    external_test_app: str = "GKD_Station_Qiyi.exe"
    notes: list[str] = Field(default_factory=list)


class EventDispositionRequest(BaseModel):
    result: str = "confirmed_safe"
    handler: str = "security_desk_demo"
    notes: str = "Subject confirmed by timeline and field review."


class EventDispositionResponse(BaseModel):
    disposition_id: str
    event_id: str
    status_before: str
    status_after: str
    result: str
    handler: str
    notes: str
    archived_at: str
    evidence_summary: dict
