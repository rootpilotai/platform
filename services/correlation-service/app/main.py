import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import CorrelationServiceSettings
from app.routers import correlation, health, timeline
from app.services.connection_manager import ConnectionManager
from shared.config import BaseAppSettings, load_settings
from shared.contracts import EventBus
from shared.contracts.events import EventTopic
from shared.contracts.interfaces.incident_store import IncidentStore
from shared.contracts.interfaces.observability import ObservabilityProvider
from shared.domain.correlation.engine import CorrelationEngine
from shared.domain.graph.store import GraphStore
from shared.domain.timeline.services import TimelineReconstructor

logger = logging.getLogger(__name__)

EventBusFactory = Callable[[str], Awaitable[EventBus]]
IncidentStoreFactory = Callable[[CorrelationServiceSettings], Awaitable[IncidentStore]]
GraphStoreFactory = Callable[[], GraphStore]
ObservabilityFactory = Callable[[BaseAppSettings], ObservabilityProvider]


def _noop_observability(_settings: BaseAppSettings) -> ObservabilityProvider:
    from shared.contracts.interfaces.observability import ObservabilityProvider

    class _NoopProvider(ObservabilityProvider):
        def setup(self, app: FastAPI) -> None:
            logger.info("No observability provider configured — tracing disabled")

    return _NoopProvider()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: CorrelationServiceSettings = app.state.settings

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(levelname)s\t%(name)s\t%(message)s",
    )

    reconstructor = TimelineReconstructor(
        window_duration_seconds=settings.timeline_window_duration,
    )

    graph_store_factory: GraphStoreFactory | None = getattr(app.state, "_graph_store_factory", None)
    graph_store = graph_store_factory() if graph_store_factory else None

    engine = CorrelationEngine(store=graph_store)

    app.state.reconstructor = reconstructor
    app.state.engine = engine
    app.state.graph_store = graph_store

    incident_store_factory: IncidentStoreFactory | None = getattr(app.state, "_incident_store_factory", None)
    if incident_store_factory is not None:
        incident_store = await incident_store_factory(settings)
        app.state.incident_store = incident_store

    factory: EventBusFactory | None = getattr(app.state, "_event_bus_factory", None)
    if factory is not None:
        event_bus = await factory(settings.event_bus_url)
        app.state.event_bus = event_bus

        manager = ConnectionManager(
            engine=engine,
            reconstructor=reconstructor,
            event_bus=event_bus,
            incident_store=getattr(app.state, "incident_store", None),
            graph_store=getattr(app.state, "graph_store", None),
            window_seconds=settings.correlation_window_seconds,
            min_events=settings.correlation_min_events,
            min_score=settings.correlation_min_score,
            incident_severity=settings.correlation_incident_severity,
            max_buffer_size=settings.correlation_max_buffer_size,
            min_correlation_interval=settings.correlation_min_interval,
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

    incident_store: IncidentStore | None = getattr(app.state, "incident_store", None)
    if incident_store is not None:
        await incident_store.close()
    manager: ConnectionManager | None = getattr(app.state, "connection_manager", None)
    if manager is not None:
        await manager.close()
    event_bus: EventBus | None = getattr(app.state, "event_bus", None)
    if event_bus is not None:
        await event_bus.close()
    logger.info("Service stopped", extra={"service": settings.service_name})


def create_app(
    event_bus_factory: EventBusFactory | None = None,
    incident_store_factory: IncidentStoreFactory | None = None,
    graph_store_factory: GraphStoreFactory | None = None,
    observability_factory: ObservabilityFactory | None = None,
) -> FastAPI:
    app = FastAPI(
        title="correlation-service",
        version="0.1.0",
        lifespan=lifespan,
    )
    settings = load_settings(CorrelationServiceSettings)
    app.state.settings = settings
    app.state._event_bus_factory = event_bus_factory
    app.state._incident_store_factory = incident_store_factory
    app.state._graph_store_factory = graph_store_factory
    app.state._observability_factory = observability_factory
    if observability_factory is not None:
        observability = observability_factory(settings)
        observability.setup(app)
    app.include_router(health.router)
    app.include_router(timeline.router)
    app.include_router(correlation.router)
    return app


app = create_app()
