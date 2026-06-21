"""Integration tests for the incident context aggregation pipeline."""

from datetime import UTC, datetime, timedelta

import pytest

from shared.domain.graph.enums import DependencyType
from shared.domain.graph.models import DependencyEdge
from shared.domain.graph.store import InMemoryGraphStore
from shared.domain.incident.context.aggregator import IncidentContextAggregator
from shared.domain.incident.context.builders import (
    ContextBuilder,
    ContextBuilderState,
    CorrelationBuilder,
    ImpactBuilder,
    TimelineBuilder,
    TraceBuilder,
)
from shared.domain.timeline.enums import TimelineEventCategory, TimelineEventSource
from shared.domain.timeline.models import TimelineEvent


@pytest.fixture
def events() -> list[TimelineEvent]:
    base = datetime(2026, 6, 14, 10, 0, 0, tzinfo=UTC)
    return [
        TimelineEvent(
            event_id="e1",
            category=TimelineEventCategory.FAILURE,
            source=TimelineEventSource.TELEMETRY,
            timestamp=base,
            service_name="api",
            title="error burst",
            trace_id="trace-abc",
            span_id="span-1",
        ),
        TimelineEvent(
            event_id="e2",
            category=TimelineEventCategory.FAILURE,
            source=TimelineEventSource.TELEMETRY,
            timestamp=base + timedelta(seconds=30),
            service_name="api",
            title="error burst",
            trace_id="trace-abc",
            span_id="span-2",
            parent_span_id="span-1",
        ),
        TimelineEvent(
            event_id="e3",
            category=TimelineEventCategory.RETRY,
            source=TimelineEventSource.TELEMETRY,
            timestamp=base + timedelta(minutes=3),
            service_name="db",
            title="retry",
            trace_id="trace-xyz",
        ),
        TimelineEvent(
            event_id="e4",
            category=TimelineEventCategory.RECOVERY,
            source=TimelineEventSource.TELEMETRY,
            timestamp=base + timedelta(minutes=6),
            service_name="api",
            title="recovered",
        ),
    ]


class TestAggregatorNoBuilders:
    async def test_minimal_context_with_no_builders(self) -> None:
        ts = datetime.now(UTC)
        aggregator = IncidentContextAggregator(builders=[])
        context = await aggregator.aggregate(
            incident_id="inc-1",
            primary_service="api",
            events=[],
            detected_at=ts,
        )
        assert context.incident_id == "inc-1"
        assert context.timeline is None
        assert context.correlation_groups == []
        assert context.ungrouped_events == []
        assert context.impacts == []
        assert context.trace_groups == []
        assert context.event_count == 0

    async def test_context_counts_metadata(self) -> None:
        ts = datetime.now(UTC)
        aggregator = IncidentContextAggregator(builders=[])
        context = await aggregator.aggregate(
            incident_id="inc-1",
            primary_service="api",
            events=[],
            severity="CRITICAL",
            title="API is down",
            detected_at=ts,
        )
        assert context.severity == "CRITICAL"
        assert context.title == "API is down"


class TestAggregatorAllBuilders:
    @pytest.fixture
    async def graph_store(self) -> InMemoryGraphStore:
        s = InMemoryGraphStore()
        await s.add_edge(DependencyEdge(source="web", target="api", dependency_type=DependencyType.SYNCHRONOUS))
        await s.add_edge(DependencyEdge(source="api", target="db", dependency_type=DependencyType.DATABASE))
        return s

    @pytest.fixture
    def aggregator(self, graph_store: InMemoryGraphStore) -> IncidentContextAggregator:
        return IncidentContextAggregator(
            builders=[
                TimelineBuilder(),
                CorrelationBuilder(),
                TraceBuilder(),
                ImpactBuilder(graph_store),
            ]
        )

    async def test_aggregator_populates_all_sections(
        self,
        aggregator: IncidentContextAggregator,
        events: list[TimelineEvent],
    ) -> None:
        ts = datetime.now(UTC)
        context = await aggregator.aggregate(
            incident_id="inc-agg-1",
            primary_service="api",
            events=events,
            detected_at=ts,
        )

        assert context.incident_id == "inc-agg-1"
        assert context.event_count == 4

        assert context.timeline is not None
        assert context.timeline.total_events == 4
        assert context.timeline.primary_service == "api"

        assert 1 <= len(context.timeline.windows) <= 3
        assert len(context.ungrouped_events) >= 0

        assert len(context.trace_groups) >= 1
        trace_ids = {g.trace_id for g in context.trace_groups}
        assert "trace-abc" in trace_ids

        assert len(context.impacts) >= 1
        svcs = {i.service for i in context.impacts}
        assert "api" in svcs

    async def test_aggregator_handles_empty_events(
        self,
        aggregator: IncidentContextAggregator,
    ) -> None:
        ts = datetime.now(UTC)
        context = await aggregator.aggregate(
            incident_id="inc-empty",
            primary_service="api",
            events=[],
            detected_at=ts,
        )
        assert context.event_count == 0
        assert context.timeline is None
        assert context.correlation_groups == []
        assert context.impacts == []
        assert context.trace_groups == []


class TestCustomBuilder:
    async def test_builders_executed_by_weight_order(self) -> None:
        order: list[int] = []

        class BuilderA(ContextBuilder):
            weight = 20

            async def build(self, state: ContextBuilderState) -> None:  # noqa: ARG002
                order.append(20)

        class BuilderB(ContextBuilder):
            weight = 10

            async def build(self, state: ContextBuilderState) -> None:  # noqa: ARG002
                order.append(10)

        class BuilderC(ContextBuilder):
            weight = 30

            async def build(self, state: ContextBuilderState) -> None:  # noqa: ARG002
                order.append(30)

        aggregator = IncidentContextAggregator(builders=[BuilderA(), BuilderB(), BuilderC()])
        ts = datetime.now(UTC)
        await aggregator.aggregate("inc-1", "api", [], detected_at=ts)
        assert order == [10, 20, 30]
