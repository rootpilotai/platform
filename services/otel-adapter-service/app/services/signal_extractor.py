"""Signal Extraction Layer — filters low-signal telemetry before queue publication.

Drops routine telemetry (healthy spans, INFO logs, zero-value metrics)
and promotes only investigation-worthy signals (errors, failures, anomalies).
"""

import logging
from collections import Counter

from shared.contracts.events.telemetry import TelemetryEvent
from shared.domain.timeline.enums import TimelineEventCategory

logger = logging.getLogger(__name__)

_HIGH_SIGNAL_CATEGORIES = {
    TimelineEventCategory.FAILURE,
    TimelineEventCategory.DEPENDENCY_FAILURE,
    TimelineEventCategory.METRIC_ANOMALY,
}

_SELF_MONITORING_SOURCES = {"otelcol-contrib", "otel-adapter"}


class SignalExtractor:
    """Filters TelemetryEvents before they reach the event bus.

    Keeps events classified as FAILURE, DEPENDENCY_FAILURE, or METRIC_ANOMALY.
    Drops everything else (HEALTH_CHECK — healthy spans, INFO logs, routine metrics).

    Also filters telemetry from infrastructure services that generate
    self-monitoring noise (e.g. the OTEL collector itself).
    """

    def __init__(self, drop_collector_self_monitoring: bool = True) -> None:
        self._drop_collector_self_monitoring = drop_collector_self_monitoring
        self._counts: Counter[str] = Counter()
        self._seen_sources: set[str] = set()

    def should_drop(self, event: TelemetryEvent) -> bool:
        self._counts["received"] += 1
        self._seen_sources.add(event.source)

        if self._drop_collector_self_monitoring and event.source in _SELF_MONITORING_SOURCES:
            self._counts["dropped"] += 1
            return True

        category = getattr(event, "__otel_category__", None)

        if category in _HIGH_SIGNAL_CATEGORIES:
            self._counts["promoted"] += 1
            self._counts[f"promoted_{event.metric}"] += 1
            return False

        self._counts["dropped"] += 1
        self._counts[f"dropped_{event.metric}"] += 1
        return True

    def sample_event(self, event: TelemetryEvent) -> str:
        cat = getattr(event, "__otel_category__", None)
        return f"source={event.source} metric={event.metric} severity={event.severity} category={cat}"

    @property
    def counts(self) -> dict[str, int]:
        return dict(self._counts)

    @property
    def seen_sources(self) -> set[str]:
        return self._seen_sources.copy()

    @property
    def reduction_ratio(self) -> float:
        total = self._counts.get("received", 0)
        dropped = self._counts.get("dropped", 0)
        if total == 0:
            return 0.0
        return dropped / total

    def log_stats(self) -> None:
        total = self._counts.get("received", 0)
        if total == 0:
            return
        logger.info(
            "SignalExtractor stats: received=%d dropped=%d promoted=%d reduction=%.1f%%",
            total,
            self._counts.get("dropped", 0),
            self._counts.get("promoted", 0),
            self.reduction_ratio * 100,
        )
