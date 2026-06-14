"""Integration tests for ScoringPipeline — group detection, scoring, confidence."""

from datetime import UTC, datetime

from shared.domain.correlation.enums import CorrelationSignal, CorrelationStrategyType
from shared.domain.correlation.models import CorrelationContext, CorrelationMatch
from shared.domain.correlation.scoring.pipeline import ScoringPipeline
from shared.domain.correlation.strategies import TimeWindowStrategy, TraceIdStrategy
from shared.domain.timeline.enums import TimelineEventCategory, TimelineEventSource
from shared.domain.timeline.models import TimelineEvent


def _event(event_id: str, ts_offset: int = 0, trace_id: str | None = None) -> TimelineEvent:
    from datetime import timedelta

    base = datetime(2026, 6, 14, 10, 0, 0, tzinfo=UTC)
    return TimelineEvent(
        event_id=event_id,
        category=TimelineEventCategory.METRIC_ANOMALY,
        source=TimelineEventSource.TELEMETRY,
        timestamp=base + timedelta(seconds=ts_offset),
        service_name="api",
        title=f"event {event_id}",
        trace_id=trace_id,
    )


class TestScoringPipeline:
    def test_empty_matches_returns_no_groups(self) -> None:
        pipeline = ScoringPipeline(strategies=[TimeWindowStrategy(60)])
        ctx = CorrelationContext(events=[_event("a"), _event("b")])
        groups = pipeline.process([], ctx)
        assert groups == []

    def test_singleton_events_are_skipped(self) -> None:
        pipeline = ScoringPipeline(strategies=[TraceIdStrategy()])
        ctx = CorrelationContext(events=[_event("a", trace_id="t1"), _event("b", trace_id="t2")])
        # No shared trace -> no matches
        groups = pipeline.process([], ctx)
        assert groups == []

    def test_weighted_composite_from_matches(self) -> None:
        trace_strat = TraceIdStrategy()
        pipeline = ScoringPipeline(strategies=[trace_strat])
        ctx = CorrelationContext(events=[_event("a", trace_id="t1"), _event("b", trace_id="t1")])
        matches = [
            CorrelationMatch(
                event_id_a="a",
                event_id_b="b",
                strategy_type=CorrelationStrategyType.TRACE_ID,
                signal=CorrelationSignal.TRACE_MATCH,
                score=1.0,
            ),
        ]
        groups = pipeline.process(matches, ctx)
        assert len(groups) == 1
        g = groups[0]
        assert g.composite_score == 0.9
        assert g.confidence > 0.0
        assert len(g.contributions) == 1
        assert g.contributions[0].strategy_name == "trace_id"

    def test_min_score_filters_low_scoring_groups(self) -> None:
        pipeline = ScoringPipeline(strategies=[TimeWindowStrategy(60)])
        ctx = CorrelationContext(
            events=[_event("a", ts_offset=0), _event("b", ts_offset=55)],
            min_score=0.5,
        )
        matches = [
            CorrelationMatch(
                event_id_a="a",
                event_id_b="b",
                strategy_type=CorrelationStrategyType.TIME_WINDOW,
                signal=CorrelationSignal.TIME_PROXIMITY,
                score=1.0 - 55 / 60,
            ),
        ]
        groups = pipeline.process(matches, ctx)
        assert len(groups) == 0

    def test_group_includes_all_event_ids(self) -> None:
        pipeline = ScoringPipeline(strategies=[TraceIdStrategy()])
        ctx = CorrelationContext(
            events=[
                _event("a", trace_id="t1"),
                _event("b", trace_id="t1"),
                _event("c", trace_id="t1"),
            ]
        )
        matches = [
            CorrelationMatch(
                event_id_a="a",
                event_id_b="b",
                strategy_type=CorrelationStrategyType.TRACE_ID,
                signal=CorrelationSignal.TRACE_MATCH,
                score=1.0,
            ),
            CorrelationMatch(
                event_id_a="a",
                event_id_b="c",
                strategy_type=CorrelationStrategyType.TRACE_ID,
                signal=CorrelationSignal.TRACE_MATCH,
                score=1.0,
            ),
        ]
        groups = pipeline.process(matches, ctx)
        assert len(groups) == 1
        assert sorted(groups[0].event_ids) == ["a", "b", "c"]

    def test_custom_scorer_can_be_injected(self) -> None:
        from shared.domain.correlation.scoring.strategies import ScoringStrategy, WeightedProbabilisticScorer

        class FixedScorer(ScoringStrategy):
            def score_group(self, group_event_ids, matches, strategy_map):
                return WeightedProbabilisticScorer().score_group(group_event_ids, matches, strategy_map)

        pipeline = ScoringPipeline(strategies=[TraceIdStrategy()], scorer=FixedScorer())
        ctx = CorrelationContext(events=[_event("a", trace_id="t1"), _event("b", trace_id="t1")])
        matches = [
            CorrelationMatch(
                event_id_a="a",
                event_id_b="b",
                strategy_type=CorrelationStrategyType.TRACE_ID,
                signal=CorrelationSignal.TRACE_MATCH,
                score=1.0,
            ),
        ]
        groups = pipeline.process(matches, ctx)
        assert len(groups) == 1

    def test_window_start_end_from_timestamps(self) -> None:
        pipeline = ScoringPipeline(strategies=[TraceIdStrategy()])
        ctx = CorrelationContext(
            events=[
                _event("a", ts_offset=10, trace_id="t1"),
                _event("b", ts_offset=20, trace_id="t1"),
            ]
        )
        matches = [
            CorrelationMatch(
                event_id_a="a",
                event_id_b="b",
                strategy_type=CorrelationStrategyType.TRACE_ID,
                signal=CorrelationSignal.TRACE_MATCH,
                score=1.0,
            ),
        ]
        groups = pipeline.process(matches, ctx)
        assert len(groups) == 1
        g = groups[0]
        assert g.window_start is not None
        assert g.window_end is not None
        assert g.window_start < g.window_end
