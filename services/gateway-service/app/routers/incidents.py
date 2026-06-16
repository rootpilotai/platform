"""Incident query endpoints for the gateway service."""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies import get_incident_store, require_api_key
from app.schemas import IncidentResponse, PaginatedResponse
from app.services.incident_service import map_incident_to_response
from shared.contracts.interfaces.incident_store import (
    IncidentFilter,
    IncidentSortField,
    IncidentSortOrder,
    IncidentStore,
)

router = APIRouter(prefix="/incidents", tags=["incidents"], dependencies=[Depends(require_api_key)])


@router.get("", response_model=PaginatedResponse[IncidentResponse])
async def list_incidents(
    primary_service: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    incident_store: IncidentStore = Depends(get_incident_store),
) -> PaginatedResponse[IncidentResponse]:
    filter = IncidentFilter(
        primary_service=primary_service,
        severity=severity,
        limit=limit,
        offset=offset,
        sort_field=IncidentSortField.DETECTED_AT,
        sort_order=IncidentSortOrder.DESC,
    )
    total = await incident_store.count(filter)
    items = [map_incident_to_response(ctx) async for ctx in incident_store.search(filter)]
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/{incident_id}", response_model=IncidentResponse)
async def get_incident(
    incident_id: str,
    incident_store: IncidentStore = Depends(get_incident_store),
) -> IncidentResponse:
    context = await incident_store.get(incident_id)
    if context is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    return map_incident_to_response(context)
