from datetime import datetime, timezone

from shared.domain.correlation.enums import CorrelationSignal, CorrelationStrategyType
from shared.domain.correlation.models import CorrelationContext
from shared.domain.correlation.strategies.span_relation import SpanRelationStrategy
from shared.domain.timeline.enums import TimelineEventCategory, TimelineEventSource
from shared.domain.timeline.models import TimelineEvent

TRACE = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa0"


def _event(
    event_id: str,
    trace_id: str | None = TRACE,
    span_id: str | None = None,
    parent_span_id: str | None = None,
) -> TimelineEvent:
    return TimelineEvent(
        event_id=event_id,
        category=TimelineEventCategory.METRIC_ANOMALY,
        source=TimelineEventSource.TELEMETRY,
        timestamp=datetime(2026, 6, 14, 10, 0, 0, tzinfo=timezone.utc),
        service_name="api",
        title=f"event {event_id}",
        trace_id=trace_id,
        span_id=span_id,
        parent_span_id=parent_span_id,
    )


class TestSpanRelationStrategy:
    def setup_method(self) -> None:
        self.strategy = SpanRelationStrategy()

    async def test_empty_events(self) -> None:
        ctx = CorrelationContext(events=[])
        matches = await self.strategy.correlate(ctx)
        assert matches == []

    async def test_single_event_no_match(self) -> None:
        ctx = CorrelationContext(events=[_event("a", span_id="s1")])
        matches = await self.strategy.correlate(ctx)
        assert matches == []

    async def test_parent_child_scores_highest(self) -> None:
        ctx = CorrelationContext(events=[
            _event("a", span_id="s1"),
            _event("b", span_id="s2", parent_span_id="s1"),
        ])
        matches = await self.strategy.correlate(ctx)
        assert len(matches) == 1
        assert matches[0].score == SpanRelationStrategy.PARENT_CHILD_SCORE
        assert matches[0].signal == CorrelationSignal.SPAN_PARENT_CHILD

    async def test_siblings_score_middle(self) -> None:
        ctx = CorrelationContext(events=[
            _event("a", span_id="s1", parent_span_id="s0"),
            _event("b", span_id="s2", parent_span_id="s0"),
        ])
        matches = await self.strategy.correlate(ctx)
        assert len(matches) == 1
        assert matches[0].score == SpanRelationStrategy.SIBLING_SCORE
        assert matches[0].signal == CorrelationSignal.SPAN_SIBLING

    async def test_same_trace_no_span_relation_scores_lowest(self) -> None:
        ctx = CorrelationContext(events=[
            _event("a", trace_id=TRACE, span_id="s1"),
            _event("b", trace_id=TRACE, span_id="s2"),
        ])
        matches = await self.strategy.correlate(ctx)
        assert len(matches) == 1
        assert matches[0].score == SpanRelationStrategy.SAME_TRACE_SCORE
        assert matches[0].signal == CorrelationSignal.TRACE_MATCH

    async def test_events_without_span_ids_fall_back_to_same_trace(self) -> None:
        ctx = CorrelationContext(events=[
            _event("a", trace_id=TRACE),
            _event("b", trace_id=TRACE),
        ])
        matches = await self.strategy.correlate(ctx)
        assert len(matches) == 1
        assert matches[0].score == SpanRelationStrategy.SAME_TRACE_SCORE

    async def test_different_traces_no_match(self) -> None:
        ctx = CorrelationContext(events=[
            _event("a", trace_id="t1", span_id="s1"),
            _event("b", trace_id="t2", span_id="s2"),
        ])
        matches = await self.strategy.correlate(ctx)
        assert matches == []

    async def test_metadata_includes_trace_id(self) -> None:
        ctx = CorrelationContext(events=[
            _event("a", span_id="s1"),
            _event("b", span_id="s2", parent_span_id="s1"),
        ])
        matches = await self.strategy.correlate(ctx)
        assert matches[0].metadata.get("trace_id") == TRACE

    async def test_in_engine_default_pipeline(self) -> None:
        from shared.domain.correlation.engine import CorrelationEngine

        engine = CorrelationEngine()
        events = [
            _event("a", span_id="s1"),
            _event("b", span_id="s2", parent_span_id="s1"),
            _event("c"),
        ]
        result = await engine.correlate(events)
        assert result.total_events == 3
        assert len(result.groups) >= 1
        assert CorrelationStrategyType.SPAN_RELATION.value in result.strategy_counts
