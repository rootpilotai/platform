"""Discord notification provider implementation using webhooks."""

import logging

import httpx
from pydantic import BaseModel, Field

from shared.contracts.interfaces.notification_provider import NotificationProvider
from shared.contracts.schemas.notification import NotificationMessage

logger = logging.getLogger(__name__)


class DiscordProviderConfig(BaseModel):
    webhook_url: str = Field(default="", description="Discord webhook URL.")
    default_username: str = Field(default="RootPilot", description="Bot username for Discord messages.")


class DiscordNotificationProvider(NotificationProvider):
    def __init__(self, config: DiscordProviderConfig) -> None:
        self._config = config
        self._client: httpx.AsyncClient | None = None

    async def start(self) -> None:
        self._client = httpx.AsyncClient(timeout=10.0)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def send(self, message: NotificationMessage) -> None:
        if self._client is None:
            raise RuntimeError("DiscordNotificationProvider not started")
        if not self._config.webhook_url:
            raise RuntimeError("Discord webhook URL not configured")

        embed: dict = {
            "title": message.title,
            "description": message.body,
            "color": self._severity_color(message.severity),
            "fields": [{"name": k, "value": v, "inline": True} for k, v in message.fields.items()],
            "footer": {"text": f"Source: {message.source}"},
            "timestamp": message.timestamp.isoformat(),
        }

        payload = {
            "username": self._config.default_username,
            "embeds": [embed],
        }

        try:
            response = await self._client.post(self._config.webhook_url, json=payload)
            response.raise_for_status()
            logger.info("Discord notification sent", extra={"topic": message.topic})
        except httpx.HTTPError as e:
            logger.error("Discord webhook error", extra={"error": str(e)})
            raise

    async def health(self) -> bool:
        return self._client is not None

    @staticmethod
    def _severity_color(severity: str) -> int:
        mapping = {
            "critical": 0xE74C3C,
            "error": 0xE67E22,
            "warning": 0xF1C40F,
            "info": 0x3498DB,
            "debug": 0x95A5A6,
        }
        return mapping.get(severity.lower(), 0x95A5A6)
