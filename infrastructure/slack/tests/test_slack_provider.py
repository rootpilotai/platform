"""Tests for the Slack notification provider."""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from infrastructure.slack.slack_notification_provider import (
    SlackNotificationProvider,
    SlackProviderConfig,
)
from shared.contracts.schemas.notification import NotificationMessage


@pytest.fixture
def config() -> SlackProviderConfig:
    return SlackProviderConfig(bot_token="xoxb-test-token")


@pytest.fixture
def provider(config: SlackProviderConfig) -> SlackNotificationProvider:
    p = SlackNotificationProvider(config)
    p._client = AsyncMock()
    return p


class TestSlackProviderConfig:
    def test_defaults(self) -> None:
        cfg = SlackProviderConfig()
        assert cfg.bot_token == ""
        assert cfg.default_channel == "#incidents"

    def test_custom_values(self) -> None:
        cfg = SlackProviderConfig(bot_token="xoxb-token", default_channel="#alerts")
        assert cfg.bot_token == "xoxb-token"
        assert cfg.default_channel == "#alerts"


class TestSlackNotificationProvider:
    async def test_start_creates_client(self) -> None:
        cfg = SlackProviderConfig(bot_token="xoxb-test-token")
        provider = SlackNotificationProvider(cfg)
        assert provider._client is None
        with patch("infrastructure.slack.slack_notification_provider.AsyncWebClient") as mock:
            await provider.start()
        mock.assert_called_once_with(token="xoxb-test-token")
        assert provider._client is not None

    async def test_close_clears_client(self, provider: SlackNotificationProvider) -> None:
        await provider.close()
        assert provider._client is None

    async def test_send_posts_to_channel(self, provider: SlackNotificationProvider) -> None:
        client: Any = provider._client
        client.chat_postMessage = AsyncMock()

        message = NotificationMessage(
            topic="investigation.completed",
            title="Investigation Complete",
            body="RCA analysis for INC-001",
            fields={"Incident": "INC-001", "Confidence": "0.95"},
            severity="critical",
            source="ai-investigation-service",
        )

        await provider.send(message)

        client.chat_postMessage.assert_awaited_once()
        call_kwargs = client.chat_postMessage.call_args[1]
        assert call_kwargs["channel"] == "#incidents"
        assert call_kwargs["text"] == "Investigation Complete"

    async def test_send_uses_channel_from_metadata(self, provider: SlackNotificationProvider) -> None:
        client: Any = provider._client
        client.chat_postMessage = AsyncMock()

        message = NotificationMessage(
            topic="investigation.completed",
            title="Test",
            body="Body",
            metadata={"channel": "#alerts"},
            source="test",
        )

        await provider.send(message)
        assert client.chat_postMessage.call_args[1]["channel"] == "#alerts"

    async def test_send_raises_if_not_started(self) -> None:
        cfg = SlackProviderConfig(bot_token="xoxb-test-token")
        provider = SlackNotificationProvider(cfg)
        message = NotificationMessage(topic="test", title="Test", body="Body", source="test")
        with pytest.raises(RuntimeError, match="not started"):
            await provider.send(message)

    async def test_health_returns_true_when_connected(self, provider: SlackNotificationProvider) -> None:
        client: Any = provider._client
        client.auth_test = AsyncMock()
        assert await provider.health() is True

    async def test_health_returns_false_when_not_started(self) -> None:
        cfg = SlackProviderConfig(bot_token="xoxb-test-token")
        provider = SlackNotificationProvider(cfg)
        assert await provider.health() is False

    async def test_send_includes_blocks(self, provider: SlackNotificationProvider) -> None:
        client: Any = provider._client
        client.chat_postMessage = AsyncMock()

        message = NotificationMessage(
            topic="investigation.completed",
            title="RCA Complete",
            body="Analysis finished",
            fields={"Incident": "INC-001"},
            severity="error",
            source="ai-investigation-service",
        )

        await provider.send(message)

        blocks = client.chat_postMessage.call_args[1]["blocks"]
        assert len(blocks) == 4
        assert blocks[0]["type"] == "header"
        assert blocks[1]["type"] == "section"
        assert blocks[2]["type"] == "section"
        assert blocks[3]["type"] == "context"
