"""Tests for the investigation.requested event consumer."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from app.main import _handle_investigation_requested
from app.pipeline import InvestigationPipeline

from shared.contracts import Event
from shared.contracts.events import EventTopic, InvestigationRequestedEvent, ServiceName
from shared.contracts.interfaces.llm_provider import LLMProvider
from shared.domain.incident.context.models import IncidentContext
from shared.domain.investigation.models import (
    IncidentProgression,
    RCASummary,
    RemediationStep,
    RootCause,
)


@pytest.fixture
def mock_llm() -> LLMProvider:
    provider = AsyncMock(spec=LLMProvider)

    async def structured_side_effect(messages, schema, model=None):
        rc = RootCause(service="api", confidence=0.85, evidence=["5xx spike"], explanation="timeout cascade")
        prog = IncidentProgression(
            sequence=["deploy", "degradation"],
            timeline_summary="post-deploy regression",
            key_transitions=["paging"],
        )
        step = RemediationStep(action="rollback", service="api", priority="critical", expected_impact="restore")
        return RCASummary(
            incident_id="inc-001",
            title="API degradation",
            root_causes=[rc],
            progression=prog,
            remediation=[step],
            overall_confidence=0.85,
        )

    provider.generate_structured = AsyncMock(side_effect=structured_side_effect)
    return provider


@pytest.fixture
def pipeline(mock_llm: LLMProvider) -> InvestigationPipeline:
    return InvestigationPipeline(mock_llm)


@pytest.fixture
def mock_event_bus() -> AsyncMock:
    bus = AsyncMock()
    bus.publish = AsyncMock()
    return bus


def _make_context_dict() -> dict:
    return IncidentContext(
        incident_id="inc-001",
        primary_service="api",
        severity="ERROR",
        title="API degradation",
        detected_at=datetime.now(UTC),
    ).model_dump()


@pytest.fixture
def investigation_event() -> Event:
    requested = InvestigationRequestedEvent(
        investigation_id="inv-001",
        incident_id="inc-001",
        context=_make_context_dict(),
    )
    return Event(
        source=ServiceName.CORRELATION,
        topic=EventTopic.INVESTIGATION_REQUESTED,
        payload=requested.model_dump(),
    )


class TestInvestigationRequestedConsumer:
    async def test_handles_event_and_publishes_completed(
        self,
        investigation_event: Event,
        pipeline: InvestigationPipeline,
        mock_event_bus: AsyncMock,
    ) -> None:
        await _handle_investigation_requested(investigation_event, pipeline, mock_event_bus)

        mock_event_bus.publish.assert_awaited_once()
        published: Event = mock_event_bus.publish.await_args[0][0]
        assert published.topic == EventTopic.INVESTIGATION_COMPLETED
        assert published.payload["incident_id"] == "inc-001"
        assert "summary" in published.payload

    async def test_runs_pipeline_with_reconstructed_context(
        self,
        investigation_event: Event,
        mock_llm: LLMProvider,
        mock_event_bus: AsyncMock,
    ) -> None:
        pipeline = InvestigationPipeline(mock_llm)
        await _handle_investigation_requested(investigation_event, pipeline, mock_event_bus)

        mock_llm.generate_structured.assert_awaited_once()

    async def test_handles_malformed_payload_gracefully(
        self,
        pipeline: InvestigationPipeline,
        mock_event_bus: AsyncMock,
    ) -> None:
        bad_event = Event(
            source=ServiceName.CORRELATION,
            topic=EventTopic.INVESTIGATION_REQUESTED,
            payload={"bad": "data"},
        )
        await _handle_investigation_requested(bad_event, pipeline, mock_event_bus)
        mock_event_bus.publish.assert_not_called()

    async def test_publishes_completed_with_summary(
        self,
        investigation_event: Event,
        pipeline: InvestigationPipeline,
        mock_event_bus: AsyncMock,
    ) -> None:
        await _handle_investigation_requested(investigation_event, pipeline, mock_event_bus)

        published: Event = mock_event_bus.publish.await_args[0][0]
        summary = published.payload.get("summary", {})
        assert isinstance(summary, dict)
        assert "root_causes" in summary
        assert "title" in summary
