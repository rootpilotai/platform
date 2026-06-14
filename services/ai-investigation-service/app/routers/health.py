from fastapi import APIRouter
from pydantic import BaseModel

from app.config import InvestigationServiceConfig

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    service: str
    environment: str


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    cfg = InvestigationServiceConfig()
    return HealthResponse(
        status="healthy",
        service=cfg.service_name,
        environment=cfg.environment,
    )
