from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

from app.models import CarDispatchRequest, CarDispatchResponse


def create_mock_dispatch(request: CarDispatchRequest) -> CarDispatchResponse:
    start_time = datetime.now().replace(microsecond=0)
    end_time = start_time + timedelta(minutes=6)
    return CarDispatchResponse(
        task_id=f"TASK-{uuid4().hex[:8].upper()}",
        car_id="CAR-DEMO-01",
        event_id=request.event_id,
        route_id=request.route_id,
        location=request.target_location,
        status="arrived_mock",
        start_time=start_time.isoformat(),
        end_time=end_time.isoformat(),
        snapshot_url="/mock/car_snapshots/review_task_001.jpg",
    )
