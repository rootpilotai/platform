from abc import ABC, abstractmethod

from shared.domain.correlation.enums import CorrelationSignal, CorrelationStrategyType
from shared.domain.correlation.models import CorrelationContext, CorrelationMatch


class CorrelationStrategy(ABC):
    strategy_type: CorrelationStrategyType
    signal: CorrelationSignal
    weight: float

    @abstractmethod
    async def correlate(self, context: CorrelationContext) -> list[CorrelationMatch]: ...
