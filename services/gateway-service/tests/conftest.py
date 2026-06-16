import sys
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import GatewayServiceSettings
from app.main import create_app

from shared.domain.investigation.models import (
    IncidentProgression,
    InvestigationResult,
    RCASummary,
    RemediationStep,
    RootCause,
)


@pytest.fixture
def mock_incident_store() -> MagicMock:
    store = MagicMock()
    store.health = AsyncMock(return_value=True)
    store.get = AsyncMock(return_value=None)
    store.count = AsyncMock(return_value=0)
    store.store = AsyncMock()
    store.delete = AsyncMock()

    async def _empty_search(*args, **kwargs):
        return
        yield  # type: ignore

    store.search = _empty_search
    return store


@pytest.fixture
def mock_investigation_store() -> MagicMock:
    store = MagicMock()
    store.health = AsyncMock(return_value=True)
    store.get = AsyncMock(return_value=None)
    store.get_by_incident = AsyncMock(return_value=None)
    store.count = AsyncMock(return_value=0)
    store.latest = AsyncMock(return_value=None)
    store.store = AsyncMock()

    async def _empty_search(*args, **kwargs):
        return
        yield  # type: ignore

    store.search = _empty_search
    return store


@pytest.fixture
def mock_api_key_store() -> MagicMock:
    store = MagicMock()
    store.health = AsyncMock(return_value=True)
    store.validate = AsyncMock(return_value=True)
    return store


@pytest.fixture
def test_settings() -> GatewayServiceSettings:
    return GatewayServiceSettings(
        service_name="gateway-service",
        environment="test",
        debug=True,
        log_level="DEBUG",
        api_keys="test-key-1",
    )


@pytest.fixture
def app(
    mock_incident_store: MagicMock,
    mock_investigation_store: MagicMock,
    mock_api_key_store: MagicMock,
    test_settings: GatewayServiceSettings,
) -> FastAPI:
    application = create_app()
    application.state.settings = test_settings
    application.state.incident_store = mock_incident_store
    application.state.investigation_store = mock_investigation_store
    application.state.api_key_store = mock_api_key_store
    return application


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def sample_investigation_result() -> InvestigationResult:
    return InvestigationResult(
        summary=RCASummary(
            incident_id="inc-001",
            title="High CPU on api-gateway",
            root_causes=[
                RootCause(
                    service="api-gateway",
                    confidence=0.85,
                    evidence=["CPU at 95%", "Memory at 80%"],
                    explanation="Traffic spike caused resource exhaustion",
                ),
            ],
            progression=IncidentProgression(
                sequence=["CPU rose to 95%", "Latency exceeded 5s"],
                timeline_summary="Degradation over 10 minutes",
                key_transitions=["Alert triggered at 14:30"],
            ),
            remediation=[
                RemediationStep(
                    action="Scale up api-gateway",
                    service="api-gateway",
                    priority="high",
                    expected_impact="Reduced CPU load",
                ),
            ],
            overall_confidence=0.92,
            generated_at=datetime(2026, 6, 15, 12, 0, 0, tzinfo=UTC),
        ),
        duration_ms=1500.0,
    )


@pytest.fixture
def sample_incident_context() -> dict:
    return {
        "incident_id": "inc-001",
        "primary_service": "api-gateway",
        "severity": "CRITICAL",
        "title": "High CPU on api-gateway",
        "detected_at": "2026-06-15T12:00:00Z",
        "aggregated_at": "2026-06-15T12:05:00Z",
        "event_count": 150,
        "service_count": 3,
        "trace_count": 45,
        "correlation_groups": [
            {
                "group_id": "g-1",
                "event_ids": ["e-1", "e-2"],
                "composite_score": 0.95,
                "signals": [],
                "services": ["api-gateway", "auth-service"],
                "trace_id": None,
                "span_count": 0,
                "window_start": None,
                "window_end": None,
            },
        ],
        "ungrouped_events": [],
        "impacts": [],
        "trace_groups": [],
        "timeline": None,
    }
