from fastapi import APIRouter

from app.models import CarDispatchRequest, CarDispatchResponse
from app.services.car_service import create_mock_dispatch


router = APIRouter(prefix="/car-tasks", tags=["campusCar mock"])


@router.post("/mock-dispatch", response_model=CarDispatchResponse)
def mock_dispatch(request: CarDispatchRequest) -> CarDispatchResponse:
    return create_mock_dispatch(request)
