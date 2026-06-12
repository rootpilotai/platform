from shared.domain.correlation.enums import CorrelationSignal, CorrelationStrategyType
from shared.domain.correlation.models import CorrelationContext, CorrelationMatch
from shared.domain.correlation.strategies.base import CorrelationStrategy


class RequestIdStrategy(CorrelationStrategy):
    strategy_type = CorrelationStrategyType.REQUEST_ID
    signal = CorrelationSignal.REQUEST_MATCH
    weight = 0.8

    async def correlate(self, context: CorrelationContext) -> list[CorrelationMatch]:
        matches: list[CorrelationMatch] = []
        by_request: dict[str, list[str]] = {}
        for ev in context.events:
            if ev.request_id:
                by_request.setdefault(ev.request_id, []).append(ev.event_id)
        for request_id, ids in by_request.items():
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
                            metadata={"request_id": request_id},
                        )
                    )
        return matches
