import pytest

from shared.domain.correlation.models import CorrelationContext
from shared.domain.correlation.pipeline import CorrelationPipeline
from shared.domain.correlation.strategies import TimeWindowStrategy, TraceIdStrategy
from shared.domain.timeline.enums import TimelineEventCategory, TimelineEventSource
from shared.domain.timeline.models import TimelineEvent


def _event(event_id: str, ts_offset: int = 0, trace_id: str | None = None) -> TimelineEvent:
    import datetime

    base = datetime.datetime(2026, 6, 12, 10, 0, 0, tzinfo=datetime.UTC)
    return TimelineEvent(
        event_id=event_id,
        category=TimelineEventCategory.METRIC_ANOMALY,
        source=TimelineEventSource.TELEMETRY,
        timestamp=base + datetime.timedelta(seconds=ts_offset),
        service_name="api",
        title=f"event {event_id}",
        trace_id=trace_id,
        metadata={"metric": "cpu.usage", "value": "1.0"},
    )


class TestPipelineValidation:
    async def test_raises_on_empty_strategies(self) -> None:
        with pytest.raises(ValueError, match="At least one strategy"):
            CorrelationPipeline([])


class TestPipelineMerging:
    async def test_merges_multiple_strategy_matches(self) -> None:
        ctx = CorrelationContext(
            events=[
                _event("a", ts_offset=0, trace_id="trace-1"),
                _event("b", ts_offset=5, trace_id="trace-1"),
            ]
        )
        pipeline = CorrelationPipeline([TimeWindowStrategy(60), TraceIdStrategy()])
        result = await pipeline.run(ctx)
        assert len(result.groups) == 1
        assert "a" in result.groups[0].event_ids
        assert "b" in result.groups[0].event_ids
        assert result.groups[0].composite_score > 0.9

    async def test_two_groups_separate(self) -> None:
        ctx = CorrelationContext(
            events=[
                _event("a", ts_offset=0, trace_id="trace-1"),
                _event("b", ts_offset=1, trace_id="trace-1"),
                _event("c", ts_offset=300, trace_id="trace-2"),
                _event("d", ts_offset=301, trace_id="trace-2"),
            ]
        )
        pipeline = CorrelationPipeline([TimeWindowStrategy(60), TraceIdStrategy()])
        result = await pipeline.run(ctx)
        assert len(result.groups) == 2
        assert sum(g.composite_score for g in result.groups) > 1.8


class TestScoring:
    async def test_composite_score_combines_strategies(self) -> None:
        ctx = CorrelationContext(
            events=[
                _event("a", ts_offset=0, trace_id="trace-1"),
                _event("b", ts_offset=5, trace_id="trace-1"),
            ]
        )
        pipeline = CorrelationPipeline([TimeWindowStrategy(60)])
        time_only = await pipeline.run(ctx)
        pipeline2 = CorrelationPipeline([TimeWindowStrategy(60), TraceIdStrategy()])
        both = await pipeline2.run(ctx)
        assert both.groups[0].composite_score > time_only.groups[0].composite_score


class TestNoiseFiltering:
    async def test_low_score_group_filtered(self) -> None:
        ctx = CorrelationContext(
            events=[
                _event("a", ts_offset=0),
                _event("b", ts_offset=55),
            ],
            min_score=0.5,
        )
        pipeline = CorrelationPipeline([TimeWindowStrategy(60)])
        result = await pipeline.run(ctx)
        assert len(result.groups) == 0

    async def test_ungrouped_events_tracked(self) -> None:
        ctx = CorrelationContext(
            events=[
                _event("a", ts_offset=0),
                _event("b", ts_offset=300),
            ],
            min_score=0.5,
        )
        pipeline = CorrelationPipeline([TimeWindowStrategy(60)])
        result = await pipeline.run(ctx)
        assert len(result.ungrouped_event_ids) == 2
