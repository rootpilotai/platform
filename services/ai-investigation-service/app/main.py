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
from shared.contracts import EventBus

logger = logging.getLogger(__name__)

EventBusFactory = Callable[[str], Awaitable[EventBus]]


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
    app.state.pipeline = InvestigationPipeline(llm_provider)

    factory: EventBusFactory | None = getattr(app.state, "_event_bus_factory", None)
    if factory is not None:
        event_bus = await factory(settings.event_bus_url)
        app.state.event_bus = event_bus
    else:
        logger.warning("No event bus factory configured — events will not be published")

    logger.info("Service started", extra={"service": settings.service_name})
    yield

    event_bus: EventBus | None = getattr(app.state, "event_bus", None)
    if event_bus is not None:
        await event_bus.close()
    await llm_provider.close()
    logger.info("Service stopped", extra={"service": settings.service_name})


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
