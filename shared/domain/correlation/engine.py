from shared.domain.correlation.models import CorrelationContext, CorrelationResult
from shared.domain.correlation.pipeline import CorrelationPipeline
from shared.domain.correlation.strategies import (
    CorrelationStrategy,
    DependencyStrategy,
    ErrorSignatureStrategy,
    RequestIdStrategy,
    TimeWindowStrategy,
    TraceIdStrategy,
)
from shared.domain.graph.store import GraphStore
from shared.domain.timeline.models import TimelineEvent


class CorrelationEngine:
    def __init__(
        self,
        store: GraphStore | None = None,
        strategies: list[CorrelationStrategy] | None = None,
        default_window_seconds: int = 60,
        default_min_score: float = 0.2,
    ) -> None:
        if strategies is not None:
            self._pipeline = CorrelationPipeline(strategies)
        else:
            built: list[CorrelationStrategy] = [
                TimeWindowStrategy(window_seconds=default_window_seconds),
                TraceIdStrategy(),
                RequestIdStrategy(),
                ErrorSignatureStrategy(),
            ]
            if store is not None:
                built.append(DependencyStrategy(store=store))
            self._pipeline = CorrelationPipeline(built)
        self._default_min_score = default_min_score

    async def correlate(
        self,
        events: list[TimelineEvent],
        min_score: float | None = None,
    ) -> CorrelationResult:
        context = CorrelationContext(
            events=events,
            min_score=min_score if min_score is not None else self._default_min_score,
        )
        return await self._pipeline.run(context)
