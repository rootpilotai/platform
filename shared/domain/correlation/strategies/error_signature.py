import re

from shared.domain.correlation.enums import CorrelationSignal, CorrelationStrategyType
from shared.domain.correlation.models import CorrelationContext, CorrelationMatch
from shared.domain.correlation.strategies.base import CorrelationStrategy


class ErrorSignatureStrategy(CorrelationStrategy):
    strategy_type = CorrelationStrategyType.ERROR_SIGNATURE
    signal = CorrelationSignal.ERROR_PATTERN
    weight = 0.6

    _ERROR_PATTERN = re.compile(r"^(error|failure|exception|fault|timeout)", re.IGNORECASE)

    async def correlate(self, context: CorrelationContext) -> list[CorrelationMatch]:
        matches: list[CorrelationMatch] = []
        error_ids: list[str] = []
        anomaly_ids: list[str] = []

        for ev in context.events:
            metric = ev.metadata.get("metric", "")
            if self._ERROR_PATTERN.search(metric):
                error_ids.append(ev.event_id)
            elif ev.category.value in ("metric_anomaly", "outage", "dependency_failure"):
                anomaly_ids.append(ev.event_id)

        for i in range(len(error_ids)):
            for j in range(i + 1, len(error_ids)):
                matches.append(
                    CorrelationMatch(
                        event_id_a=error_ids[i],
                        event_id_b=error_ids[j],
                        strategy_type=self.strategy_type,
                        signal=self.signal,
                        score=0.8,
                        metadata={"match_type": "error_to_error"},
                    )
                )

        for err_id in error_ids:
            for anom_id in anomaly_ids:
                matches.append(
                    CorrelationMatch(
                        event_id_a=err_id,
                        event_id_b=anom_id,
                        strategy_type=self.strategy_type,
                        signal=self.signal,
                        score=0.5,
                        metadata={"match_type": "error_to_anomaly"},
                    )
                )

        return matches
