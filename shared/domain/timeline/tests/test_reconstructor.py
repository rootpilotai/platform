from datetime import UTC, datetime

import pytest

from shared.contracts.events.telemetry import TelemetryEvent
from shared.domain.timeline.enums import TimelineEventCategory, TimelineEventSource
from shared.domain.timeline.models import TimelineEvent
from shared.domain.timeline.services.reconstructor import TimelineReconstructor


class TestWindowGrouping:
    async def test_empty_events(self) -> None:
        r = TimelineReconstructor()
        timeline = r.build_timeline(incident_id="inc-1", service="api", events=[])
        assert timeline.event_count == 0
        assert timeline.window_count == 0

    async def test_single_event_single_window(self) -> None:
        ts = datetime(2026, 6, 12, 10, 0, 0, tzinfo=UTC)
        event = TimelineEvent(
            event_id="e1",
            category=TimelineEventCategory.FAILURE,
            source=TimelineEventSource.TELEMETRY,
            timestamp=ts,
            service_name="api",
            title="err",
        )
        r = TimelineReconstructor(window_duration_seconds=300)
        timeline = r.build_timeline("inc-1", "api", [event])
        assert timeline.window_count == 1
        assert timeline.event_count == 1

    async def test_events_grouped_into_separate_windows(self) -> None:
        r = TimelineReconstructor(window_duration_seconds=300)
        base = datetime(2026, 6, 12, 10, 0, 0, tzinfo=UTC)

        events = [
            TimelineEvent(
                event_id=f"e{i}",
                category=TimelineEventCategory.FAILURE,
                source=TimelineEventSource.TELEMETRY,
                timestamp=base,
                service_name="api",
                title="e1",
            )
            for i in range(1, 4)
        ]
        events[1] = TimelineEvent(
            event_id="e2",
            category=TimelineEventCategory.RETRY,
            source=TimelineEventSource.TELEMETRY,
            timestamp=base.replace(hour=10, minute=5, second=1),
            service_name="api",
            title="e2",
        )
        events[2] = TimelineEvent(
            event_id="e3",
            category=TimelineEventCategory.RECOVERY,
            source=TimelineEventSource.TELEMETRY,
            timestamp=base.replace(hour=10, minute=10, second=0),
            service_name="api",
            title="e3",
        )

        timeline = r.build_timeline("inc-1", "api", events)
        assert timeline.window_count == 3
        assert timeline.event_count == 3

    async def test_events_sorted_chronologically(self) -> None:
        r = TimelineReconstructor(window_duration_seconds=300)
        base = datetime(2026, 6, 12, 10, 0, 0, tzinfo=UTC)

        events = [
            TimelineEvent(
                event_id="e3",
                category=TimelineEventCategory.RECOVERY,
                source=TimelineEventSource.TELEMETRY,
                timestamp=base.replace(minute=6),
                service_name="api",
                title="recovery",
            ),
            TimelineEvent(
                event_id="e1",
                category=TimelineEventCategory.FAILURE,
                source=TimelineEventSource.TELEMETRY,
                timestamp=base.replace(minute=1),
                service_name="api",
                title="failure",
            ),
            TimelineEvent(
                event_id="e2",
                category=TimelineEventCategory.RETRY,
                source=TimelineEventSource.TELEMETRY,
                timestamp=base.replace(minute=3),
                service_name="api",
                title="retry",
            ),
        ]

        timeline = r.build_timeline("inc-1", "api", events)
        ids = [e.event_id for e in timeline.events]
        assert ids == ["e1", "e2", "e3"]

    async def test_window_boundary_alignment(self) -> None:
        r = TimelineReconstructor(window_duration_seconds=60)
        ts = datetime(2026, 6, 12, 10, 2, 30, tzinfo=UTC)
        event = TimelineEvent(
            event_id="e1",
            category=TimelineEventCategory.FAILURE,
            source=TimelineEventSource.TELEMETRY,
            timestamp=ts,
            service_name="api",
            title="failure",
        )
        timeline = r.build_timeline("inc-1", "api", [event])
        assert timeline.window_count == 1
        w = timeline.windows[0]
        assert w.window_start.minute == 2
        assert w.window_start.second == 0


