from shared.domain.correlation.enums import CorrelationSignal, CorrelationStrategyType
from shared.domain.correlation.models import CorrelationContext, CorrelationMatch
from shared.domain.correlation.strategies.base import CorrelationStrategy


class TraceIdStrategy(CorrelationStrategy):
    strategy_type = CorrelationStrategyType.TRACE_ID
    signal = CorrelationSignal.TRACE_MATCH
    weight = 0.9

    async def correlate(self, context: CorrelationContext) -> list[CorrelationMatch]:
        matches: list[CorrelationMatch] = []
        by_trace: dict[str, list[str]] = {}
        for ev in context.events:
            if ev.trace_id:
                by_trace.setdefault(ev.trace_id, []).append(ev.event_id)
        for trace_id, ids in by_trace.items():
            if len(ids) < 2:
                continue
            for i in range(len(ids)):
                for j in range(i + 1, len(ids)):
                    matches.append(
                        CorrelationMatch(
                            event_id_a=ids[i],
                            event_id_b=ids[j],
                            strategy_type=self.strategy_type,
                            signal=self.signal,
                            score=1.0,
                            metadata={"trace_id": trace_id},
                        )
                    )
        return matches
