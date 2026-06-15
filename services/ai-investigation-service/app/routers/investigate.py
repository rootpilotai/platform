import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from app.pipeline import InvestigationPipeline
from shared.contracts import Event, EventBus
from shared.contracts.events import EventTopic, InvestigationCompletedEvent, ServiceName
from shared.domain.incident.context.models import IncidentContext
from shared.domain.investigation.models import InvestigationResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/investigate", tags=["investigate"])


def _get_pipeline(request: Request) -> InvestigationPipeline:
    pipeline: InvestigationPipeline | None = getattr(request.app.state, "pipeline", None)
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Investigation pipeline not available")
    return pipeline


def _get_event_bus(request: Request) -> EventBus:
    event_bus: EventBus | None = getattr(request.app.state, "event_bus", None)
    if event_bus is None:
        raise HTTPException(status_code=503, detail="Event bus not available")
    return event_bus


@router.post("/run", response_model=InvestigationResult)
async def run_investigation(
    context: IncidentContext,
    pipeline: InvestigationPipeline = Depends(_get_pipeline),
    event_bus: EventBus = Depends(_get_event_bus),
) -> InvestigationResult:
    result = await pipeline.run(context)

    try:
        completed = InvestigationCompletedEvent(
            investigation_id=context.incident_id,
            incident_id=context.incident_id,
            summary=result.summary.model_dump(),
        )
        event = Event(
            source=ServiceName.INVESTIGATION,
            topic=EventTopic.INVESTIGATION_COMPLETED,
            payload=completed.model_dump(),
        )
        await event_bus.publish(event)
        logger.info("Published investigation.completed", extra={"incident_id": context.incident_id})
    except Exception:
        logger.exception("Failed to publish investigation.completed event")

    return result
