"""Scoring strategies for weighted probabilistic correlation scoring."""

from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Mapping

from shared.domain.correlation.enums import CorrelationStrategyType
from shared.domain.correlation.models import CorrelationMatch, ScoreContribution
from shared.domain.correlation.scoring.models import ScoringResult
from shared.domain.correlation.strategies.base import CorrelationStrategy


def _probabilistic_union(scores: list[float]) -> float:
    """Combine scores using probabilistic union: 1 - ∏(1 - sᵢ)."""
    if not scores:
        return 0.0
    result = 0.0
    for s in scores:
        result = 1.0 - (1.0 - result) * (1.0 - s)
    return round(result, 4)


class ScoringStrategy(ABC):
    """Pluggable strategy for computing composite scores from correlation matches."""

    @abstractmethod
    def score_group(
        self,
        _group_event_ids: set[str],
        matches: list[CorrelationMatch],
        strategy_map: Mapping[CorrelationStrategyType, CorrelationStrategy],
    ) -> ScoringResult: ...


class WeightedProbabilisticScorer(ScoringStrategy):
    """Default scorer using strategy weights to attenuate match scores before probabilistic combination.

    Each match score is attenuated by its strategy's weight:
        weighted_score = 1 - (1 - raw_score * weight)

    The composite score is the probabilistic union of all weighted scores.
    """

    def score_group(
        self,
        _group_event_ids: set[str],
        matches: list[CorrelationMatch],
        strategy_map: Mapping[CorrelationStrategyType, CorrelationStrategy],
    ) -> ScoringResult:
        per_strategy_matches: dict[str, list[CorrelationMatch]] = defaultdict(list)
        for m in matches:
            per_strategy_matches[m.strategy_type.value].append(m)

        weighted_scores: list[float] = []
        contributions: list[ScoreContribution] = []
        strategy_scores: dict[str, float] = {}
        strategies_used: set[CorrelationStrategyType] = set()

        for strategy_key, strategy_matches in per_strategy_matches.items():
            strategy_type = strategy_matches[0].strategy_type
            strategies_used.add(strategy_type)
            signal = strategy_matches[0].signal

            weight = _resolve_weight(strategy_type, strategy_map)
            raw_max = max(m.score for m in strategy_matches)

            # Attenuate by weight
            weighted_strategy_score = 1.0 - (1.0 - raw_max * weight)
            weighted_strategy_score = max(0.0, round(weighted_strategy_score, 4))
            strategy_scores[strategy_key] = weighted_strategy_score

            event_ids: list[str] = []
            for m in strategy_matches:
                if m.event_id_a not in event_ids:
                    event_ids.append(m.event_id_a)
                if m.event_id_b not in event_ids:
                    event_ids.append(m.event_id_b)

            contributions.append(
                ScoreContribution(
                    strategy_name=strategy_key,
                    signal=signal,
                    raw_score=raw_max,
                    weighted_score=weighted_strategy_score,
                    weight=weight,
                    match_count=len(strategy_matches),
                    event_ids=event_ids,
                )
            )

            for m in strategy_matches:
                ws = 1.0 - (1.0 - m.score * weight)
                weighted_scores.append(max(0.0, round(ws, 4)))

        composite = _probabilistic_union(weighted_scores)

        return ScoringResult(
            composite_score=composite,
            confidence=0.0,
            contributions=contributions,
            strategy_scores=strategy_scores,
            strategies_used=sorted(strategies_used, key=lambda s: s.value),
        )


def _resolve_weight(
    strategy_type: CorrelationStrategyType,
    strategy_map: Mapping[CorrelationStrategyType, CorrelationStrategy],
) -> float:
    strategy = strategy_map.get(strategy_type)
    if strategy is not None:
        return strategy.weight
    return 0.5
