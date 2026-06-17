"""Production entry point — wires concrete infrastructure into the service."""

from app.main import create_app

from shared.config import BaseAppSettings
from shared.contracts import EventBus, ObservabilityProvider
from shared.contracts.interfaces.investigation_store import InvestigationStore
from shared.contracts.interfaces.llm_provider import LLMProvider


async def _create_rabbitmq_bus(url: str) -> EventBus:
    from infrastructure.rabbitmq import RabbitMQConfig, RabbitMQEventBus

    config = RabbitMQConfig(url=url)
    bus = RabbitMQEventBus(config=config)
    await bus.start()
    return bus


async def _create_investigation_store(settings) -> InvestigationStore:
    from infrastructure.elasticsearch import ElasticsearchInvestigationStore
    from infrastructure.elasticsearch.elasticsearch_investigation_store import InvestigationElasticsearchConfig

    config = InvestigationElasticsearchConfig(
        hosts=settings.elasticsearch_hosts,
        username=settings.elasticsearch_username,
        password=settings.elasticsearch_password,
    )
    store = ElasticsearchInvestigationStore(config=config)
    await store.start()
    return store


async def _create_llm_provider() -> LLMProvider:
    from infrastructure.openai.openai_llm_provider import OpenAILLMProvider, OpenAIProviderConfig

    provider = OpenAILLMProvider(OpenAIProviderConfig())
    await provider.start()
    return provider


def _create_otel_observability(settings: BaseAppSettings) -> ObservabilityProvider:
    from infrastructure.monitoring.otel import OTelObservabilityProvider

    return OTelObservabilityProvider(settings)


app = create_app(
    event_bus_factory=_create_rabbitmq_bus,
    investigation_store_factory=_create_investigation_store,
    llm_provider_factory=_create_llm_provider,
    observability_factory=_create_otel_observability,
)
