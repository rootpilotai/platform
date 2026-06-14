"""Tests for the ConfidenceScorer."""

from datetime import UTC, datetime, timedelta

from shared.domain.correlation.enums import CorrelationSignal, CorrelationStrategyType
from shared.domain.correlation.scoring.confidence import ConfidenceScorer
from shared.domain.correlation.scoring.models import ScoreContribution, ScoringResult


class TestConfidenceScorer:
    def setup_method(self) -> None:
        self.scorer = ConfidenceScorer()

    def test_perfect_confidence(self) -> None:
        result = ScoringResult(
            composite_score=1.0,
            confidence=0.0,
            contributions=[
                ScoreContribution(
                    strategy_name="trace_id",
                    signal=CorrelationSignal.TRACE_MATCH,
                    raw_score=1.0,
                    weighted_score=1.0,
                    weight=1.0,
                    match_count=1,
                    event_ids=["e1", "e2"],
                ),
                ScoreContribution(
                    strategy_name="time_window",
                    signal=CorrelationSignal.TIME_PROXIMITY,
                    raw_score=1.0,
                    weighted_score=1.0,
                    weight=1.0,
                    match_count=1,
                    event_ids=["e1", "e2"],
                ),
                ScoreContribution(
                    strategy_name="request_id",
                    signal=CorrelationSignal.REQUEST_MATCH,
                    raw_score=1.0,
                    weighted_score=1.0,
                    weight=1.0,
                    match_count=1,
                    event_ids=["e1", "e2"],
                ),
                ScoreContribution(
                    strategy_name="error_signature",
                    signal=CorrelationSignal.ERROR_PATTERN,
                    raw_score=1.0,
                    weighted_score=1.0,
                    weight=1.0,
                    match_count=1,
                    event_ids=["e1", "e2"],
                ),
            ],
            strategy_scores={"trace_id": 1.0},
            strategies_used=[
                CorrelationStrategyType.TRACE_ID,
                CorrelationStrategyType.TIME_WINDOW,
                CorrelationStrategyType.REQUEST_ID,
                CorrelationStrategyType.ERROR_SIGNATURE,
            ],
        )
        ts = datetime.now(UTC)
        confidence = self.scorer.compute(result, total_events_in_group=2, event_timestamps=[ts])
        # composite=1.0 * 0.4 = 0.4, diversity=4/4=1.0 * 0.3 = 0.3, coverage=2/2=1.0 * 0.2 = 0.2, recency=1.0 * 0.1 = 0.1
        # total = 0.4 + 0.3 + 0.2 + 0.1 = 1.0
        assert confidence == 1.0

    def test_single_strategy_lowers_confidence(self) -> None:
        result = ScoringResult(
            composite_score=0.5,
            confidence=0.0,
            contributions=[
                ScoreContribution(
                    strategy_name="trace_id",
                    signal=CorrelationSignal.TRACE_MATCH,
                    raw_score=1.0,
                    weighted_score=0.5,
                    weight=0.5,
                    match_count=1,
                    event_ids=["e1", "e2"],
                ),
            ],
            strategy_scores={"trace_id": 0.5},
            strategies_used=[CorrelationStrategyType.TRACE_ID],
        )
        confidence = self.scorer.compute(result, total_events_in_group=2, event_timestamps=None)
        # composite=0.5 * 0.4 = 0.2, diversity=1/4=0.25 * 0.3 = 0.075, coverage=2/2=1.0 * 0.2 = 0.2, recency=1.0 * 0.1 = 0.1
        # total = 0.2 + 0.075 + 0.2 + 0.1 = 0.575
        assert confidence == 0.575

    def test_low_coverage_lowers_confidence(self) -> None:
        result = ScoringResult(
            composite_score=0.5,
            confidence=0.0,
            contributions=[
                ScoreContribution(
                    strategy_name="trace_id",
                    signal=CorrelationSignal.TRACE_MATCH,
                    raw_score=1.0,
                    weighted_score=0.5,
                    weight=0.5,
                    match_count=1,
                    event_ids=["e1"],
                ),
            ],
            strategy_scores={"trace_id": 0.5},
            strategies_used=[CorrelationStrategyType.TRACE_ID],
        )
        confidence = self.scorer.compute(result, total_events_in_group=10, event_timestamps=None)
        # coverage = 1/10 = 0.1
        # composite=0.5 * 0.4 = 0.2, diversity=0.25*0.3=0.075, coverage=0.1*0.2=0.02, recency=1.0*0.1=0.1
        # total = 0.395
        assert confidence == 0.395

    def test_old_events_reduce_recency(self) -> None:
        result = ScoringResult(
            composite_score=0.5,
            confidence=0.0,
            contributions=[
                ScoreContribution(
                    strategy_name="trace_id",
                    signal=CorrelationSignal.TRACE_MATCH,
                    raw_score=1.0,
                    weighted_score=0.5,
                    weight=0.5,
                    match_count=1,
                    event_ids=["e1", "e2"],
                ),
            ],
            strategy_scores={"trace_id": 0.5},
            strategies_used=[CorrelationStrategyType.TRACE_ID],
        )
        old_ts = datetime.now(UTC) - timedelta(hours=12)
        confidence = self.scorer.compute(result, total_events_in_group=2, event_timestamps=[old_ts])
        # recency: 12h = 43200s -> 1.0 - (43200-3600)/(86400-3600) = 1.0 - 39600/82800 = 1.0 - 0.478 = 0.522
        assert confidence < 0.6
        assert confidence > 0.4

    def test_empty_strategies_returns_zero_diversity(self) -> None:
        result = ScoringResult(
            composite_score=0.5,
            confidence=0.0,
            contributions=[],
            strategy_scores={},
            strategies_used=[],
        )
        confidence = self.scorer.compute(result, total_events_in_group=2, event_timestamps=None)
        # composite=0.5*0.4=0.2, diversity=0*0.3=0, coverage=0*0.2=0, recency=1*0.1=0.1 = 0.3
        assert confidence == 0.3

    def test_empty_events_returns_full_recency(self) -> None:
        assert ConfidenceScorer._recency_factor(None) == 1.0
        assert ConfidenceScorer._recency_factor([]) == 1.0
