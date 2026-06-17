"""Production entry point — wires concrete infrastructure into the service."""

from app.main import create_app

from shared.config import BaseAppSettings
from shared.contracts import EventBus, ObservabilityProvider


async def _create_rabbitmq_bus(url: str) -> EventBus:
    from infrastructure.rabbitmq import RabbitMQConfig, RabbitMQEventBus

    config = RabbitMQConfig(url=url)
    bus = RabbitMQEventBus(config=config)
    await bus.start()
    return bus


def _create_otel_observability(settings: BaseAppSettings) -> ObservabilityProvider:
    from infrastructure.monitoring.otel import OTelObservabilityProvider

    return OTelObservabilityProvider(settings)


app = create_app(
    event_bus_factory=_create_rabbitmq_bus,
    observability_factory=_create_otel_observability,
)
