from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.config import IngestionServiceSettings
from app.dependencies import get_event_bus, get_settings
from shared.contracts import EventBus

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    service: str
    environment: str
    event_bus_connected: bool


@router.get("/health", response_model=HealthResponse)
async def health(
    settings: IngestionServiceSettings = Depends(get_settings),
    event_bus: EventBus = Depends(get_event_bus),
) -> HealthResponse:
    event_bus_ok = await event_bus.health()
    return HealthResponse(
        status="healthy" if event_bus_ok else "degraded",
        service=settings.service_name,
        environment=settings.environment,
        event_bus_connected=event_bus_ok,
    )
