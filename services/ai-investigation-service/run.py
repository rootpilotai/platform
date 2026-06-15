"""Production entry point — wires concrete infrastructure into the service."""

from app.main import create_app

from shared.contracts import EventBus


async def _create_rabbitmq_bus(url: str) -> EventBus:
    from infrastructure.rabbitmq import RabbitMQConfig, RabbitMQEventBus

    config = RabbitMQConfig(url=url)
    bus = RabbitMQEventBus(config=config)
    await bus.start()
    return bus


app = create_app(event_bus_factory=_create_rabbitmq_bus)
