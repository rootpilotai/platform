from shared.domain.correlation.enums import CorrelationSignal, CorrelationStrategyType
from shared.domain.correlation.grouping import TraceGroupingService
from shared.domain.correlation.grouping.models import TraceTree
from shared.domain.correlation.models import CorrelationContext, CorrelationMatch
from shared.domain.correlation.strategies.base import CorrelationStrategy


class SpanRelationStrategy(CorrelationStrategy):
    """Scores event pairs based on their span relationship within a trace.

    Hierarchy (highest → lowest score):
    - Parent-child spans (direct call relationship): 1.0
    - Sibling spans (same parent): 0.8
    - Same trace, no direct span relation: 0.5
    """

    strategy_type = CorrelationStrategyType.SPAN_RELATION
    weight = 0.85

    PARENT_CHILD_SCORE = 1.0
    SIBLING_SCORE = 0.8
    SAME_TRACE_SCORE = 0.5

    def __init__(self, grouping_service: TraceGroupingService | None = None) -> None:
        self._grouping = grouping_service or TraceGroupingService()

    async def correlate(self, context: CorrelationContext) -> list[CorrelationMatch]:
        matches: list[CorrelationMatch] = []
        trace_groups = self._grouping.build_trace_groups(context.events)

        for group in trace_groups:
            tree = group.tree
            if tree is None:
                continue

            event_ids = group.event_ids
            if len(event_ids) < 2:
                continue

            for i in range(len(event_ids)):
                for j in range(i + 1, len(event_ids)):
                    eid_a = event_ids[i]
                    eid_b = event_ids[j]
                    score, signal = self._score_pair(eid_a, eid_b, tree)
                    matches.append(
                        CorrelationMatch(
                            event_id_a=eid_a,
                            event_id_b=eid_b,
                            strategy_type=self.strategy_type,
                            signal=signal,
                            score=score,
                            metadata={"trace_id": group.trace_id},
                        )
                    )

        return matches

    def _score_pair(self, eid_a: str, eid_b: str, tree: TraceTree) -> tuple[float, CorrelationSignal]:
        spans_a = [s for s in tree.all_spans if eid_a in s.event_ids]
        spans_b = [s for s in tree.all_spans if eid_b in s.event_ids]

        if not spans_a or not spans_b:
            return self.SAME_TRACE_SCORE, CorrelationSignal.TRACE_MATCH

        for sa in spans_a:
            for sb in spans_b:
                if sa.parent_span_id == sb.span_id:
                    return self.PARENT_CHILD_SCORE, CorrelationSignal.SPAN_PARENT_CHILD
                if sb.parent_span_id == sa.span_id:
                    return self.PARENT_CHILD_SCORE, CorrelationSignal.SPAN_PARENT_CHILD

        for sa in spans_a:
            for sb in spans_b:
                if (
                    sa.parent_span_id is not None
                    and sb.parent_span_id is not None
                    and sa.parent_span_id == sb.parent_span_id
                ):
                    return self.SIBLING_SCORE, CorrelationSignal.SPAN_SIBLING

        return self.SAME_TRACE_SCORE, CorrelationSignal.TRACE_MATCH
