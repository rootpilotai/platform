import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import OtelAdapterSettings
from app.routers import health, otlp
from app.services.otel_normalizer import OtelNormalizer
from shared.config import BaseAppSettings, load_settings
from shared.contracts import EventBus, ObservabilityProvider

logger = logging.getLogger(__name__)

EventBusFactory = Callable[[str], Awaitable[EventBus]]
ObservabilityFactory = Callable[[BaseAppSettings], ObservabilityProvider]


def _noop_observability(_settings: BaseAppSettings) -> ObservabilityProvider:
    """Return a no-op provider when nothing is configured."""
    from shared.contracts.interfaces.observability import ObservabilityProvider

    class _NoopProvider(ObservabilityProvider):
        def setup(self, app: FastAPI) -> None:
            logger.info("No observability provider configured — tracing disabled")

    return _NoopProvider()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: OtelAdapterSettings = load_settings(OtelAdapterSettings)
    app.state.settings = settings

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(levelname)s\t%(name)s\t%(message)s",
    )

    obs_factory: ObservabilityFactory | None = getattr(app.state, "_observability_factory", None)
    provider = obs_factory(settings) if obs_factory else _noop_observability(settings)
    provider.setup(app)

    factory: EventBusFactory | None = getattr(app.state, "_event_bus_factory", None)
    if factory is not None:
        event_bus = await factory(settings.event_bus_url)
        app.state.event_bus = event_bus
    else:
        logger.warning("No event bus factory configured — events will be logged but not published")

    normalizer = OtelNormalizer(
        source=settings.source_name,
        latency_threshold_ms=settings.anomaly_latency_threshold_ms,
    )
    app.state.normalizer = normalizer

    logger.info("Service started", extra={"service": settings.service_name})
    yield

    event_bus: EventBus | None = getattr(app.state, "event_bus", None)
    if event_bus is not None:
        await event_bus.close()
    logger.info("Service stopped", extra={"service": settings.service_name})


def create_app(
    event_bus_factory: EventBusFactory | None = None,
    observability_factory: ObservabilityFactory | None = None,
) -> FastAPI:
    app = FastAPI(
        title="otel-adapter-service",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state._event_bus_factory = event_bus_factory
    app.state._observability_factory = observability_factory
    app.include_router(health.router)
    app.include_router(otlp.router)
    return app


app = create_app()
