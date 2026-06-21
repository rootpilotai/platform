import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import InvestigationServiceConfig
from app.pipeline import InvestigationPipeline
from app.routers import health, investigate
from shared.config import BaseAppSettings, load_settings
from shared.contracts import Event, EventBus
from shared.contracts.events import EventTopic, InvestigationCompletedEvent, InvestigationRequestedEvent, ServiceName
from shared.contracts.interfaces.investigation_store import InvestigationStore
from shared.contracts.interfaces.llm_provider import LLMProvider
from shared.contracts.interfaces.observability import ObservabilityProvider
from shared.domain.incident.context.models import IncidentContext

logger = logging.getLogger(__name__)

EventBusFactory = Callable[[str], Awaitable[EventBus]]
InvestigationStoreFactory = Callable[[InvestigationServiceConfig], Awaitable[InvestigationStore]]
LLMProviderFactory = Callable[[], Awaitable[LLMProvider]]
ObservabilityFactory = Callable[[BaseAppSettings], ObservabilityProvider]


def _noop_observability(_settings: BaseAppSettings) -> ObservabilityProvider:
    from shared.contracts.interfaces.observability import ObservabilityProvider

    class _NoopProvider(ObservabilityProvider):
        def setup(self, app: FastAPI) -> None:
            logger.info("No observability provider configured — tracing disabled")

    return _NoopProvider()


async def _handle_investigation_requested(
    event: Event,
    pipeline: InvestigationPipeline,
    event_bus: EventBus,
    investigation_store: InvestigationStore | None = None,
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
        logger.info(
            "Reconstructed IncidentContext",
            extra={
                "incident_id": requested.incident_id,
                "event_count": context.event_count,
                "service_count": context.service_count,
                "impacts": len(context.impacts),
                "reachable_services": len(context.reachable_services),
                "trace_groups": len(context.trace_groups),
            },
        )
    except Exception:
        logger.exception(
            "Failed to reconstruct IncidentContext from event payload",
            extra={"incident_id": requested.incident_id},
        )
        return

    result = await pipeline.run(context)

    top = result.summary.root_causes[0] if result.summary.root_causes else None
    logger.info(
        "Investigation result — incident=%s top_root_cause=%s confidence=%.2f duration=%.0fms",
        requested.incident_id,
        top.service if top else "none",
        top.confidence if top else 0.0,
        result.duration_ms,
    )

    if investigation_store is not None:
        await investigation_store.store(requested.investigation_id, result)

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
    settings: InvestigationServiceConfig = app.state.settings

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(levelname)s\t%(name)s\t%(message)s",
    )

    llm_factory: LLMProviderFactory | None = getattr(app.state, "_llm_provider_factory", None)
    pipeline = None
    if llm_factory is not None:
        llm_provider = await llm_factory()
        app.state.llm = llm_provider
        pipeline = InvestigationPipeline(llm_provider)
        app.state.pipeline = pipeline

    investigation_store = None
    investigation_store_factory: InvestigationStoreFactory | None = getattr(
        app.state, "_investigation_store_factory", None
    )
    if investigation_store_factory is not None:
        investigation_store = await investigation_store_factory(settings)
        app.state.investigation_store = investigation_store

    factory: EventBusFactory | None = getattr(app.state, "_event_bus_factory", None)
    if factory is not None:
        event_bus = await factory(settings.event_bus_url)
        app.state.event_bus = event_bus

        handler = _make_investigation_handler(pipeline, event_bus, investigation_store)
        await event_bus.subscribe(EventTopic.INVESTIGATION_REQUESTED, handler)
        logger.info("Subscribed to investigation.requested")
    else:
        logger.warning("No event bus factory configured — events will not be published or consumed")

    logger.info("Service started", extra={"service": settings.service_name})
    yield

    investigation_store: InvestigationStore | None = getattr(app.state, "investigation_store", None)
    if investigation_store is not None:
        await investigation_store.close()
    event_bus: EventBus | None = getattr(app.state, "event_bus", None)
    if event_bus is not None:
        await event_bus.close()
    llm_provider: LLMProvider | None = getattr(app.state, "llm", None)
    if llm_provider is not None:
        await llm_provider.close()
    logger.info("Service stopped", extra={"service": settings.service_name})


def _make_investigation_handler(
    pipeline: InvestigationPipeline,
    event_bus: EventBus,
    investigation_store: InvestigationStore | None = None,
) -> Callable[[Event], Awaitable[None]]:
    async def handler(event: Event) -> None:
        await _handle_investigation_requested(event, pipeline, event_bus, investigation_store)

    return handler


def create_app(
    event_bus_factory: EventBusFactory | None = None,
    investigation_store_factory: InvestigationStoreFactory | None = None,
    llm_provider_factory: LLMProviderFactory | None = None,
    observability_factory: ObservabilityFactory | None = None,
) -> FastAPI:
    app = FastAPI(
        title="ai-investigation-service",
        version="0.1.0",
        lifespan=lifespan,
    )
    settings = load_settings(InvestigationServiceConfig)
    app.state.settings = settings
    app.state._event_bus_factory = event_bus_factory
    app.state._investigation_store_factory = investigation_store_factory
    app.state._llm_provider_factory = llm_provider_factory
    app.state._observability_factory = observability_factory
    if observability_factory is not None:
        provider = observability_factory(settings)
        provider.setup(app)
    else:
        _noop_observability(settings).setup(app)
    app.include_router(health.router)
    app.include_router(investigate.router)
    return app


app = create_app()
