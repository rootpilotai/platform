"""Tests for incident context models."""

from datetime import UTC, datetime

from shared.domain.correlation.enums import CorrelationSignal
from shared.domain.incident.context.models import (
    AggregatedCorrelationGroup,
    AggregatedTimeline,
    ImpactAnalysis,
    IncidentContext,
)


class TestAggregatedCorrelationGroup:
    async def test_minimal_group(self) -> None:
        group = AggregatedCorrelationGroup(
            group_id="g-1",
            event_ids=["e1", "e2"],
            composite_score=0.85,
        )
        assert group.group_id == "g-1"
        assert group.composite_score == 0.85
        assert group.signals == []
        assert group.services == []
        assert group.trace_id is None
        assert group.span_count == 0

    async def test_group_with_all_fields(self) -> None:
        ts = datetime.now(UTC)
        group = AggregatedCorrelationGroup(
            group_id="g-2",
            event_ids=["e1"],
            composite_score=0.9,
            signals=[CorrelationSignal.TRACE_MATCH, CorrelationSignal.ERROR_PATTERN],
            services=["api", "db"],
            trace_id="trace-abc",
            span_count=3,
            window_start=ts,
            window_end=ts,
        )
        assert CorrelationSignal.TRACE_MATCH in group.signals
        assert group.services == ["api", "db"]

    async def test_json_round_trip(self) -> None:
        original = AggregatedCorrelationGroup(
            group_id="g-3",
            event_ids=["e1"],
            composite_score=0.5,
        )
        restored = AggregatedCorrelationGroup.model_validate_json(original.model_dump_json())
        assert restored == original


class TestAggregatedTimeline:
    async def test_empty_timeline(self) -> None:
        timeline = AggregatedTimeline(incident_id="inc-1", primary_service="api")
        assert timeline.total_events == 0
        assert timeline.window_count == 0
        assert timeline.duration_seconds is None

    async def test_timeline_with_duration(self) -> None:
        start = datetime(2026, 6, 14, 10, 0, 0, tzinfo=UTC)
        end = datetime(2026, 6, 14, 10, 10, 0, tzinfo=UTC)
        timeline = AggregatedTimeline(
            incident_id="inc-1",
            primary_service="api",
            total_events=5,
            window_count=2,
            start_time=start,
            end_time=end,
            duration_seconds=600.0,
        )
        assert timeline.duration_seconds == 600.0
        assert timeline.start_time == start


class TestImpactAnalysis:
    async def test_empty_impact(self) -> None:
        impact = ImpactAnalysis(service="api")
        assert impact.service == "api"
        assert impact.upstream_causes == []
        assert impact.downstream_impact == []

    async def test_impact_with_paths(self) -> None:
        impact = ImpactAnalysis(
            service="db",
            upstream_causes=["api-gateway", "user-service"],
            downstream_impact=["cache"],
            propagation_paths=[["api-gateway", "user-service", "db"]],
        )
        assert len(impact.propagation_paths) == 1
        assert impact.propagation_paths[0] == ["api-gateway", "user-service", "db"]


class TestIncidentContext:
    async def test_minimal_context(self) -> None:
        ts = datetime.now(UTC)
        context = IncidentContext(
            incident_id="inc-1",
            primary_service="api",
            detected_at=ts,
        )
        assert context.incident_id == "inc-1"
        assert context.severity == "UNKNOWN"
        assert context.event_count == 0
        assert context.timeline is None

    async def test_inherited_counts_from_event_data(self) -> None:
        ts = datetime.now(UTC)
        context = IncidentContext(
            incident_id="inc-2",
            primary_service="db",
            detected_at=ts,
            event_count=100,
            service_count=3,
            trace_count=2,
            correlation_groups=[
                AggregatedCorrelationGroup(
                    group_id="g-1",
                    event_ids=["e1", "e2"],
                    composite_score=0.75,
                ),
            ],
            ungrouped_events=["e3"],
        )
        assert context.event_count == 100
        assert context.service_count == 3
        assert context.trace_count == 2
        assert len(context.correlation_groups) == 1
        assert len(context.ungrouped_events) == 1
        assert context.aggregated_at is not None

    async def test_json_round_trip(self) -> None:
        ts = datetime.now(UTC)
        original = IncidentContext(
            incident_id="inc-3",
            primary_service="api",
            detected_at=ts,
            title="High error rate on api",
            severity="CRITICAL",
        )
        restored = IncidentContext.model_validate_json(original.model_dump_json())
        assert restored.incident_id == original.incident_id
        assert restored.title == original.title
        assert restored.severity == original.severity
