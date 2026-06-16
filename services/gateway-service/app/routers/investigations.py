"""Investigation query endpoints for the gateway service."""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies import get_investigation_store, require_api_key
from app.schemas import InvestigationResponse, PaginatedResponse
from app.services.investigation_service import map_investigation_to_response
from shared.contracts.interfaces.investigation_store import InvestigationFilter, InvestigationStore
from shared.domain.investigation.models import InvestigationResult

router = APIRouter(prefix="/investigations", tags=["investigations"], dependencies=[Depends(require_api_key)])


@router.get("", response_model=PaginatedResponse[InvestigationResponse])
async def list_investigations(
    incident_id: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    investigation_store: InvestigationStore = Depends(get_investigation_store),
) -> PaginatedResponse[InvestigationResponse]:
    filter = InvestigationFilter(
        incident_id=incident_id,
        limit=limit,
        offset=offset,
    )
    total = await investigation_store.count(filter)
    results = await _search_with_ids(investigation_store, filter)
    items = [map_investigation_to_response(inv_id, result) for inv_id, result in results]
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/latest", response_model=InvestigationResponse)
async def get_latest_investigation(
    investigation_store: InvestigationStore = Depends(get_investigation_store),
) -> InvestigationResponse:
    result = await investigation_store.latest()
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No investigations found")
    return map_investigation_to_response(investigation_id="", result=result)


@router.get("/{incident_id}", response_model=InvestigationResponse)
async def get_investigation_by_incident(
    incident_id: str,
    investigation_store: InvestigationStore = Depends(get_investigation_store),
) -> InvestigationResponse:
    result = await investigation_store.get_by_incident(incident_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Investigation not found for this incident",
        )
    return map_investigation_to_response(investigation_id=incident_id, result=result)


async def _search_with_ids(
    store: InvestigationStore,
    filter: InvestigationFilter,
) -> list[tuple[str, InvestigationResult]]:
    results: list[tuple[str, InvestigationResult]] = []
    async for result in store.search(filter):
        results.append(("", result))
    return results
