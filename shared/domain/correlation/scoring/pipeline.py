"""ScoringPipeline — orchestrates group detection, weighted scoring, and confidence computation."""

from collections import defaultdict, deque
from uuid import uuid4

from shared.domain.correlation.enums import CorrelationStrategyType
from shared.domain.correlation.models import CorrelationContext, CorrelationGroup, CorrelationMatch
from shared.domain.correlation.scoring.confidence import ConfidenceScorer
from shared.domain.correlation.scoring.strategies import ScoringStrategy, WeightedProbabilisticScorer
from shared.domain.correlation.strategies.base import CorrelationStrategy


class ScoringPipeline:
    """Orchestrates the full scoring flow: group detection, weighted scoring, confidence computation.

    Accepts a list of correlation strategies (for weight resolution) and
    delegates the per-group score computation to a pluggable *ScoringStrategy*.
    """

    def __init__(
        self,
        strategies: list[CorrelationStrategy],
        scorer: ScoringStrategy | None = None,
        confidence_scorer: ConfidenceScorer | None = None,
    ) -> None:
        self._strategy_map: dict[CorrelationStrategyType, CorrelationStrategy] = {
            s.strategy_type: s for s in strategies
        }
        self._scorer = scorer or WeightedProbabilisticScorer()
        self._confidence_scorer = confidence_scorer or ConfidenceScorer()

    def process(
        self,
        matches: list[CorrelationMatch],
        context: CorrelationContext,
    ) -> list[CorrelationGroup]:
        """Group matches by connected components and score each group."""
        adj: dict[str, set[str]] = defaultdict(set)
        event_map = {ev.event_id: ev for ev in context.events}

        for m in matches:
            adj[m.event_id_a].add(m.event_id_b)
            adj[m.event_id_b].add(m.event_id_a)

        visited: set[str] = set()
        groups: list[CorrelationGroup] = []

        for event_id in context.events:
            eid = event_id.event_id
            if eid in visited:
                continue
            group = self._bfs_group(eid, adj, visited)
            if len(group) < 2:
                continue

            group_matches = [m for m in matches if m.event_id_a in group or m.event_id_b in group]

            scoring_result = self._scorer.score_group(group, group_matches, self._strategy_map)

            timestamps = [event_map[eid].timestamp for eid in group if eid in event_map]
            confidence = self._confidence_scorer.compute(
                result=scoring_result,
                total_events_in_group=len(group),
                event_timestamps=timestamps,
            )

            groups.append(
                CorrelationGroup(
                    group_id=uuid4().hex,
                    event_ids=sorted(group),
                    strategies_used=scoring_result.strategies_used,
                    strategy_scores=scoring_result.strategy_scores,
                    composite_score=scoring_result.composite_score,
                    confidence=confidence,
                    contributions=scoring_result.contributions,
                    window_start=min(timestamps) if timestamps else None,
                    window_end=max(timestamps) if timestamps else None,
                )
            )

        return [g for g in groups if g.composite_score >= context.min_score]

    @staticmethod
    def _bfs_group(start: str, adj: dict[str, set[str]], visited: set[str]) -> set[str]:
        group: set[str] = set()
        queue: deque[str] = deque([start])
        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)
            group.add(current)
            for neighbor in adj.get(current, set()):
                if neighbor not in visited:
                    queue.append(neighbor)
        return group
