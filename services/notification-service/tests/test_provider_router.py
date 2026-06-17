"""Tests for the NotificationRouter."""

from unittest.mock import AsyncMock, MagicMock

from app.services.provider_router import NotificationRouter

from shared.contracts.interfaces.notification_provider import NotificationProvider
from shared.contracts.schemas.notification import NotificationMessage


def _mock_provider(name: str = "MockProvider") -> NotificationProvider:
    namespace = {"__slots__": ()}
    cls = type(name, (MagicMock,), namespace)
    provider = cls(spec=NotificationProvider)
    provider.start = AsyncMock()
    provider.close = AsyncMock()
    provider.send = AsyncMock()
    provider.health = AsyncMock(return_value=True)
    return provider


class TestNotificationRouter:
    def test_no_providers_when_disabled(self) -> None:
        router = NotificationRouter([])
        assert len(router.providers) == 0

    def test_slack_provider_created_when_enabled(self) -> None:
        slack = _mock_provider("SlackNotificationProvider")
        router = NotificationRouter([slack])
        assert len(router.providers) == 1
        assert "Slack" in type(router.providers[0]).__name__

    def test_discord_provider_created_when_enabled(self) -> None:
        discord = _mock_provider("DiscordNotificationProvider")
        router = NotificationRouter([discord])
        assert len(router.providers) == 1
        assert "Discord" in type(router.providers[0]).__name__

    def test_both_providers_created(self) -> None:
        slack = _mock_provider("SlackNotificationProvider")
        discord = _mock_provider("DiscordNotificationProvider")
        router = NotificationRouter([slack, discord])
        assert len(router.providers) == 2

    async def test_route_sends_to_all_providers(self) -> None:
        slack = _mock_provider("SlackNotificationProvider")
        discord = _mock_provider("DiscordNotificationProvider")
        router = NotificationRouter([slack, discord])

        message = NotificationMessage(topic="test", title="Test", body="Body", source="test")
        await router.route(message)

        slack.send.assert_awaited_once_with(message)
        discord.send.assert_awaited_once_with(message)

    async def test_route_continues_on_failure(self) -> None:
        slack = _mock_provider("SlackNotificationProvider")
        discord = _mock_provider("DiscordNotificationProvider")
        slack.send = AsyncMock(side_effect=RuntimeError("fail"))
        router = NotificationRouter([slack, discord])

        message = NotificationMessage(topic="test", title="Test", body="Body", source="test")
        await router.route(message)

        discord.send.assert_awaited_once()

    async def test_start_all_calls_start_on_providers(self) -> None:
        slack = _mock_provider("SlackNotificationProvider")
        router = NotificationRouter([slack])

        await router.start_all()
        slack.start.assert_awaited_once()

    async def test_stop_all_calls_close_on_providers(self) -> None:
        slack = _mock_provider("SlackNotificationProvider")
        router = NotificationRouter([slack])

        await router.stop_all()
        slack.close.assert_awaited_once()

    async def test_health_returns_provider_status(self) -> None:
        slack = _mock_provider("SlackNotificationProvider")
        slack.health = AsyncMock(return_value=True)
        router = NotificationRouter([slack])

        status = await router.health()
        assert "SlackNotificationProvider" in status
        assert status["SlackNotificationProvider"] is True
