from fastapi import APIRouter

from app.models import CarDispatchRequest, CarDispatchResponse, UeBridgeStatusResponse
from app.services.car_service import create_mock_dispatch, get_ue_bridge_status


router = APIRouter(prefix="/car-tasks", tags=["campusCar mock"])


@router.post("/mock-dispatch", response_model=CarDispatchResponse)
def mock_dispatch(request: CarDispatchRequest) -> CarDispatchResponse:
    return create_mock_dispatch(request)


@router.get("/ue-bridge-status", response_model=UeBridgeStatusResponse)
def ue_bridge_status() -> UeBridgeStatusResponse:
    return get_ue_bridge_status()
