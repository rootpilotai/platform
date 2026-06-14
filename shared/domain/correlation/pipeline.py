import time
from collections import defaultdict
from uuid import uuid4

from shared.domain.correlation.enums import CorrelationStrategyType
from shared.domain.correlation.models import CorrelationContext, CorrelationGroup, CorrelationMatch, CorrelationResult
from shared.domain.correlation.strategies.base import CorrelationStrategy


def _composite_score(scores: list[float]) -> float:
    if not scores:
        return 0.0
    result = 0.0
    for s in scores:
        result = 1.0 - (1.0 - result) * (1.0 - s)
    return round(result, 4)


class CorrelationPipeline:
    def __init__(self, strategies: list[CorrelationStrategy]) -> None:
        if not strategies:
            raise ValueError("At least one strategy is required")
        self._strategies = strategies

    async def run(self, context: CorrelationContext) -> CorrelationResult:
        start = time.perf_counter()
        all_matches: list[CorrelationMatch] = []
        strategy_counts: dict[str, int] = {}

        for strategy in self._strategies:
            matches = await strategy.correlate(context)
            all_matches.extend(matches)
            strategy_counts[strategy.strategy_type.value] = len(matches)

        groups = self._merge_into_groups(all_matches, context)
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

    def _merge_into_groups(
        self, matches: list[CorrelationMatch], context: CorrelationContext
    ) -> list[CorrelationGroup]:
        adj: dict[str, set[str]] = defaultdict(set)
        event_scores: dict[str, list[float]] = defaultdict(list)
        event_strategies: dict[str, set[CorrelationStrategyType]] = defaultdict(set)
        strategy_scores: dict[str, dict[str, float]] = defaultdict(dict)

        for m in matches:
            adj[m.event_id_a].add(m.event_id_b)
            adj[m.event_id_b].add(m.event_id_a)
            event_scores[m.event_id_a].append(m.score)
            event_scores[m.event_id_b].append(m.score)
            event_strategies[m.event_id_a].add(m.strategy_type)
            event_strategies[m.event_id_b].add(m.strategy_type)
            for eid in (m.event_id_a, m.event_id_b):
                key = m.strategy_type.value
                existing = strategy_scores[eid].get(key, 0.0)
                strategy_scores[eid][key] = max(existing, m.score)

        visited: set[str] = set()
        groups: list[CorrelationGroup] = []
        event_map = {ev.event_id: ev for ev in context.events}

        for event_id in context.events:
            eid = event_id.event_id
            if eid in visited:
                continue
            group = self._bfs_group(eid, adj, visited)
            if len(group) < 2:
                continue
            scores = [s for eid in group for s in event_scores.get(eid, [])]
            strategies = list({st for eid in group for st in event_strategies.get(eid, set())})
            timestamps = [event_map[eid].timestamp for eid in group if eid in event_map]
            combined_scores: dict[str, float] = {}
            for eid in group:
                for strategy_key, sc in strategy_scores.get(eid, {}).items():
                    combined_scores[strategy_key] = max(combined_scores.get(strategy_key, 0.0), sc)
            groups.append(
                CorrelationGroup(
                    group_id=uuid4().hex,
                    event_ids=sorted(group),
                    strategies_used=sorted(strategies, key=lambda s: s.value),
                    strategy_scores=combined_scores,
                    composite_score=_composite_score(scores),
                    window_start=min(timestamps) if timestamps else None,
                    window_end=max(timestamps) if timestamps else None,
                )
            )

        return [g for g in groups if g.composite_score >= context.min_score]

    def _find_ungrouped(self, events: list, groups: list[CorrelationGroup]) -> list[str]:
        grouped: set[str] = set()
        for g in groups:
            grouped.update(g.event_ids)
        return [ev.event_id for ev in events if ev.event_id not in grouped]

    @staticmethod
    def _bfs_group(start: str, adj: dict[str, set[str]], visited: set[str]) -> set[str]:
        from collections import deque

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
