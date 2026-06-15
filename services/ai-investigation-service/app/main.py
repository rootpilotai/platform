import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import InvestigationServiceConfig
from app.pipeline import InvestigationPipeline
from app.routers import health, investigate
from infrastructure.monitoring.otel import setup_tracing
from infrastructure.openai.openai_llm_provider import OpenAILLMProvider, OpenAIProviderConfig
from shared.config import load_settings
from shared.contracts import Event, EventBus
from shared.contracts.events import EventTopic, InvestigationCompletedEvent, InvestigationRequestedEvent, ServiceName
from shared.domain.incident.context.models import IncidentContext

logger = logging.getLogger(__name__)

EventBusFactory = Callable[[str], Awaitable[EventBus]]


async def _handle_investigation_requested(
    event: Event,
    pipeline: InvestigationPipeline,
    event_bus: EventBus,
) -> None:
    try:
        requested = InvestigationRequestedEvent(**event.payload)
    except Exception:
        logger.exception("Failed to parse investigation.requested payload")
        return

    logger.info(
        "Received investigation.requested",
        extra={"incident_id": requested.incident_id, "depth": requested.depth},
    )

    try:
        context = IncidentContext(**requested.context)
    except Exception:
        logger.exception(
            "Failed to reconstruct IncidentContext from event payload",
            extra={"incident_id": requested.incident_id},
        )
        return

    result = await pipeline.run(context)

    try:
        completed = InvestigationCompletedEvent(
            investigation_id=requested.investigation_id,
            incident_id=requested.incident_id,
            summary=result.summary.model_dump(),
        )
        outbound = Event(
            source=ServiceName.INVESTIGATION,
            topic=EventTopic.INVESTIGATION_COMPLETED,
            payload=completed.model_dump(),
        )
        await event_bus.publish(outbound)
        logger.info("Published investigation.completed", extra={"incident_id": requested.incident_id})
    except Exception:
        logger.exception("Failed to publish investigation.completed event")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: InvestigationServiceConfig = load_settings(InvestigationServiceConfig)
    app.state.settings = settings

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(levelname)s\t%(name)s\t%(message)s",
    )

    setup_tracing(app, settings)

    llm_provider = OpenAILLMProvider(OpenAIProviderConfig())
    await llm_provider.start()
    app.state.llm = llm_provider
    pipeline = InvestigationPipeline(llm_provider)
    app.state.pipeline = pipeline

    factory: EventBusFactory | None = getattr(app.state, "_event_bus_factory", None)
    if factory is not None:
        event_bus = await factory(settings.event_bus_url)
        app.state.event_bus = event_bus

        handler = _make_investigation_handler(pipeline, event_bus)
        await event_bus.subscribe(EventTopic.INVESTIGATION_REQUESTED, handler)
        logger.info("Subscribed to investigation.requested")
    else:
        logger.warning("No event bus factory configured — events will not be published or consumed")

    logger.info("Service started", extra={"service": settings.service_name})
    yield

    event_bus: EventBus | None = getattr(app.state, "event_bus", None)
    if event_bus is not None:
        await event_bus.close()
    await llm_provider.close()
    logger.info("Service stopped", extra={"service": settings.service_name})


def _make_investigation_handler(
    pipeline: InvestigationPipeline,
    event_bus: EventBus,
) -> Callable[[Event], Awaitable[None]]:
    async def handler(event: Event) -> None:
        await _handle_investigation_requested(event, pipeline, event_bus)

    return handler


def create_app(event_bus_factory: EventBusFactory | None = None) -> FastAPI:
    app = FastAPI(
        title="ai-investigation-service",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state._event_bus_factory = event_bus_factory
    app.include_router(health.router)
    app.include_router(investigate.router)
    return app


app = create_app()
