"""Health and metrics endpoints for the gateway service."""

from fastapi import APIRouter, Depends

from app.dependencies import get_api_key_store, get_incident_store, get_investigation_store
from app.schemas import HealthResponse
from shared.contracts.interfaces.api_key_store import ApiKeyStore
from shared.contracts.interfaces.incident_store import IncidentStore
from shared.contracts.interfaces.investigation_store import InvestigationStore

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(
    incident_store: IncidentStore = Depends(get_incident_store),
    investigation_store: InvestigationStore = Depends(get_investigation_store),
    api_key_store: ApiKeyStore = Depends(get_api_key_store),
) -> HealthResponse:
    incident_ok = await incident_store.health()
    investigation_ok = await investigation_store.health()
    api_key_ok = await api_key_store.health()
    overall = incident_ok and investigation_ok and api_key_ok
    return HealthResponse(
        status="ok" if overall else "degraded",
        incident_store=incident_ok,
        investigation_store=investigation_ok,
        api_key_store=api_key_ok,
    )


@router.get("/metrics", include_in_schema=False)
async def metrics() -> dict:
    return {"service": "gateway-service", "status": "ok"}
