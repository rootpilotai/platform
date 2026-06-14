"""Tests for InvestigationPipeline."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from app.pipeline import InvestigationPipeline

from shared.contracts.interfaces.llm_provider import LLMProvider
from shared.domain.incident.context.models import IncidentContext
from shared.domain.investigation.models import (
    IncidentProgression,
    InvestigationResult,
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
            sequence=["deploy", "degradation"], timeline_summary="post-deploy regression", key_transitions=["paging"]
        )
        step = RemediationStep(action="rollback", service="api", priority="critical", expected_impact="restore service")
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
def incident_context() -> IncidentContext:
    return IncidentContext(
        incident_id="inc-001",
        primary_service="api",
        severity="CRITICAL",
        title="API degradation",
        detected_at=datetime.now(UTC),
    )


class TestInvestigationPipeline:
    async def test_run_returns_investigation_result(
        self, mock_llm: LLMProvider, incident_context: IncidentContext
    ) -> None:
        pipeline = InvestigationPipeline(mock_llm)
        result = await pipeline.run(incident_context)
        assert isinstance(result, InvestigationResult)
        assert isinstance(result.summary, RCASummary)

    async def test_run_populates_summary_fields(self, mock_llm: LLMProvider, incident_context: IncidentContext) -> None:
        pipeline = InvestigationPipeline(mock_llm)
        result = await pipeline.run(incident_context)
        assert result.summary.incident_id == "inc-001"
        assert result.summary.title == "API degradation"
        assert len(result.summary.root_causes) == 1
        assert result.summary.root_causes[0].service == "api"
        assert len(result.summary.remediation) == 1

    async def test_run_measures_duration(self, mock_llm: LLMProvider, incident_context: IncidentContext) -> None:
        pipeline = InvestigationPipeline(mock_llm)
        result = await pipeline.run(incident_context)
        assert result.duration_ms > 0

    async def test_run_passes_context_to_llm(self, mock_llm: LLMProvider, incident_context: IncidentContext) -> None:
        from typing import cast
        from unittest.mock import AsyncMock

        pipeline = InvestigationPipeline(mock_llm)
        await pipeline.run(incident_context)
        generated = cast(AsyncMock, mock_llm.generate_structured)
        generated.assert_awaited_once()
        assert generated.await_args is not None
        args, kwargs = generated.await_args
        assert len(args[0]) == 2  # system + user message
        assert args[1] == RCASummary

    async def test_run_with_complex_context(self, mock_llm: LLMProvider) -> None:
        from shared.domain.correlation.grouping.models import TraceGroup

        ctx = IncidentContext(
            incident_id="inc-002",
            primary_service="gateway",
            severity="HIGH",
            title="Gateway timeout",
            detected_at=datetime.now(UTC),
            event_count=100,
            service_count=3,
            trace_count=5,
            correlation_groups=[],
            trace_groups=[
                TraceGroup(
                    trace_id="t1",
                    event_ids=["a", "b", "c"],
                    service_names=["gateway"],
                    span_count=10,
                )
            ],
        )
        pipeline = InvestigationPipeline(mock_llm)
        result = await pipeline.run(ctx)
        assert result.summary.incident_id == "inc-001"  # mock returns inc-001 regardless of context
