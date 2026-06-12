import sys
from collections.abc import AsyncGenerator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import IngestionServiceSettings
from app.dependencies import get_event_bus, get_settings
from app.main import create_app
from shared.contracts import EventBus


@pytest.fixture
def mock_event_bus() -> MagicMock:
    bus = MagicMock(spec=EventBus)
    bus.health = AsyncMock(return_value=True)
    bus.publish = AsyncMock()
    bus.start = AsyncMock()
    bus.close = AsyncMock()
    return bus


@pytest.fixture
def test_settings() -> IngestionServiceSettings:
    return IngestionServiceSettings(
        service_name="ingestion-service",
        environment="test",
        debug=True,
        log_level="DEBUG",
        event_bus_url="memory://test",
    )


@pytest.fixture
def app(
    mock_event_bus: MagicMock,
    test_settings: IngestionServiceSettings,
) -> FastAPI:
    application = create_app()
    application.state.settings = test_settings
    application.state.event_bus = mock_event_bus
    return application


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
