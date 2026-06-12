from shared.domain.correlation.engine import CorrelationEngine
from shared.domain.graph.models import DependencyEdge
from shared.domain.graph.store import InMemoryGraphStore
from shared.domain.timeline.enums import TimelineEventCategory, TimelineEventSource
from shared.domain.timeline.models import TimelineEvent


def _event(
    event_id: str,
    service: str = "api",
    ts_offset: int = 0,
    trace_id: str | None = None,
    metric: str = "cpu.usage",
    category: str = "metric_anomaly",
) -> TimelineEvent:
    import datetime

    base = datetime.datetime(2026, 6, 12, 10, 0, 0, tzinfo=datetime.timezone.utc)
    return TimelineEvent(
        event_id=event_id,
        category=TimelineEventCategory(category),
        source=TimelineEventSource.TELEMETRY,
        timestamp=base + datetime.timedelta(seconds=ts_offset),
        service_name=service,
        title=f"event {event_id}",
        trace_id=trace_id,
        metadata={"metric": metric, "value": "1.0"},
    )


class TestFullFlow:
    async def test_empty_events(self) -> None:
        engine = CorrelationEngine()
        result = await engine.correlate([])
        assert result.total_events == 0
        assert len(result.groups) == 0

    async def test_single_event_no_group(self) -> None:
        engine = CorrelationEngine()
        result = await engine.correlate([_event("a")])
        assert result.total_events == 1
        assert len(result.groups) == 0

    async def test_two_correlated_events(self) -> None:
        engine = CorrelationEngine()
        result = await engine.correlate([
            _event("a", trace_id="t1"),
            _event("b", trace_id="t1"),
        ])
        assert result.total_events == 2
        assert len(result.groups) == 1

    async def test_noise_filtered(self) -> None:
        engine = CorrelationEngine()
        result = await engine.correlate([
            _event("a", ts_offset=0),
            _event("b", ts_offset=100),
        ])
        assert result.total_events == 2
        assert len(result.groups) == 0

    async def test_with_dependency_store(self) -> None:
        store = InMemoryGraphStore()
        await store.add_edge(DependencyEdge(source="api", target="db"))
        engine = CorrelationEngine(store=store)
        result = await engine.correlate([
            _event("a", service="api"),
            _event("b", service="db"),
        ])
        assert len(result.groups) == 1

    async def test_strategy_counts_reported(self) -> None:
        engine = CorrelationEngine()
        result = await engine.correlate([
            _event("a", trace_id="t1"),
            _event("b", trace_id="t1"),
        ])
        assert result.strategy_counts.get("trace_id", 0) == 1
