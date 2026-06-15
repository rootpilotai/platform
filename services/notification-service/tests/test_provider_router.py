"""Tests for the NotificationRouter."""

from unittest.mock import AsyncMock, MagicMock

from app.services.provider_router import NotificationRouter

from shared.contracts.schemas.notification import NotificationMessage


class TestNotificationRouter:
    def test_no_providers_when_disabled(self) -> None:
        settings = MagicMock()
        settings.slack_enabled = False
        settings.discord_enabled = False

        router = NotificationRouter(settings)
        assert len(router.providers) == 0

    def test_slack_provider_created_when_enabled(self) -> None:
        settings = MagicMock()
        settings.slack_enabled = True
        settings.slack_bot_token = "xoxb-token"
        settings.slack_default_channel = "#alerts"
        settings.discord_enabled = False

        router = NotificationRouter(settings)
        assert len(router.providers) == 1
        assert "Slack" in type(router.providers[0]).__name__

    def test_discord_provider_created_when_enabled(self) -> None:
        settings = MagicMock()
        settings.slack_enabled = False
        settings.discord_enabled = True
        settings.discord_webhook_url = "https://discord.webhook"
        settings.discord_username = "Bot"

        router = NotificationRouter(settings)
        assert len(router.providers) == 1
        assert "Discord" in type(router.providers[0]).__name__

    def test_both_providers_created(self) -> None:
        settings = MagicMock()
        settings.slack_enabled = True
        settings.slack_bot_token = "xoxb-token"
        settings.slack_default_channel = "#incidents"
        settings.discord_enabled = True
        settings.discord_webhook_url = "https://discord.webhook"
        settings.discord_username = "Bot"

        router = NotificationRouter(settings)
        assert len(router.providers) == 2

    async def test_route_sends_to_all_providers(self) -> None:
        settings = MagicMock()
        settings.slack_enabled = True
        settings.slack_bot_token = "xoxb-token"
        settings.slack_default_channel = "#incidents"
        settings.discord_enabled = True
        settings.discord_webhook_url = "https://discord.webhook"
        settings.discord_username = "Bot"

        router = NotificationRouter(settings)
        for p in router.providers:
            p.send = AsyncMock()

        message = NotificationMessage(topic="test", title="Test", body="Body", source="test")
        await router.route(message)

        for p in router.providers:
            p.send.assert_awaited_once_with(message)

    async def test_route_continues_on_failure(self) -> None:
        settings = MagicMock()
        settings.slack_enabled = True
        settings.slack_bot_token = "xoxb-token"
        settings.slack_default_channel = "#incidents"
        settings.discord_enabled = True
        settings.discord_webhook_url = "https://discord.webhook"
        settings.discord_username = "Bot"

        router = NotificationRouter(settings)
        router._providers[0].send = AsyncMock(side_effect=RuntimeError("fail"))
        router._providers[1].send = AsyncMock()

        message = NotificationMessage(topic="test", title="Test", body="Body", source="test")
        await router.route(message)

        router._providers[1].send.assert_awaited_once()

    async def test_start_all_calls_start_on_providers(self) -> None:
        settings = MagicMock()
        settings.slack_enabled = True
        settings.slack_bot_token = "xoxb-token"
        settings.slack_default_channel = "#incidents"
        settings.discord_enabled = False

        router = NotificationRouter(settings)
        router._providers[0].start = AsyncMock()
        router._providers[0].close = AsyncMock()

        await router.start_all()
        router._providers[0].start.assert_awaited_once()

    async def test_stop_all_calls_close_on_providers(self) -> None:
        settings = MagicMock()
        settings.slack_enabled = True
        settings.slack_bot_token = "xoxb-token"
        settings.slack_default_channel = "#incidents"
        settings.discord_enabled = False

        router = NotificationRouter(settings)
        router._providers[0].close = AsyncMock()

        await router.stop_all()
        router._providers[0].close.assert_awaited_once()

    async def test_health_returns_provider_status(self) -> None:
        settings = MagicMock()
        settings.slack_enabled = True
        settings.slack_bot_token = "xoxb-token"
        settings.slack_default_channel = "#incidents"
        settings.discord_enabled = False

        router = NotificationRouter(settings)
        router._providers[0].health = AsyncMock(return_value=True)

        status = await router.health()
        assert "SlackNotificationProvider" in status
        assert status["SlackNotificationProvider"] is True
