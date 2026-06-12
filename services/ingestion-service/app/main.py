import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import IngestionServiceSettings
from app.routers import health, ingest
from infrastructure.rabbitmq import RabbitMQConfig, RabbitMQEventBus
from shared.config import load_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: IngestionServiceSettings = load_settings(IngestionServiceSettings)
    app.state.settings = settings

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(levelname)s\t%(name)s\t%(message)s",
    )

    config = RabbitMQConfig(url=settings.event_bus_url)
    event_bus = RabbitMQEventBus(config=config)
    try:
        await event_bus.start()
    except Exception:
        logger.warning("Event bus unavailable at startup — will retry in background")
    app.state.event_bus = event_bus

    logger.info("Service started", extra={"service": settings.service_name})

    yield

    await event_bus.close()
    logger.info("Service stopped", extra={"service": settings.service_name})


def create_app() -> FastAPI:
    app = FastAPI(
        title="ingestion-service",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(health.router)
    app.include_router(ingest.router)
    return app


app = create_app()
