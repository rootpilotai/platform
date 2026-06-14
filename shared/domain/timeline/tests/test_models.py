from datetime import UTC, datetime, timedelta

from shared.contracts.events.enums import Severity
from shared.domain.timeline.enums import TimelineEventCategory, TimelineEventSource
from shared.domain.timeline.models import IncidentTimeline, TimelineEvent, TimelineWindow


class TestTimelineEvent:
    async def test_minimal_event(self) -> None:
        ts = datetime.now(UTC)
        event = TimelineEvent(
            event_id="evt-1",
            category=TimelineEventCategory.FAILURE,
            source=TimelineEventSource.TELEMETRY,
            timestamp=ts,
            service_name="api-gateway",
            title="High error rate detected",
        )
        assert event.event_id == "evt-1"
        assert event.category == TimelineEventCategory.FAILURE
        assert event.description == ""
        assert event.trace_id is None
        assert event.tags == {}

    async def test_event_with_all_fields(self) -> None:
        ts = datetime.now(UTC)
        event = TimelineEvent(
            event_id="evt-2",
            category=TimelineEventCategory.DEPLOYMENT,
            source=TimelineEventSource.DEPLOYMENT,
            timestamp=ts,
            service_name="user-service",
            title="Deployed v2.1.0",
            description="Rolled out new auth module",
            trace_id="trace-abc",
            request_id="req-123",
            severity=Severity.INFO,
            tags={"env": "prod", "region": "us-east"},
            metadata={"commit": "a1b2c3d"},
        )
        assert event.trace_id == "trace-abc"
        assert event.request_id == "req-123"
        assert event.severity == Severity.INFO

    async def test_round_trip_json(self) -> None:
        ts = datetime.now(UTC)
        original = TimelineEvent(
            event_id="evt-3",
            category=TimelineEventCategory.RECOVERY,
            source=TimelineEventSource.LOG,
            timestamp=ts,
            service_name="db",
            title="Connection pool restored",
        )
        restored = TimelineEvent.model_validate_json(original.model_dump_json())
        assert restored == original


class TestTimelineWindow:
    async def test_empty_window(self) -> None:
        start = datetime(2026, 6, 12, 10, 0, 0, tzinfo=UTC)
        end = datetime(2026, 6, 12, 10, 5, 0, tzinfo=UTC)
        window = TimelineWindow(window_start=start, window_end=end)
        assert window.event_count == 0
        assert window.duration_seconds == 300.0

    async def test_window_with_events(self) -> None:
        start = datetime(2026, 6, 12, 10, 0, 0, tzinfo=UTC)
        end = datetime(2026, 6, 12, 10, 5, 0, tzinfo=UTC)
        event = TimelineEvent(
            event_id="e1",
            category=TimelineEventCategory.FAILURE,
            source=TimelineEventSource.TELEMETRY,
            timestamp=datetime(2026, 6, 12, 10, 2, 0, tzinfo=UTC),
            service_name="api",
            title="failure",
        )
        window = TimelineWindow(window_start=start, window_end=end, events=[event])
        assert window.event_count == 1
        assert window.events[0].event_id == "e1"


class TestIncidentTimeline:
    async def test_empty_timeline(self) -> None:
        timeline = IncidentTimeline(incident_id="inc-1", service="api-gateway")
        assert timeline.incident_id == "inc-1"
        assert timeline.windows == []
        assert timeline.event_count == 0
        assert timeline.window_count == 0
        assert timeline.start_time is None
        assert timeline.end_time is None

    async def test_timeline_with_windows(self) -> None:
        start = datetime(2026, 6, 12, 10, 0, 0, tzinfo=UTC)
        mid = datetime(2026, 6, 12, 10, 5, 0, tzinfo=UTC)
        end = datetime(2026, 6, 12, 10, 10, 0, tzinfo=UTC)

        w1 = TimelineWindow(
            window_start=start,
            window_end=mid,
            events=[
                TimelineEvent(
                    event_id="e1",
                    category=TimelineEventCategory.FAILURE,
                    source=TimelineEventSource.TELEMETRY,
                    timestamp=datetime(2026, 6, 12, 10, 2, 0, tzinfo=UTC),
                    service_name="api",
                    title="fail-1",
                )
            ],
        )
        w2 = TimelineWindow(
            window_start=mid,
            window_end=end,
            events=[
                TimelineEvent(
                    event_id="e2",
                    category=TimelineEventCategory.RETRY,
                    source=TimelineEventSource.TELEMETRY,
                    timestamp=datetime(2026, 6, 12, 10, 7, 0, tzinfo=UTC),
                    service_name="api",
                    title="retry-1",
                ),
                TimelineEvent(
                    event_id="e3",
                    category=TimelineEventCategory.RECOVERY,
                    source=TimelineEventSource.TELEMETRY,
                    timestamp=datetime(2026, 6, 12, 10, 9, 0, tzinfo=UTC),
                    service_name="api",
                    title="recovered",
                ),
            ],
        )

        timeline = IncidentTimeline(
            incident_id="inc-1",
            service="api-gateway",
            windows=[w1, w2],
            window_duration_seconds=300,
        )

        assert timeline.window_count == 2
        assert timeline.event_count == 3
        assert timeline.start_time == start
        assert timeline.end_time == end

        flattened = timeline.events
        assert len(flattened) == 3
        assert [e.event_id for e in flattened] == ["e1", "e2", "e3"]

    async def test_json_round_trip(self) -> None:
        ts = datetime(2026, 6, 12, 10, 0, 0, tzinfo=UTC)
        timeline = IncidentTimeline(
            incident_id="inc-2",
            service="db",
            windows=[
                TimelineWindow(
                    window_start=ts,
                    window_end=ts + timedelta(minutes=5),
                    events=[
                        TimelineEvent(
                            event_id="e1",
                            category=TimelineEventCategory.OUTAGE,
                            source=TimelineEventSource.INCIDENT,
                            timestamp=ts,
                            service_name="db",
                            title="db outage",
                        )
                    ],
                )
            ],
        )
        restored = IncidentTimeline.model_validate_json(timeline.model_dump_json())
        assert restored.model_dump() == timeline.model_dump()
