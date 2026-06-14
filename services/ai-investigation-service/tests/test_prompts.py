"""Tests for RCA prompt templates."""

from typing import Any

from app.prompts.rca import RCAPrompts

from shared.domain.incident.context.models import (
    AggregatedCorrelationGroup,
    AggregatedTimeline,
    ImpactAnalysis,
    IncidentContext,
)


def _make_context(**overrides: Any) -> IncidentContext:
    from datetime import UTC, datetime

    defaults: dict = dict(
        incident_id="inc-001",
        primary_service="api",
        severity="CRITICAL",
        title="API degradation",
        detected_at=datetime.now(UTC),
    )
    defaults.update(overrides)
    return IncidentContext(**defaults)


class TestRCAPrompts:
    def test_build_rca_messages_returns_system_and_user(self) -> None:
        ctx = _make_context()
        messages = RCAPrompts.build_rca_messages(ctx)
        assert len(messages) == 2
        assert messages[0].role == "system"
        assert messages[1].role == "user"

    def test_system_prompt_includes_sre_context(self) -> None:
        ctx = _make_context()
        messages = RCAPrompts.build_rca_messages(ctx)
        assert "senior Site Reliability Engineer" in messages[0].content

    def test_format_context_includes_incident_metadata(self) -> None:
        ctx = _make_context(incident_id="inc-999", title="Test incident", severity="HIGH")
        text = RCAPrompts._format_context(ctx)
        assert "inc-999" in text
        assert "Test incident" in text
        assert "HIGH" in text

    def test_format_context_with_timeline(self) -> None:
        from datetime import UTC, datetime

        ctx = _make_context()
        ctx.timeline = AggregatedTimeline(
            incident_id="inc-001",
            primary_service="api",
            total_events=10,
            window_count=2,
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC),
            duration_seconds=300.0,
        )
        text = RCAPrompts._format_context(ctx)
        assert "300" in text
        assert "10" in text

    def test_format_context_with_correlation_groups(self) -> None:
        from shared.domain.correlation.enums import CorrelationSignal

        ctx = _make_context()
        ctx.correlation_groups = [
            AggregatedCorrelationGroup(
                group_id="g1",
                event_ids=["a", "b"],
                composite_score=0.95,
                signals=[CorrelationSignal.TRACE_MATCH],
                services=["api", "db"],
            )
        ]
        ctx.event_count = 5
        text = RCAPrompts._format_context(ctx)
        assert "0.95" in text
        assert "trace_match" in text
        assert "api" in text

    def test_format_context_with_impacts(self) -> None:
        ctx = _make_context()
        ctx.impacts = [
            ImpactAnalysis(
                service="api",
                upstream_causes=["gateway"],
                downstream_impact=["cache"],
                propagation_paths=[["gateway", "api", "cache"]],
            )
        ]
        text = RCAPrompts._format_context(ctx)
        assert "gateway" in text
        assert "cache" in text
        assert "propagation" in text.lower()

    def test_format_context_with_trace_groups(self) -> None:
        from shared.domain.correlation.grouping.models import TraceGroup

        ctx = _make_context()
        ctx.trace_groups = [
            TraceGroup(trace_id="t1", event_ids=["a", "b"], service_names=["api-gateway"], span_count=5),
        ]
        text = RCAPrompts._format_context(ctx)
        assert "t1" in text
        assert "api-gateway" in text

    def test_format_context_with_ungrouped_events(self) -> None:
        ctx = _make_context()
        ctx.ungrouped_events = ["e1", "e2"]
        text = RCAPrompts._format_context(ctx)
        assert "ungrouped" in text.lower()
        assert "e1" in text or "2 events" in text

    def test_format_context_empty_minimal(self) -> None:
        ctx = _make_context()
        text = RCAPrompts._format_context(ctx)
        assert "## Incident" in text
        assert "Incident" in text
