"""Gateway service FastAPI application factory."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import GatewayServiceSettings
from app.routers import health, incidents, investigations
from shared.config import BaseAppSettings, load_settings
from shared.contracts import EventBus, ObservabilityProvider
from shared.contracts.interfaces.api_key_store import ApiKeyStore
from shared.contracts.interfaces.incident_store import IncidentStore
from shared.contracts.interfaces.investigation_store import InvestigationStore

logger = logging.getLogger(__name__)

EventBusFactory = Callable[[str], Awaitable[EventBus]]
IncidentStoreFactory = Callable[[GatewayServiceSettings], Awaitable[IncidentStore]]
InvestigationStoreFactory = Callable[[GatewayServiceSettings], Awaitable[InvestigationStore]]
ApiKeyStoreFactory = Callable[[GatewayServiceSettings], ApiKeyStore]
ObservabilityFactory = Callable[[BaseAppSettings], ObservabilityProvider]


def _noop_observability(_settings: BaseAppSettings) -> ObservabilityProvider:
    from shared.contracts.interfaces.observability import ObservabilityProvider

    class _NoopProvider(ObservabilityProvider):
        def setup(self, app: FastAPI) -> None:
            logger.info("No observability configured")

    return _NoopProvider()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = load_settings(GatewayServiceSettings)
    app.state.settings = settings

    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))

    incident_store_factory: IncidentStoreFactory | None = getattr(app.state, "_incident_store_factory", None)
    if incident_store_factory:
        incident_store = await incident_store_factory(settings)
        app.state.incident_store = incident_store

    investigation_store_factory: InvestigationStoreFactory | None = getattr(
        app.state, "_investigation_store_factory", None
    )
    if investigation_store_factory:
        investigation_store = await investigation_store_factory(settings)
        app.state.investigation_store = investigation_store

    api_key_store_factory: ApiKeyStoreFactory | None = getattr(app.state, "_api_key_store_factory", None)
    if api_key_store_factory:
        api_key_store = api_key_store_factory(settings)
        app.state.api_key_store = api_key_store

    logger.info("Gateway service started", extra={"host": settings.host, "port": settings.port})

    yield

    incident_store = getattr(app.state, "incident_store", None)
    if incident_store is not None:
        await incident_store.close()
    investigation_store = getattr(app.state, "investigation_store", None)
    if investigation_store is not None:
        await investigation_store.close()
    logger.info("Gateway service shut down")


def create_app(
    *,
    event_bus_factory: EventBusFactory | None = None,
    incident_store_factory: IncidentStoreFactory | None = None,
    investigation_store_factory: InvestigationStoreFactory | None = None,
    api_key_store_factory: ApiKeyStoreFactory | None = None,
    observability_factory: ObservabilityFactory | None = None,
) -> FastAPI:
    app = FastAPI(
        title="gateway-service",
        version="0.1.0",
        lifespan=lifespan,
        description="External platform access layer for RootPilot",
    )

    app.state._event_bus_factory = event_bus_factory
    app.state._incident_store_factory = incident_store_factory
    app.state._investigation_store_factory = investigation_store_factory
    app.state._api_key_store_factory = api_key_store_factory

    # Observability must be set up before the app starts (middleware must be
    # registered before uvicorn begins serving).
    obs = (
        _noop_observability(GatewayServiceSettings())
        if observability_factory is None
        else observability_factory(GatewayServiceSettings())
    )
    obs.setup(app)
    app.state._observability = obs

    app.include_router(health.router)
    app.include_router(incidents.router)
    app.include_router(investigations.router)

    return app


app = create_app()
