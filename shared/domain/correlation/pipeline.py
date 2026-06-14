import time

from shared.domain.correlation.models import CorrelationContext, CorrelationGroup, CorrelationMatch, CorrelationResult
from shared.domain.correlation.scoring.pipeline import ScoringPipeline
from shared.domain.correlation.strategies.base import CorrelationStrategy


class CorrelationPipeline:
    def __init__(self, strategies: list[CorrelationStrategy]) -> None:
        if not strategies:
            raise ValueError("At least one strategy is required")
        self._strategies = strategies
        self._scoring_pipeline = ScoringPipeline(strategies)

    async def run(self, context: CorrelationContext) -> CorrelationResult:
        start = time.perf_counter()
        all_matches: list[CorrelationMatch] = []
        strategy_counts: dict[str, int] = {}

        for strategy in self._strategies:
            matches = await strategy.correlate(context)
            all_matches.extend(matches)
            strategy_counts[strategy.strategy_type.value] = len(matches)

        groups = self._scoring_pipeline.process(all_matches, context)
        ungrouped = self._find_ungrouped(context.events, groups)

        duration = (time.perf_counter() - start) * 1000
        grouped_ids = {eid for g in groups for eid in g.event_ids}

        return CorrelationResult(
            groups=sorted(groups, key=lambda g: g.composite_score, reverse=True),
            ungrouped_event_ids=ungrouped,
            total_events=len(context.events),
            grouped_count=len(grouped_ids),
            ungrouped_count=len(ungrouped),
            strategy_counts=strategy_counts,
            duration_ms=round(duration, 2),
        )

    def _find_ungrouped(self, events: list, groups: list[CorrelationGroup]) -> list[str]:
        grouped: set[str] = set()
        for g in groups:
            grouped.update(g.event_ids)
        return [ev.event_id for ev in events if ev.event_id not in grouped]
