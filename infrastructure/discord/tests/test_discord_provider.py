"""Tests for the Discord notification provider."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from infrastructure.discord.discord_notification_provider import (
    DiscordNotificationProvider,
    DiscordProviderConfig,
)
from shared.contracts.schemas.notification import NotificationMessage


@pytest.fixture
def config() -> DiscordProviderConfig:
    return DiscordProviderConfig(webhook_url="https://discord.com/api/webhooks/test")


@pytest.fixture
def provider(config: DiscordProviderConfig) -> DiscordNotificationProvider:
    p = DiscordNotificationProvider(config)
    p._client = AsyncMock()
    return p


class TestDiscordProviderConfig:
    def test_defaults(self) -> None:
        cfg = DiscordProviderConfig()
        assert cfg.webhook_url == ""
        assert cfg.default_username == "RootPilot"

    def test_custom_values(self) -> None:
        cfg = DiscordProviderConfig(webhook_url="https://discord.webhook", default_username="AlertBot")
        assert cfg.webhook_url == "https://discord.webhook"
        assert cfg.default_username == "AlertBot"


class TestDiscordNotificationProvider:
    async def test_start_creates_client(self) -> None:
        cfg = DiscordProviderConfig(webhook_url="https://discord.com/api/webhooks/test")
        provider = DiscordNotificationProvider(cfg)
        assert provider._client is None
        await provider.start()
        assert provider._client is not None
        await provider.close()

    async def test_close_clears_client(self, provider: DiscordNotificationProvider) -> None:
        await provider.close()
        assert provider._client is None

    async def test_send_posts_to_webhook(self, provider: DiscordNotificationProvider) -> None:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        client: Any = provider._client
        client.post = AsyncMock(return_value=mock_response)

        message = NotificationMessage(
            topic="investigation.completed",
            title="Investigation Complete",
            body="RCA analysis for INC-001",
            fields={"Incident": "INC-001", "Confidence": "0.95"},
            severity="critical",
            source="ai-investigation-service",
        )

        await provider.send(message)

        client.post.assert_awaited_once()
        call_args = client.post.call_args
        assert call_args[0][0] == "https://discord.com/api/webhooks/test"
        payload = call_args[1]["json"]
        assert payload["username"] == "RootPilot"
        assert len(payload["embeds"]) == 1
        embed = payload["embeds"][0]
        assert embed["title"] == "Investigation Complete"
        assert embed["color"] == 0xE74C3C

    async def test_send_raises_if_not_started(self) -> None:
        cfg = DiscordProviderConfig(webhook_url="https://discord.com/api/webhooks/test")
        provider = DiscordNotificationProvider(cfg)
        message = NotificationMessage(topic="test", title="Test", body="Body", source="test")
        with pytest.raises(RuntimeError, match="not started"):
            await provider.send(message)

    async def test_send_raises_if_no_webhook_url(self) -> None:
        cfg = DiscordProviderConfig()
        provider = DiscordNotificationProvider(cfg)
        provider._client = AsyncMock()
        message = NotificationMessage(topic="test", title="Test", body="Body", source="test")
        with pytest.raises(RuntimeError, match="webhook URL not configured"):
            await provider.send(message)

    async def test_health_returns_true_when_started(self, provider: DiscordNotificationProvider) -> None:
        assert await provider.health() is True

    async def test_health_returns_false_when_not_started(self) -> None:
        cfg = DiscordProviderConfig(webhook_url="https://discord.com/api/webhooks/test")
        provider = DiscordNotificationProvider(cfg)
        assert await provider.health() is False

    async def test_send_raises_on_http_error(self, provider: DiscordNotificationProvider) -> None:
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=MagicMock()
        )
        client: Any = provider._client
        client.post = AsyncMock(return_value=mock_response)

        message = NotificationMessage(topic="test", title="Test", body="Body", source="test")
        with pytest.raises(httpx.HTTPError):
            await provider.send(message)

    async def test_severity_color_mapping(self) -> None:
        assert DiscordNotificationProvider._severity_color("critical") == 0xE74C3C
        assert DiscordNotificationProvider._severity_color("error") == 0xE67E22
        assert DiscordNotificationProvider._severity_color("warning") == 0xF1C40F
        assert DiscordNotificationProvider._severity_color("info") == 0x3498DB
        assert DiscordNotificationProvider._severity_color("debug") == 0x95A5A6
        assert DiscordNotificationProvider._severity_color("unknown") == 0x95A5A6
