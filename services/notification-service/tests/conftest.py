import sys
from collections.abc import AsyncGenerator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import NotificationServiceSettings
from app.main import create_app
from app.services.provider_router import NotificationRouter

from shared.contracts import EventBus


@pytest.fixture
def mock_event_bus() -> MagicMock:
    bus = MagicMock(spec=EventBus)
    bus.health = AsyncMock(return_value=True)
    bus.publish = AsyncMock()
    bus.start = AsyncMock()
    bus.close = AsyncMock()
    bus.subscribe = AsyncMock()
    return bus


@pytest.fixture
def mock_router() -> MagicMock:
    router = MagicMock(spec=NotificationRouter)
    router.start_all = AsyncMock()
    router.stop_all = AsyncMock()
    router.route = AsyncMock()
    router.health = AsyncMock(return_value={"SlackNotificationProvider": True})
    return router


@pytest.fixture
def test_settings() -> NotificationServiceSettings:
    return NotificationServiceSettings(
        service_name="notification-service",
        environment="test",
        debug=True,
        log_level="DEBUG",
        slack_enabled=True,
        slack_bot_token="xoxb-test",
        discord_enabled=False,
    )


@pytest.fixture
def app(
    mock_event_bus: MagicMock,
    mock_router: MagicMock,
    test_settings: NotificationServiceSettings,
) -> FastAPI:
    application = create_app()
    application.state.settings = test_settings
    application.state.event_bus = mock_event_bus
    application.state.router = mock_router
    return application


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
