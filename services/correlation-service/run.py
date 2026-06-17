"""Production entry point — wires concrete infrastructure into the service."""

from app.main import create_app

from shared.config import BaseAppSettings
from shared.contracts import EventBus, ObservabilityProvider
from shared.contracts.interfaces.incident_store import IncidentStore


async def _create_rabbitmq_bus(url: str) -> EventBus:
    from infrastructure.rabbitmq import RabbitMQConfig, RabbitMQEventBus

    config = RabbitMQConfig(url=url)
    bus = RabbitMQEventBus(config=config)
    await bus.start()
    return bus


async def _create_incident_store(settings) -> IncidentStore:
    from infrastructure.elasticsearch import ElasticsearchIncidentStore
    from infrastructure.elasticsearch.elasticsearch_incident_store import IncidentElasticsearchConfig

    config = IncidentElasticsearchConfig(
        hosts=settings.elasticsearch_hosts,
        username=settings.elasticsearch_username,
        password=settings.elasticsearch_password,
    )
    store = ElasticsearchIncidentStore(config=config)
    await store.start()
    return store


def _create_otel_observability(settings: BaseAppSettings) -> ObservabilityProvider:
    from infrastructure.monitoring.otel.otel_observability_provider import OTelObservabilityProvider

    return OTelObservabilityProvider(settings)


app = create_app(
    event_bus_factory=_create_rabbitmq_bus,
    incident_store_factory=_create_incident_store,
    observability_factory=_create_otel_observability,
)
