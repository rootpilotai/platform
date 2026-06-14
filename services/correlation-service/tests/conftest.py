import sys
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import CorrelationServiceSettings
from app.main import create_app

from shared.domain.correlation.engine import CorrelationEngine
from shared.domain.timeline.services import TimelineReconstructor


@pytest.fixture
def test_settings() -> CorrelationServiceSettings:
    return CorrelationServiceSettings(
        service_name="correlation-service",
        environment="test",
        debug=True,
        log_level="DEBUG",
        timeline_window_duration=300,
    )


@pytest.fixture
def app(
    test_settings: CorrelationServiceSettings,
) -> FastAPI:
    application = create_app()
    application.state.settings = test_settings
    application.state.reconstructor = TimelineReconstructor(
        window_duration_seconds=test_settings.timeline_window_duration,
    )
    application.state.engine = CorrelationEngine()
    return application


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
