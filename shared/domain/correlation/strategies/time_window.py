from datetime import timedelta

from shared.domain.correlation.enums import CorrelationSignal, CorrelationStrategyType
from shared.domain.correlation.models import CorrelationContext, CorrelationMatch
from shared.domain.correlation.strategies.base import CorrelationStrategy


class TimeWindowStrategy(CorrelationStrategy):
    strategy_type = CorrelationStrategyType.TIME_WINDOW
    signal = CorrelationSignal.TIME_PROXIMITY
    weight = 0.3

    def __init__(self, window_seconds: int = 60) -> None:
        self._window = timedelta(seconds=window_seconds)

    async def correlate(self, context: CorrelationContext) -> list[CorrelationMatch]:
        matches: list[CorrelationMatch] = []
        events = context.events
        for i in range(len(events)):
            for j in range(i + 1, len(events)):
                a, b = events[i], events[j]
                diff = abs((a.timestamp - b.timestamp).total_seconds())
                if diff <= self._window.total_seconds():
                    score = max(0.0, 1.0 - (diff / self._window.total_seconds()))
                    matches.append(
                        CorrelationMatch(
                            event_id_a=a.event_id,
                            event_id_b=b.event_id,
                            strategy_type=self.strategy_type,
                            signal=self.signal,
                            score=round(score, 4),
                            metadata={
                                "time_diff_seconds": str(int(diff)),
                                "window_seconds": str(int(self._window.total_seconds())),
                            },
                        )
                    )
        return matches
