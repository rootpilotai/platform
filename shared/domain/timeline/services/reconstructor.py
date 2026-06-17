import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from shared.contracts.events.telemetry import TelemetryEvent
from shared.domain.timeline.enums import TimelineEventCategory, TimelineEventSource
from shared.domain.timeline.models import IncidentTimeline, TimelineEvent, TimelineWindow

ClassifierFn = Callable[[str, float, dict[str, str]], TimelineEventCategory]


def _default_classifier(metric: str, _value: float, _tags: dict[str, str]) -> TimelineEventCategory:
    _patterns: dict[re.Pattern[str], TimelineEventCategory] = {
        re.compile(r"^(error|failure|exception|fault)", re.IGNORECASE): TimelineEventCategory.FAILURE,
        re.compile(r"^retry", re.IGNORECASE): TimelineEventCategory.RETRY,
        re.compile(r"^(deploy|rollout|release)", re.IGNORECASE): TimelineEventCategory.DEPLOYMENT,
        re.compile(r"^(outage|downtime|unreachable)", re.IGNORECASE): TimelineEventCategory.OUTAGE,
        re.compile(r"^(recover|restore|heal)", re.IGNORECASE): TimelineEventCategory.RECOVERY,
        re.compile(r"^config", re.IGNORECASE): TimelineEventCategory.CONFIG_CHANGE,
        re.compile(r"^(scale|autoscale)", re.IGNORECASE): TimelineEventCategory.SCALING_EVENT,
        re.compile(r"^(health|heartbeat|ping)", re.IGNORECASE): TimelineEventCategory.HEALTH_CHECK,
        re.compile(r"^(dependency|upstream|downstream)", re.IGNORECASE): TimelineEventCategory.DEPENDENCY_FAILURE,
    }

    for pattern, category in _patterns.items():
        if pattern.search(metric):
            return category

    return TimelineEventCategory.METRIC_ANOMALY


class EventClassifier:
    def __init__(self, classifier_fn: ClassifierFn | None = None) -> None:
        self._classifier = classifier_fn or _default_classifier

    def classify(self, metric: str, value: float, tags: dict[str, str] | None = None) -> TimelineEventCategory:
        return self._classifier(metric, value, tags or {})


class TimelineReconstructor:
    def __init__(
        self,
        window_duration_seconds: int = 300,
        classifier: EventClassifier | None = None,
    ) -> None:
        if window_duration_seconds < 1:
            raise ValueError("window_duration_seconds must be >= 1")
        self._window_duration = window_duration_seconds
        self._classifier = classifier or EventClassifier()

    def build_timeline(
        self,
        incident_id: str,
        service: str,
        events: list[TimelineEvent],
    ) -> IncidentTimeline:
        sorted_events = sorted(events, key=lambda e: e.timestamp)
        windows = self._group_into_windows(sorted_events)
        return IncidentTimeline(
            incident_id=incident_id,
            service=service,
            windows=windows,
            window_duration_seconds=self._window_duration,
        )

    def telemetry_to_timeline_events(self, telemetry_events: list[TelemetryEvent]) -> list[TimelineEvent]:
        return [self._convert_telemetry(ev) for ev in telemetry_events]

    def _convert_telemetry(self, event: TelemetryEvent) -> TimelineEvent:
        category = self._classifier.classify(
            metric=event.metric,
            value=event.value,
            tags=event.tags,
        )
        return TimelineEvent(
            event_id=uuid4().hex,
            category=category,
            source=TimelineEventSource.TELEMETRY,
            timestamp=event.timestamp,
            service_name=event.source,
            title=f"{category.value}: {event.metric}={event.value}",
            description=f"{event.metric} recorded at {event.value} {event.unit or ''}",
            trace_id=event.trace_id,
            span_id=event.span_id,
            parent_span_id=event.parent_span_id,
            request_id=event.request_id,
            severity=event.severity,
            tags=event.tags,
            metadata={"metric": event.metric, "unit": event.unit or "", "value": str(event.value)},
        )

    def _group_into_windows(self, events: list[TimelineEvent]) -> list[TimelineWindow]:
        if not events:
            return []

        windows: list[TimelineWindow] = []
        window_start = self._floor_to_window(events[0].timestamp)
        window_end = window_start + timedelta(seconds=self._window_duration)
        current_window = TimelineWindow(window_start=window_start, window_end=window_end)

        for event in events:
            if event.timestamp >= window_end:
                windows.append(current_window)
                window_start = self._floor_to_window(event.timestamp)
                window_end = window_start + timedelta(seconds=self._window_duration)
                current_window = TimelineWindow(window_start=window_start, window_end=window_end)
            current_window.events.append(event)

        if current_window.events:
            windows.append(current_window)

        return windows

    def _floor_to_window(self, dt: datetime) -> datetime:
        epoch = int(dt.timestamp())
        floored = epoch - (epoch % self._window_duration)
        return datetime.fromtimestamp(floored, tz=UTC)
