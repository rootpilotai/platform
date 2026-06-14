"""Tests for the WeightedProbabilisticScorer."""

from shared.domain.correlation.enums import CorrelationSignal, CorrelationStrategyType
from shared.domain.correlation.models import CorrelationMatch
from shared.domain.correlation.scoring.strategies import WeightedProbabilisticScorer
from shared.domain.correlation.strategies.base import CorrelationStrategy


class _FakeStrategy(CorrelationStrategy):
    strategy_type: CorrelationStrategyType
    signal: CorrelationSignal
    weight: float

    def __init__(self, strategy_type: CorrelationStrategyType, weight: float, signal: CorrelationSignal) -> None:
        self.strategy_type = strategy_type
        self.weight = weight
        self.signal = signal

    async def correlate(self, context):  # noqa: ARG002
        return []


class TestWeightedProbabilisticScorer:
    def setup_method(self) -> None:
        self.scorer = WeightedProbabilisticScorer()

    def test_empty_matches_returns_zero_composite(self) -> None:
        result = self.scorer.score_group(set(), [], {})
        assert result.composite_score == 0.0
        assert result.contributions == []

    def test_single_match_high_weight(self) -> None:
        trace_strat = _FakeStrategy(CorrelationStrategyType.TRACE_ID, 0.9, CorrelationSignal.TRACE_MATCH)
        matches = [
            CorrelationMatch(
                event_id_a="e1",
                event_id_b="e2",
                strategy_type=CorrelationStrategyType.TRACE_ID,
                signal=CorrelationSignal.TRACE_MATCH,
                score=1.0,
            ),
        ]
        strategy_map = {CorrelationStrategyType.TRACE_ID: trace_strat}
        result = self.scorer.score_group({"e1", "e2"}, matches, strategy_map)

        assert result.composite_score == 0.9
        assert len(result.contributions) == 1
        contrib = result.contributions[0]
        assert contrib.strategy_name == "trace_id"
        assert contrib.raw_score == 1.0
        assert contrib.weighted_score == 0.9
        assert contrib.weight == 0.9

    def test_low_weight_attenuates_score(self) -> None:
        time_strat = _FakeStrategy(CorrelationStrategyType.TIME_WINDOW, 0.3, CorrelationSignal.TIME_PROXIMITY)
        matches = [
            CorrelationMatch(
                event_id_a="e1",
                event_id_b="e2",
                strategy_type=CorrelationStrategyType.TIME_WINDOW,
                signal=CorrelationSignal.TIME_PROXIMITY,
                score=1.0,
            ),
        ]
        strategy_map = {CorrelationStrategyType.TIME_WINDOW: time_strat}
        result = self.scorer.score_group({"e1", "e2"}, matches, strategy_map)

        assert result.composite_score == 0.3
        assert result.contributions[0].weighted_score == 0.3

    def test_multiple_strategies_combine_probabilistically(self) -> None:
        trace_strat = _FakeStrategy(CorrelationStrategyType.TRACE_ID, 0.9, CorrelationSignal.TRACE_MATCH)
        time_strat = _FakeStrategy(CorrelationStrategyType.TIME_WINDOW, 0.3, CorrelationSignal.TIME_PROXIMITY)
        matches = [
            CorrelationMatch(
                event_id_a="e1",
                event_id_b="e2",
                strategy_type=CorrelationStrategyType.TRACE_ID,
                signal=CorrelationSignal.TRACE_MATCH,
                score=1.0,
            ),
            CorrelationMatch(
                event_id_a="e1",
                event_id_b="e2",
                strategy_type=CorrelationStrategyType.TIME_WINDOW,
                signal=CorrelationSignal.TIME_PROXIMITY,
                score=0.9,
            ),
        ]
        strategy_map = {
            CorrelationStrategyType.TRACE_ID: trace_strat,
            CorrelationStrategyType.TIME_WINDOW: time_strat,
        }
        result = self.scorer.score_group({"e1", "e2"}, matches, strategy_map)

        # Weighted: trace = 0.9, time = 1 - (1 - 0.9*0.3) = 0.27
        # Composite: 1 - (1-0.9)*(1-0.27) = 1 - 0.1*0.73 = 1 - 0.073 = 0.927
        assert result.composite_score == 0.927

    def test_missing_strategy_falls_back_to_default_weight(self) -> None:
        matches = [
            CorrelationMatch(
                event_id_a="e1",
                event_id_b="e2",
                strategy_type=CorrelationStrategyType.DEPENDENCY,
                signal=CorrelationSignal.DEPENDENCY_CHAIN,
                score=1.0,
            ),
        ]
        # Empty strategy map -> fallback to 0.5
        result = self.scorer.score_group({"e1", "e2"}, matches, {})
        assert result.composite_score == 0.5
        assert result.contributions[0].weight == 0.5

    def test_strategy_scores_uses_max_per_strategy(self) -> None:
        trace_strat = _FakeStrategy(CorrelationStrategyType.TRACE_ID, 0.9, CorrelationSignal.TRACE_MATCH)
        matches = [
            CorrelationMatch(
                event_id_a="e1",
                event_id_b="e2",
                strategy_type=CorrelationStrategyType.TRACE_ID,
                signal=CorrelationSignal.TRACE_MATCH,
                score=0.5,
            ),
            CorrelationMatch(
                event_id_a="e1",
                event_id_b="e3",
                strategy_type=CorrelationStrategyType.TRACE_ID,
                signal=CorrelationSignal.TRACE_MATCH,
                score=1.0,
            ),
        ]
        strategy_map = {CorrelationStrategyType.TRACE_ID: trace_strat}
        result = self.scorer.score_group({"e1", "e2", "e3"}, matches, strategy_map)

        assert result.strategy_scores["trace_id"] == 0.9
        assert result.contributions[0].raw_score == 1.0

    def test_strategies_used_is_sorted(self) -> None:
        time_strat = _FakeStrategy(CorrelationStrategyType.TIME_WINDOW, 0.3, CorrelationSignal.TIME_PROXIMITY)
        trace_strat = _FakeStrategy(CorrelationStrategyType.TRACE_ID, 0.9, CorrelationSignal.TRACE_MATCH)
        matches = [
            CorrelationMatch(
                event_id_a="e1",
                event_id_b="e2",
                strategy_type=CorrelationStrategyType.TIME_WINDOW,
                signal=CorrelationSignal.TIME_PROXIMITY,
                score=0.5,
            ),
            CorrelationMatch(
                event_id_a="e1",
                event_id_b="e2",
                strategy_type=CorrelationStrategyType.TRACE_ID,
                signal=CorrelationSignal.TRACE_MATCH,
                score=1.0,
            ),
        ]
        strategy_map = {
            CorrelationStrategyType.TIME_WINDOW: time_strat,
            CorrelationStrategyType.TRACE_ID: trace_strat,
        }
        result = self.scorer.score_group({"e1", "e2"}, matches, strategy_map)
        assert result.strategies_used == sorted(
            [CorrelationStrategyType.TIME_WINDOW, CorrelationStrategyType.TRACE_ID],
            key=lambda s: s.value,
        )
