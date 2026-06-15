from contextlib import suppress

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.config import NotificationServiceSettings

router = APIRouter(tags=["health"])


class ProviderHealth(BaseModel):
    name: str
    connected: bool


class HealthResponse(BaseModel):
    status: str
    service: str
    environment: str
    event_bus_connected: bool
    providers: list[ProviderHealth]


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    settings: NotificationServiceSettings = request.app.state.settings
    event_bus = getattr(request.app.state, "event_bus", None)
    router = getattr(request.app.state, "router", None)

    event_bus_healthy = False
    if event_bus is not None:
        with suppress(Exception):
            event_bus_healthy = await event_bus.health()

    provider_status = []
    if router is not None:
        provider_status = [ProviderHealth(name=name, connected=ok) for name, ok in (await router.health()).items()]

    status = "healthy" if event_bus_healthy else "degraded"

    return HealthResponse(
        status=status,
        service=settings.service_name,
        environment=settings.environment,
        event_bus_connected=event_bus_healthy,
        providers=provider_status,
    )
