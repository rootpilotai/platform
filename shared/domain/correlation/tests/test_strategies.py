from shared.domain.correlation.models import CorrelationContext
from shared.domain.correlation.strategies import (
    DependencyStrategy,
    ErrorSignatureStrategy,
    RequestIdStrategy,
    TimeWindowStrategy,
    TraceIdStrategy,
)
from shared.domain.graph.models import DependencyEdge
from shared.domain.graph.store import InMemoryGraphStore
from shared.domain.timeline.enums import TimelineEventCategory, TimelineEventSource
from shared.domain.timeline.models import TimelineEvent


def _event(
    event_id: str,
    service: str = "api",
    ts_offset: int = 0,
    trace_id: str | None = None,
    request_id: str | None = None,
    category: str = "metric_anomaly",
    metric: str = "cpu.usage",
) -> TimelineEvent:
    import datetime

    base = datetime.datetime(2026, 6, 12, 10, 0, 0, tzinfo=datetime.UTC)
    return TimelineEvent(
        event_id=event_id,
        category=TimelineEventCategory(category),
        source=TimelineEventSource.TELEMETRY,
        timestamp=base + datetime.timedelta(seconds=ts_offset),
        service_name=service,
        title=f"event {event_id}",
        trace_id=trace_id,
        request_id=request_id,
        metadata={"metric": metric, "value": "1.0"},
    )


class TestTimeWindowStrategy:
    async def test_matches_close_events(self) -> None:
        ctx = CorrelationContext(events=[_event("a", ts_offset=0), _event("b", ts_offset=10)])
        s = TimeWindowStrategy(window_seconds=60)
        matches = await s.correlate(ctx)
        assert len(matches) == 1
        assert matches[0].score > 0.8

    async def test_no_match_distant_events(self) -> None:
        ctx = CorrelationContext(events=[_event("a", ts_offset=0), _event("b", ts_offset=120)])
        s = TimeWindowStrategy(window_seconds=60)
        matches = await s.correlate(ctx)
        assert len(matches) == 0

    async def test_score_decays_with_distance(self) -> None:
        ctx = CorrelationContext(
            events=[_event("a", ts_offset=0), _event("b", ts_offset=30), _event("c", ts_offset=55)]
        )
        s = TimeWindowStrategy(window_seconds=60)
        matches = await s.correlate(ctx)
        scores = {(m.event_id_a, m.event_id_b): m.score for m in matches}
        assert scores[("a", "b")] > scores[("a", "c")]

    async def test_single_event_no_match(self) -> None:
        ctx = CorrelationContext(events=[_event("a")])
        s = TimeWindowStrategy()
        matches = await s.correlate(ctx)
        assert len(matches) == 0


class TestTraceIdStrategy:
    async def test_matches_events_sharing_trace(self) -> None:
        ctx = CorrelationContext(
            events=[
                _event("a", trace_id="trace-1"),
                _event("b", trace_id="trace-1"),
            ]
        )
        s = TraceIdStrategy()
        matches = await s.correlate(ctx)
        assert len(matches) == 1
        assert matches[0].score == 1.0

    async def test_no_match_different_traces(self) -> None:
        ctx = CorrelationContext(
            events=[
                _event("a", trace_id="trace-1"),
                _event("b", trace_id="trace-2"),
            ]
        )
        s = TraceIdStrategy()
        matches = await s.correlate(ctx)
        assert len(matches) == 0

    async def test_ignores_events_without_trace(self) -> None:
        ctx = CorrelationContext(events=[_event("a"), _event("b")])
        s = TraceIdStrategy()
        matches = await s.correlate(ctx)
        assert len(matches) == 0


class TestRequestIdStrategy:
    async def test_matches_events_sharing_request(self) -> None:
        ctx = CorrelationContext(
            events=[
                _event("a", request_id="req-1"),
                _event("b", request_id="req-1"),
            ]
        )
        s = RequestIdStrategy()
        matches = await s.correlate(ctx)
        assert len(matches) == 1
        assert matches[0].score == 1.0

    async def test_no_match_different_requests(self) -> None:
        ctx = CorrelationContext(
            events=[
                _event("a", request_id="req-1"),
                _event("b", request_id="req-2"),
            ]
        )
        s = RequestIdStrategy()
        matches = await s.correlate(ctx)
        assert len(matches) == 0


class TestDependencyStrategy:
    async def test_matches_dependent_services(self) -> None:
        store = InMemoryGraphStore()
        await store.add_edge(DependencyEdge(source="api", target="db"))
        ctx = CorrelationContext(events=[_event("a", service="api"), _event("b", service="db")])
        s = DependencyStrategy(store=store)
        matches = await s.correlate(ctx)
        assert len(matches) == 1
        assert matches[0].score == 1.0

    async def test_no_match_independent_services(self) -> None:
        store = InMemoryGraphStore()
        await store.add_edge(DependencyEdge(source="api", target="db"))
        ctx = CorrelationContext(events=[_event("a", service="api"), _event("c", service="worker")])
        s = DependencyStrategy(store=store)
        matches = await s.correlate(ctx)
        assert len(matches) == 0

    async def test_uses_edge_weight(self) -> None:
        store = InMemoryGraphStore()
        await store.add_edge(DependencyEdge(source="api", target="db", weight=0.5))
        ctx = CorrelationContext(events=[_event("a", service="api"), _event("b", service="db")])
        s = DependencyStrategy(store=store)
        matches = await s.correlate(ctx)
        assert matches[0].score == 0.5


class TestErrorSignatureStrategy:
    async def test_matches_error_metrics_together(self) -> None:
        ctx = CorrelationContext(
            events=[
                _event("a", metric="error.rate"),
                _event("b", metric="failure.count"),
            ]
        )
        s = ErrorSignatureStrategy()
        matches = await s.correlate(ctx)
        error_matches = [m for m in matches if m.metadata.get("match_type") == "error_to_error"]
        assert len(error_matches) == 1

    async def test_matches_error_to_anomaly(self) -> None:
        ctx = CorrelationContext(
            events=[
                _event("a", metric="error.rate"),
                _event("b", metric="cpu.usage", category="metric_anomaly"),
            ]
        )
        s = ErrorSignatureStrategy()
        matches = await s.correlate(ctx)
        cross_matches = [m for m in matches if m.metadata.get("match_type") == "error_to_anomaly"]
        assert len(cross_matches) == 1

    async def test_no_match_normal_metrics(self) -> None:
        ctx = CorrelationContext(
            events=[
                _event("a", metric="cpu.usage", category="metric_anomaly"),
                _event("b", metric="mem.usage", category="metric_anomaly"),
            ]
        )
        s = ErrorSignatureStrategy()
        matches = await s.correlate(ctx)
        assert len(matches) == 0
