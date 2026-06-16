"""Gateway service FastAPI application factory."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import GatewayServiceSettings
from app.routers import health, incidents, investigations
from infrastructure.auth import EnvironmentApiKeyStore
from infrastructure.elasticsearch import (
    ElasticsearchIncidentStore,
    ElasticsearchInvestigationStore,
    IncidentElasticsearchConfig,
    InvestigationElasticsearchConfig,
)
from infrastructure.monitoring.otel import OpenTelemetryMiddleware, setup_tracing
from shared.config import load_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = load_settings(GatewayServiceSettings)
    app.state.settings = settings

    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
    setup_tracing(app, settings)

    incident_es_config = IncidentElasticsearchConfig(
        hosts=settings.elasticsearch_hosts,
        username=settings.elasticsearch_username,
        password=settings.elasticsearch_password,
    )
    incident_store = ElasticsearchIncidentStore(config=incident_es_config)
    await incident_store.start()
    app.state.incident_store = incident_store

    investigation_es_config = InvestigationElasticsearchConfig(
        hosts=settings.elasticsearch_hosts,
        username=settings.elasticsearch_username,
        password=settings.elasticsearch_password,
    )
    investigation_store = ElasticsearchInvestigationStore(config=investigation_es_config)
    await investigation_store.start()
    app.state.investigation_store = investigation_store

    api_key_store = EnvironmentApiKeyStore(api_keys_csv=settings.api_keys)
    app.state.api_key_store = api_key_store

    logger.info("Gateway service started", extra={"host": settings.host, "port": settings.port})

    yield

    await incident_store.close()
    await investigation_store.close()
    logger.info("Gateway service shut down")


def create_app() -> FastAPI:
    app = FastAPI(
        title="gateway-service",
        version="0.1.0",
        lifespan=lifespan,
        description="External platform access layer for RootPilot",
    )

    app.add_middleware(OpenTelemetryMiddleware)

    app.include_router(health.router)
    app.include_router(incidents.router)
    app.include_router(investigations.router)

    return app


app = create_app()
