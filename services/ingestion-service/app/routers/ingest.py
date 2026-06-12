from fastapi import APIRouter, Depends

from app.dependencies import get_event_bus
from app.schemas import IngestRequest, IngestResponse
from app.services.ingestion_service import IngestionService
from shared.contracts import EventBus

router = APIRouter(tags=["ingestion"])


@router.post("/api/v1/ingest", response_model=IngestResponse, status_code=202)
async def ingest_telemetry(
    payload: IngestRequest,
    event_bus: EventBus = Depends(get_event_bus),
) -> IngestResponse:
    service = IngestionService(event_bus=event_bus)
    event_id = await service.process_telemetry(payload)
    return IngestResponse(accepted=True, event_id=event_id)
