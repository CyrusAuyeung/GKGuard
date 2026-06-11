from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

from app.models import CarDispatchRequest, CarDispatchResponse, UeBridgeContract, UeBridgeStatusResponse


def create_ue_bridge_contract(request: CarDispatchRequest | None = None) -> UeBridgeContract:
    return UeBridgeContract(
        command_topic=request.command_topic if request else "/U2RTopic_Command",
        position_topic=request.position_topic if request else "/R2UTopic_Pos",
        status_topic=request.status_topic if request else "/R2UTopic_Text",
        notes=[
            "Mock contract only; replace with a CampusCar adapter after ROS2 schemas are finalized.",
            "Do not package or launch the UE test app from GKGuard.",
        ],
    )


def create_mock_dispatch(request: CarDispatchRequest) -> CarDispatchResponse:
    start_time = datetime.now().replace(microsecond=0)
    end_time = start_time + timedelta(minutes=6)
    bridge_contract = create_ue_bridge_contract(request)
    return CarDispatchResponse(
        task_id=f"TASK-{uuid4().hex[:8].upper()}",
        car_id=request.robot_id,
        event_id=request.event_id,
        route_id=request.route_id,
        location=request.target_location,
        status="arrived_mock",
        start_time=start_time.isoformat(),
        end_time=end_time.isoformat(),
        snapshot_url="/mock/car_snapshots/review_task_001.jpg",
        bridge_contract=bridge_contract,
        video_hls_url=bridge_contract.video_hls_url,
        video_rtsp_url=bridge_contract.video_rtsp_url,
    )


def get_ue_bridge_status() -> UeBridgeStatusResponse:
    return UeBridgeStatusResponse(
        notes=[
            "UE test package contains ROSIntegration assets, but Bridge.ini is empty in the provided build.",
            "Expected control loop: C2 task -> /U2RTopic_Command -> /R2UTopic_Pos and /R2UTopic_Text feedback.",
            "This endpoint is a readiness placeholder, not a live rosbridge probe.",
        ],
    )
