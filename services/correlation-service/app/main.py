import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import CorrelationServiceSettings
from app.routers import correlation, health, timeline
from infrastructure.monitoring.otel import OpenTelemetryMiddleware, setup_tracing
from shared.config import load_settings
from shared.domain.correlation.engine import CorrelationEngine
from shared.domain.timeline.services import TimelineReconstructor

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: CorrelationServiceSettings = load_settings(CorrelationServiceSettings)
    app.state.settings = settings

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(levelname)s\t%(name)s\t%(message)s",
    )

    setup_tracing(app, settings)

    app.state.reconstructor = TimelineReconstructor(
        window_duration_seconds=settings.timeline_window_duration,
    )
    app.state.engine = CorrelationEngine()

    logger.info("Service started", extra={"service": settings.service_name})

    yield

    logger.info("Service stopped", extra={"service": settings.service_name})


def create_app() -> FastAPI:
    app = FastAPI(
        title="correlation-service",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(OpenTelemetryMiddleware)
    app.include_router(health.router)
    app.include_router(timeline.router)
    app.include_router(correlation.router)
    return app


app = create_app()
