"""Slack notification provider implementation using slack_sdk."""

import logging

from pydantic import BaseModel, Field
from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncWebClient

from shared.contracts.interfaces.notification_provider import NotificationProvider
from shared.contracts.schemas.notification import NotificationMessage

logger = logging.getLogger(__name__)


class SlackProviderConfig(BaseModel):
    bot_token: str = Field(default="", description="Slack bot user OAuth token.")
    default_channel: str = Field(default="#incidents", description="Default Slack channel for notifications.")


class SlackNotificationProvider(NotificationProvider):
    def __init__(self, config: SlackProviderConfig) -> None:
        self._config = config
        self._client: AsyncWebClient | None = None

    async def start(self) -> None:
        self._client = AsyncWebClient(token=self._config.bot_token)

    async def close(self) -> None:
        self._client = None

    async def send(self, message: NotificationMessage) -> None:
        if self._client is None:
            raise RuntimeError("SlackNotificationProvider not started")

        channel = message.metadata.get("channel") or self._config.default_channel

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": message.title},
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": message.body},
            },
        ]

        if message.fields:
            field_texts = [f"*{k}:* {v}" for k, v in message.fields.items()]
            blocks.append({"type": "section", "fields": field_texts})

        blocks.append(
            {
                "type": "context",
                "elements": [
                    f"Source: {message.source} | Severity: {message.severity}",
                ],
            }
        )

        try:
            await self._client.chat_postMessage(
                channel=channel,
                blocks=blocks,
                text=message.title,
            )
            logger.info("Slack notification sent", extra={"channel": channel, "topic": message.topic})
        except SlackApiError as e:
            logger.error("Slack API error", extra={"channel": channel, "error": str(e)})
            raise

    async def health(self) -> bool:
        if self._client is None:
            return False
        try:
            await self._client.auth_test()
            return True
        except SlackApiError:
            return False
