from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import InvestigationServiceConfig
from app.pipeline import InvestigationPipeline
from app.routers import health, investigate
from infrastructure.openai.openai_llm_provider import OpenAILLMProvider, OpenAIProviderConfig
from shared.config import load_settings

logger = __import__("logging").getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: InvestigationServiceConfig = load_settings(InvestigationServiceConfig)
    app.state.settings = settings

    provider = OpenAILLMProvider(OpenAIProviderConfig())
    await provider.start()
    app.state.llm = provider
    app.state.pipeline = InvestigationPipeline(provider)

    logger.info("Service started", extra={"service": settings.service_name})
    yield

    await provider.close()
    logger.info("Service stopped", extra={"service": settings.service_name})


def create_app() -> FastAPI:
    app = FastAPI(
        title="ai-investigation-service",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(health.router)
    app.include_router(investigate.router)
    return app


app = create_app()
