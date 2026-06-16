import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import CorrelationServiceSettings
from app.routers import correlation, health, timeline
from app.services.connection_manager import ConnectionManager
from infrastructure.elasticsearch import ElasticsearchIncidentStore
from infrastructure.elasticsearch.elasticsearch_incident_store import IncidentElasticsearchConfig
from infrastructure.monitoring.otel import OpenTelemetryMiddleware, setup_tracing
from shared.config import load_settings
from shared.contracts import EventBus
from shared.contracts.events import EventTopic
from shared.domain.correlation.engine import CorrelationEngine
from shared.domain.timeline.services import TimelineReconstructor

logger = logging.getLogger(__name__)

EventBusFactory = Callable[[str], Awaitable[EventBus]]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: CorrelationServiceSettings = load_settings(CorrelationServiceSettings)
    app.state.settings = settings

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(levelname)s\t%(name)s\t%(message)s",
    )

    setup_tracing(app, settings)

    reconstructor = TimelineReconstructor(
        window_duration_seconds=settings.timeline_window_duration,
    )
    engine = CorrelationEngine()

    app.state.reconstructor = reconstructor
    app.state.engine = engine

    es_config = IncidentElasticsearchConfig(
        hosts=settings.elasticsearch_hosts,
        username=settings.elasticsearch_username,
        password=settings.elasticsearch_password,
    )
    incident_store = ElasticsearchIncidentStore(config=es_config)
    await incident_store.start()
    app.state.incident_store = incident_store

    factory: EventBusFactory | None = getattr(app.state, "_event_bus_factory", None)
    if factory is not None:
        event_bus = await factory(settings.event_bus_url)
        app.state.event_bus = event_bus

        manager = ConnectionManager(
            engine=engine,
            reconstructor=reconstructor,
            event_bus=event_bus,
            incident_store=incident_store,
            window_seconds=settings.correlation_window_seconds,
            min_events=settings.correlation_min_events,
            min_score=settings.correlation_min_score,
            incident_severity=settings.correlation_incident_severity,
        )
        app.state.connection_manager = manager

        await event_bus.subscribe(
            EventTopic.TELEMETRY_INGESTED,
            manager.handle_telemetry_event,
        )
        logger.info("Subscribed to telemetry.ingested")
    else:
        logger.warning("No event bus factory configured — correlation pipeline will not run automatically")

    logger.info("Service started", extra={"service": settings.service_name})
    yield

    incident_store: ElasticsearchIncidentStore | None = getattr(app.state, "incident_store", None)
    if incident_store is not None:
        await incident_store.close()
    manager: ConnectionManager | None = getattr(app.state, "connection_manager", None)
    if manager is not None:
        await manager.close()
    event_bus: EventBus | None = getattr(app.state, "event_bus", None)
    if event_bus is not None:
        await event_bus.close()
    logger.info("Service stopped", extra={"service": settings.service_name})


def create_app(event_bus_factory: EventBusFactory | None = None) -> FastAPI:
    app = FastAPI(
        title="correlation-service",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state._event_bus_factory = event_bus_factory
    app.add_middleware(OpenTelemetryMiddleware)
    app.include_router(health.router)
    app.include_router(timeline.router)
    app.include_router(correlation.router)
    return app


app = create_app()
