from shared.domain.correlation.enums import CorrelationSignal, CorrelationStrategyType
from shared.domain.correlation.models import CorrelationContext, CorrelationMatch
from shared.domain.correlation.strategies.base import CorrelationStrategy
from shared.domain.graph.store import GraphStore


class DependencyStrategy(CorrelationStrategy):
    strategy_type = CorrelationStrategyType.DEPENDENCY
    signal = CorrelationSignal.DEPENDENCY_CHAIN
    weight = 0.5

    def __init__(self, store: GraphStore) -> None:
        self._store = store

    async def correlate(self, context: CorrelationContext) -> list[CorrelationMatch]:
        matches: list[CorrelationMatch] = []
        by_service: dict[str, list[str]] = {}
        for ev in context.events:
            by_service.setdefault(ev.service_name, []).append(ev.event_id)

        services = list(by_service.keys())
        for i in range(len(services)):
            for j in range(i + 1, len(services)):
                svc_a, svc_b = services[i], services[j]
                score = await self._service_dependency_score(svc_a, svc_b)
                if score > 0:
                    for id_a in by_service[svc_a]:
                        for id_b in by_service[svc_b]:
                            matches.append(
                                CorrelationMatch(
                                    event_id_a=id_a,
                                    event_id_b=id_b,
                                    strategy_type=self.strategy_type,
                                    signal=self.signal,
                                    score=score,
                                    metadata={
                                        "service_a": svc_a,
                                        "service_b": svc_b,
                                        "dependency_score": str(score),
                                    },
                                )
                            )
        return matches

    async def _service_dependency_score(self, svc_a: str, svc_b: str) -> float:
        outgoing = await self._store.get_outgoing(svc_a)
        for edge in outgoing:
            if edge.target == svc_b:
                return edge.weight
        outgoing_b = await self._store.get_outgoing(svc_b)
        for edge in outgoing_b:
            if edge.target == svc_a:
                return edge.weight
        return 0.0
