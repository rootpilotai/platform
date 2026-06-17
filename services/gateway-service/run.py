"""Production entry point — wires concrete infrastructure into the service."""

from app.config import GatewayServiceSettings
from app.main import create_app

from shared.config import BaseAppSettings
from shared.contracts import ObservabilityProvider
from shared.contracts.interfaces.api_key_store import ApiKeyStore
from shared.contracts.interfaces.incident_store import IncidentStore
from shared.contracts.interfaces.investigation_store import InvestigationStore


async def _create_incident_store(settings: GatewayServiceSettings) -> IncidentStore:
    from infrastructure.elasticsearch import (
        ElasticsearchIncidentStore,
        IncidentElasticsearchConfig,
    )

    config = IncidentElasticsearchConfig(
        hosts=settings.elasticsearch_hosts,
        username=settings.elasticsearch_username,
        password=settings.elasticsearch_password,
    )
    store = ElasticsearchIncidentStore(config=config)
    await store.start()
    return store


async def _create_investigation_store(settings: GatewayServiceSettings) -> InvestigationStore:
    from infrastructure.elasticsearch import (
        ElasticsearchInvestigationStore,
        InvestigationElasticsearchConfig,
    )

    config = InvestigationElasticsearchConfig(
        hosts=settings.elasticsearch_hosts,
        username=settings.elasticsearch_username,
        password=settings.elasticsearch_password,
    )
    store = ElasticsearchInvestigationStore(config=config)
    await store.start()
    return store


def _create_api_key_store(settings: GatewayServiceSettings) -> ApiKeyStore:
    from infrastructure.auth import EnvironmentApiKeyStore

    return EnvironmentApiKeyStore(api_keys_csv=settings.api_keys)


def _create_otel_observability(settings: BaseAppSettings) -> ObservabilityProvider:
    from infrastructure.monitoring.otel import OTelObservabilityProvider

    return OTelObservabilityProvider(settings)


app = create_app(
    incident_store_factory=_create_incident_store,
    investigation_store_factory=_create_investigation_store,
    api_key_store_factory=_create_api_key_store,
    observability_factory=_create_otel_observability,
)
