"""Config-driven notification provider router."""

import logging

from app.config import NotificationServiceSettings
from infrastructure.discord import DiscordNotificationProvider, DiscordProviderConfig
from infrastructure.slack import SlackNotificationProvider, SlackProviderConfig
from shared.contracts.interfaces.notification_provider import NotificationProvider
from shared.contracts.schemas.notification import NotificationMessage

logger = logging.getLogger(__name__)


class NotificationRouter:
    def __init__(self, settings: NotificationServiceSettings) -> None:
        self._providers: list[NotificationProvider] = []

        if settings.slack_enabled:
            slack_config = SlackProviderConfig(
                bot_token=settings.slack_bot_token,
                default_channel=settings.slack_default_channel,
            )
            self._providers.append(SlackNotificationProvider(slack_config))
            logger.info("Slack notification provider enabled")

        if settings.discord_enabled:
            discord_config = DiscordProviderConfig(
                webhook_url=settings.discord_webhook_url,
                default_username=settings.discord_username,
            )
            self._providers.append(DiscordNotificationProvider(discord_config))
            logger.info("Discord notification provider enabled")

        if not self._providers:
            logger.warning("No notification providers enabled")

    @property
    def providers(self) -> list[NotificationProvider]:
        return list(self._providers)

    async def start_all(self) -> None:
        for provider in self._providers:
            await provider.start()

    async def stop_all(self) -> None:
        for provider in self._providers:
            await provider.close()

    async def route(self, message: NotificationMessage) -> None:
        for provider in self._providers:
            try:
                await provider.send(message)
                logger.info(
                    "Notification delivered",
                    extra={"provider": type(provider).__name__, "topic": message.topic},
                )
            except Exception:
                logger.exception(
                    "Notification delivery failed",
                    extra={"provider": type(provider).__name__, "topic": message.topic},
                )

    async def health(self) -> dict[str, bool]:
        status: dict[str, bool] = {}
        for provider in self._providers:
            try:
                status[type(provider).__name__] = await provider.health()
            except Exception:
                status[type(provider).__name__] = False
        return status