class TestTelemetryConversion:
    async def test_error_metric_classified_as_failure(self) -> None:
        r = TimelineReconstructor()
        telemetry = TelemetryEvent(metric="error.rate", value=0.15, source="api")
        events = r.telemetry_to_timeline_events([telemetry])
        assert len(events) == 1
        assert events[0].category == TimelineEventCategory.FAILURE
        assert events[0].source == TimelineEventSource.TELEMETRY
        assert events[0].service_name == "api"

    async def test_retry_metric_classified_as_retry(self) -> None:
        r = TimelineReconstructor()
        telemetry = TelemetryEvent(metric="retry.count", value=5.0, source="worker")
        events = r.telemetry_to_timeline_events([telemetry])
        assert events[0].category == TimelineEventCategory.RETRY

    async def test_deploy_metric_classified_as_deployment(self) -> None:
        r = TimelineReconstructor()
        telemetry = TelemetryEvent(metric="deploy.status", value=1.0, source="api")
        events = r.telemetry_to_timeline_events([telemetry])
        assert events[0].category == TimelineEventCategory.DEPLOYMENT

    async def test_unknown_metric_falls_back_to_anomaly(self) -> None:
        r = TimelineReconstructor()
        telemetry = TelemetryEvent(metric="cpu.usage", value=95.0, source="api")
        events = r.telemetry_to_timeline_events([telemetry])
        assert events[0].category == TimelineEventCategory.METRIC_ANOMALY

    async def test_telemetry_metadata_preserved(self) -> None:
        r = TimelineReconstructor()
        telemetry = TelemetryEvent(
            metric="cpu.usage",
            value=95.0,
            unit="%",
            source="api",
            tags={"host": "web-01"},
        )
        events = r.telemetry_to_timeline_events([telemetry])
        ev = events[0]
        assert ev.tags == {"host": "web-01"}
        assert ev.metadata["metric"] == "cpu.usage"
        assert ev.metadata["value"] == "95.0"
        assert ev.metadata["unit"] == "%"
        assert "metric_anomaly: cpu.usage=95.0" in ev.title


class TestFullReconstruction:
    async def test_build_timeline_from_telemetry(self) -> None:
        r = TimelineReconstructor(window_duration_seconds=300)
        base = datetime(2026, 6, 12, 10, 0, 0, tzinfo=UTC)

        telemetry_events = [
            TelemetryEvent(metric="error.rate", value=0.3, source="api", timestamp=base),
            TelemetryEvent(metric="retry.count", value=10.0, source="api", timestamp=base.replace(minute=3)),
            TelemetryEvent(metric="deploy.status", value=1.0, source="api", timestamp=base.replace(minute=6)),
            TelemetryEvent(metric="cpu.usage", value=95.0, source="api", timestamp=base.replace(minute=9)),
        ]

        timeline_events = r.telemetry_to_timeline_events(telemetry_events)
        timeline = r.build_timeline("inc-42", "api", timeline_events)

        assert timeline.incident_id == "inc-42"
        assert timeline.service == "api"
        assert timeline.event_count == 4

        categories = [e.category for e in timeline.events]
        assert categories == [
            TimelineEventCategory.FAILURE,
            TimelineEventCategory.RETRY,
            TimelineEventCategory.DEPLOYMENT,
            TimelineEventCategory.METRIC_ANOMALY,
        ]


class TestWindowDurationValidation:
    async def test_rejects_zero_window_duration(self) -> None:
        with pytest.raises(ValueError, match="window_duration_seconds must be >= 1"):
            TimelineReconstructor(window_duration_seconds=0)

    async def test_rejects_negative_window_duration(self) -> None:
        with pytest.raises(ValueError, match="window_duration_seconds must be >= 1"):
            TimelineReconstructor(window_duration_seconds=-1)
