"""Production entry point — wires concrete infrastructure into the service."""

from app.config import NotificationServiceSettings
from app.main import create_app
from app.services.provider_router import NotificationRouter

from shared.config import BaseAppSettings
from shared.contracts import EventBus, ObservabilityProvider
from shared.contracts.interfaces.notification_provider import NotificationProvider


async def _create_rabbitmq_bus(url: str) -> EventBus:
    from infrastructure.rabbitmq import RabbitMQConfig, RabbitMQEventBus

    config = RabbitMQConfig(url=url)
    bus = RabbitMQEventBus(config=config)
    await bus.start()
    return bus


def _create_notification_router() -> NotificationRouter:
    from infrastructure.discord import DiscordNotificationProvider, DiscordProviderConfig
    from infrastructure.slack import SlackNotificationProvider, SlackProviderConfig

    providers: list[NotificationProvider] = []
    settings = NotificationServiceSettings()

    if settings.slack_enabled:
        slack_config = SlackProviderConfig(
            bot_token=settings.slack_bot_token,
            default_channel=settings.slack_default_channel,
        )
        providers.append(SlackNotificationProvider(slack_config))

    if settings.discord_enabled:
        discord_config = DiscordProviderConfig(
            webhook_url=settings.discord_webhook_url,
            default_username=settings.discord_username,
        )
        providers.append(DiscordNotificationProvider(discord_config))

    return NotificationRouter(providers)


def _create_otel_observability(settings: BaseAppSettings) -> ObservabilityProvider:
    from infrastructure.monitoring.otel import OTelObservabilityProvider

    return OTelObservabilityProvider(settings)


app = create_app(
    event_bus_factory=_create_rabbitmq_bus,
    notification_router_factory=_create_notification_router,
    observability_factory=_create_otel_observability,
)
