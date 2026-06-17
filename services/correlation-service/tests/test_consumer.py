"""Tests for the telemetry event consumer and correlation trigger."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.services.connection_manager import ConnectionManager

from shared.contracts import Event
from shared.contracts.events import EventTopic, ServiceName
from shared.contracts.events.telemetry import TelemetryEvent
from shared.domain.correlation.engine import CorrelationEngine
from shared.domain.timeline.services import TimelineReconstructor


@pytest.fixture
def mock_event_bus() -> MagicMock:
    bus = MagicMock()
    bus.publish = AsyncMock()
    return bus


@pytest.fixture
def engine() -> CorrelationEngine:
    return CorrelationEngine()


@pytest.fixture
def reconstructor() -> TimelineReconstructor:
    return TimelineReconstructor()


@pytest.fixture
def mock_incident_store() -> MagicMock:
    store = MagicMock()
    store.store = AsyncMock()
    return store


@pytest.fixture
def manager(
    engine: CorrelationEngine,
    reconstructor: TimelineReconstructor,
    mock_event_bus: MagicMock,
    mock_incident_store: MagicMock,
) -> ConnectionManager:
    return ConnectionManager(
        engine=engine,
        reconstructor=reconstructor,
        event_bus=mock_event_bus,
        incident_store=mock_incident_store,
        window_seconds=3600,
        min_events=2,
        min_score=0.0,
        incident_severity="ERROR",
        min_correlation_interval=0.0,
    )


def _make_telemetry_event(
    metric: str = "cpu.usage",
    value: float = 95.0,
    source: str = "web-service",
) -> Event:
    telem = TelemetryEvent(metric=metric, value=value, source=source, timestamp=datetime.now(UTC))
    return Event(
        source=ServiceName.INGESTION,
        topic=EventTopic.TELEMETRY_INGESTED,
        payload=telem.model_dump(),
    )


class TestConnectionManager:
    async def test_buffers_events_below_threshold(self, manager: ConnectionManager) -> None:
        event = _make_telemetry_event()
        await manager.handle_telemetry_event(event)
        assert len(manager._telemetry_events) == 1
        manager._event_bus.publish.assert_not_called()

    async def test_triggers_correlation_at_threshold(self, manager: ConnectionManager) -> None:
        ev1 = _make_telemetry_event(metric="cpu.usage", value=95.0, source="web-01")
        ev2 = _make_telemetry_event(metric="mem.usage", value=90.0, source="web-01")

        await manager.handle_telemetry_event(ev1)
        await manager.handle_telemetry_event(ev2)

        assert manager._event_bus.publish.await_count >= 1
        call_args = manager._event_bus.publish.await_args_list
        published_topics = [args[0][0].topic for args in call_args]
        assert EventTopic.INVESTIGATION_REQUESTED in published_topics

    async def test_clears_buffer_after_successful_correlation(self, manager: ConnectionManager) -> None:
        ev1 = _make_telemetry_event(metric="cpu.usage", value=95.0, source="web-01")
        ev2 = _make_telemetry_event(metric="mem.usage", value=90.0, source="web-01")

        await manager.handle_telemetry_event(ev1)
        await manager.handle_telemetry_event(ev2)

        assert len(manager._telemetry_events) == 0

    async def test_does_not_clear_buffer_when_no_groups_found(self, manager: ConnectionManager) -> None:
        manager._min_score = 0.5
        ev1 = _make_telemetry_event(metric="cpu.usage", value=50.0, source="svc-a")
        ev2 = _make_telemetry_event(metric="cpu.usage", value=51.0, source="svc-b")

        await manager.handle_telemetry_event(ev1)
        await manager.handle_telemetry_event(ev2)

        assert len(manager._telemetry_events) == 2

    async def test_persists_incident_to_store_on_correlation(
        self, manager: ConnectionManager, mock_incident_store: MagicMock
    ) -> None:
        ev1 = _make_telemetry_event(metric="cpu.usage", value=95.0, source="web-01")
        ev2 = _make_telemetry_event(metric="mem.usage", value=90.0, source="web-01")

        await manager.handle_telemetry_event(ev1)
        await manager.handle_telemetry_event(ev2)

        mock_incident_store.store.assert_awaited_once()

    async def test_prunes_old_events(self) -> None:
        bus = MagicMock()
        bus.publish = AsyncMock()
        now = datetime.now(UTC)
        old_ts = now - timedelta(seconds=600)
        recent_ts = now

        telem_old = TelemetryEvent(metric="cpu.usage", value=50.0, source="web", timestamp=old_ts)
        telem_recent = TelemetryEvent(metric="cpu.usage", value=95.0, source="web", timestamp=recent_ts)

        manager = ConnectionManager(
            engine=CorrelationEngine(),
            reconstructor=TimelineReconstructor(),
            event_bus=bus,
            window_seconds=300,
            min_events=2,
            min_score=0.0,
        )
        manager._telemetry_events = [telem_old, telem_recent]
        manager._prune_old_events()
        assert len(manager._telemetry_events) == 1
        assert manager._telemetry_events[0].timestamp == recent_ts

    async def test_skips_correlation_when_no_groups(self, manager: ConnectionManager) -> None:
        manager._min_score = 0.9
        ev1 = _make_telemetry_event(metric="cpu.usage", value=50.0, source="svc-a")
        ev2 = _make_telemetry_event(metric="cpu.usage", value=51.0, source="svc-b")

        await manager.handle_telemetry_event(ev1)
        await manager.handle_telemetry_event(ev2)

        manager._event_bus.publish.assert_not_called()

    async def test_publishes_investigation_requested_with_context(self) -> None:
        bus = MagicMock()
        bus.publish = AsyncMock()
        engine = CorrelationEngine()
        recon = TimelineReconstructor()

        manager = ConnectionManager(
            engine=engine,
            reconstructor=recon,
            event_bus=bus,
            window_seconds=3600,
            min_events=2,
            min_score=0.0,
            incident_severity="ERROR",
        )

        ev1 = _make_telemetry_event(metric="error.rate", value=0.95, source="api-gateway")
        ev2 = _make_telemetry_event(metric="error.rate", value=0.90, source="api-gateway")

        await manager.handle_telemetry_event(ev1)
        await manager.handle_telemetry_event(ev2)

        bus.publish.assert_awaited()
        published_event: Event = bus.publish.await_args[0][0]
        assert published_event.topic == EventTopic.INVESTIGATION_REQUESTED
        assert published_event.source == ServiceName.CORRELATION
        assert "investigation_id" in published_event.payload
        assert "context" in published_event.payload

    async def test_publish_does_not_happen_below_threshold(self, manager: ConnectionManager) -> None:
        event = _make_telemetry_event()
        await manager.handle_telemetry_event(event)
        manager._event_bus.publish.assert_not_called()

    async def test_close_clears_buffer(self, manager: ConnectionManager) -> None:
        event = _make_telemetry_event()
        await manager.handle_telemetry_event(event)
        assert len(manager._telemetry_events) == 1
        await manager.close()
        assert len(manager._telemetry_events) == 0

    async def test_handles_concurrent_events(self, manager: ConnectionManager) -> None:
        import asyncio

        events = [_make_telemetry_event(metric=f"metric-{i}", value=float(i), source="svc") for i in range(5)]
        await asyncio.gather(*[manager.handle_telemetry_event(ev) for ev in events])
        assert manager._event_bus.publish.await_count >= 1

    async def test_debounce_prevents_repeated_correlation(self, mock_event_bus: MagicMock) -> None:
        manager = ConnectionManager(
            engine=CorrelationEngine(),
            reconstructor=TimelineReconstructor(),
            event_bus=mock_event_bus,
            window_seconds=3600,
            min_events=2,
            min_score=0.0,
            min_correlation_interval=3600,
        )
        ev1 = _make_telemetry_event(metric="error.rate", value=0.95, source="api")
        ev2 = _make_telemetry_event(metric="error.rate", value=0.90, source="api")
        ev3 = _make_telemetry_event(metric="error.rate", value=0.85, source="api")

        await manager.handle_telemetry_event(ev1)
        await manager.handle_telemetry_event(ev2)
        assert mock_event_bus.publish.await_count == 1

        await manager.handle_telemetry_event(ev3)
        assert mock_event_bus.publish.await_count == 1

    async def test_enforces_max_buffer_size(self) -> None:
        bus = MagicMock()
        bus.publish = AsyncMock()
        manager = ConnectionManager(
            engine=CorrelationEngine(),
            reconstructor=TimelineReconstructor(),
            event_bus=bus,
            max_buffer_size=3,
            min_events=10,
            min_correlation_interval=0.0,
        )
        now = datetime.now(UTC)
        for i in range(5):
            ev = TelemetryEvent(
                metric=f"cpu.{i}",
                value=float(i),
                source="test",
                timestamp=now + timedelta(seconds=i),
            )
            envelope = Event(
                source=ServiceName.INGESTION,
                topic=EventTopic.TELEMETRY_INGESTED,
                payload=ev.model_dump(),
            )
            await manager.handle_telemetry_event(envelope)

        assert len(manager._telemetry_events) == 3


class TestConnectionManagerIntegration:
    async def test_full_event_flow(self, mock_event_bus: MagicMock) -> None:
        engine = CorrelationEngine()
        recon = TimelineReconstructor()
        manager = ConnectionManager(
            engine=engine,
            reconstructor=recon,
            event_bus=mock_event_bus,
            window_seconds=3600,
            min_events=3,
            min_score=0.0,
            min_correlation_interval=0.0,
        )

        events = [
            _make_telemetry_event(metric="error.count", value=10.0, source="api"),
            _make_telemetry_event(metric="error.count", value=20.0, source="api"),
            _make_telemetry_event(metric="error.count", value=30.0, source="api"),
        ]
        for ev in events:
            await manager.handle_telemetry_event(ev)

        assert mock_event_bus.publish.await_count >= 1
        published: Event = mock_event_bus.publish.await_args[0][0]
        assert published.topic == EventTopic.INVESTIGATION_REQUESTED
        payload = published.payload
        assert "investigation_id" in payload
        assert "incident_id" in payload
        assert "context" in payload
        assert "depth" in payload
        assert payload["depth"] == "standard"
