from pydantic import BaseModel
from fastapi import APIRouter

from app.services.ai_service import parse_natural_query


class NaturalQueryRequest(BaseModel):
    query: str


router = APIRouter(prefix="/ai", tags=["lightweight ai"])


@router.post("/parse-query")
def parse_query(request: NaturalQueryRequest) -> dict:
    return parse_natural_query(request.query)
