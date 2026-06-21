"""Manages incoming telemetry events, triggers correlation, and publishes investigation requests."""

import logging
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from shared.contracts import Event, EventBus
from shared.contracts.events import EventTopic, InvestigationRequestedEvent, ServiceName
from shared.contracts.events.telemetry import TelemetryEvent
from shared.contracts.interfaces.incident_store import IncidentStore
from shared.domain.correlation.engine import CorrelationEngine
from shared.domain.graph.store import GraphStore
from shared.domain.incident.context.builders import (
    ContextBuilder,
    CorrelationBuilder,
    ImpactBuilder,
    TimelineBuilder,
    TraceBuilder,
)
from shared.domain.timeline.services import TimelineReconstructor

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(
        self,
        engine: CorrelationEngine,
        reconstructor: TimelineReconstructor,
        event_bus: EventBus,
        incident_store: IncidentStore | None = None,
        graph_store: GraphStore | None = None,
        window_seconds: int = 300,
        min_events: int = 3,
        min_score: float = 0.2,
        incident_severity: str = "ERROR",
        max_buffer_size: int = 1000,
        min_correlation_interval: float = 60.0,
    ) -> None:
        self._engine = engine
        self._reconstructor = reconstructor
        self._event_bus = event_bus
        self._incident_store = incident_store
        self._graph_store = graph_store
        self._window_seconds = window_seconds
        self._min_events = min_events
        self._min_score = min_score
        self._incident_severity = incident_severity
        self._max_buffer_size = max_buffer_size
        self._min_correlation_interval = min_correlation_interval
        self._telemetry_events: list[TelemetryEvent] = []
        self._last_correlation_time: datetime | None = None

    async def handle_telemetry_event(self, event: Event) -> None:
        telemetry = TelemetryEvent(**event.payload)
        self._telemetry_events.append(telemetry)
        self._prune_old_events()
        self._enforce_max_buffer()

        logger.debug(
            "Buffered telemetry event",
            extra={"metric": telemetry.metric, "buffer_size": len(self._telemetry_events)},
        )

        if len(self._telemetry_events) < self._min_events:
            return

        if not self._should_correlate():
            return

        await self._run_correlation()

    def _should_correlate(self) -> bool:
        if self._last_correlation_time is None:
            return True
        elapsed = (datetime.now(UTC) - self._last_correlation_time).total_seconds()
        if elapsed < self._min_correlation_interval:
            logger.debug(
                "Correlation debounced — last run %.0fs ago (min interval %.0fs)",
                elapsed,
                self._min_correlation_interval,
            )
            return False
        return True

    async def _run_correlation(self) -> None:
        self._last_correlation_time = datetime.now(UTC)
        timeline_events = self._reconstructor.telemetry_to_timeline_events(self._telemetry_events)
        result = await self._engine.correlate(timeline_events, min_score=self._min_score)

        if not result.groups:
            logger.debug("No correlation groups found — skipping investigation request")
            return

        logger.info(
            "Correlation produced groups — triggering investigation",
            extra={"groups": len(result.groups), "events": result.total_events},
        )

        incident_id = f"inc-{uuid4().hex[:12]}"
        services = {ev.source for ev in self._telemetry_events}
        primary_service = next(iter(services)) if services else "unknown"

        reachable_services: set[str] = set()
        for ev in self._telemetry_events:
            seen = ev.tags.get("_seen_sources", "")
            if seen:
                reachable_services.update(s.strip() for s in seen.split(",") if s.strip())
        # A service that had failure/error events is NOT reachable — it's actively failing
        reachable_services -= services

        builders: list[ContextBuilder] = [
            TimelineBuilder(self._reconstructor),
            CorrelationBuilder(self._engine),
            TraceBuilder(),
        ]
        if self._graph_store is not None:
            builders.append(ImpactBuilder(self._graph_store))
        aggregator = _build_aggregator(builders)
        context = await aggregator.aggregate(
            incident_id=incident_id,
            primary_service=primary_service,
            events=timeline_events,
            severity=self._incident_severity,
            title=f"Correlated incident detected across {len(services)} service(s)",
            detected_at=datetime.now(UTC),
            reachable_services=reachable_services,
        )

        if self._incident_store is not None:
            await self._incident_store.store(context)

        requested = InvestigationRequestedEvent(
            investigation_id=incident_id,
            incident_id=incident_id,
            context=context.model_dump(),
        )
        outbound = Event(
            source=ServiceName.CORRELATION,
            topic=EventTopic.INVESTIGATION_REQUESTED,
            payload=requested.model_dump(),
        )
        await self._event_bus.publish(outbound)
        logger.info("Published investigation.requested", extra={"incident_id": incident_id})

        self._telemetry_events.clear()
        self._last_correlation_time = datetime.now(UTC)

    def _prune_old_events(self) -> None:
        if not self._telemetry_events:
            return
        newest = max(ev.timestamp for ev in self._telemetry_events)
        cutoff = newest - timedelta(seconds=self._window_seconds)
        self._telemetry_events = [ev for ev in self._telemetry_events if ev.timestamp >= cutoff]

    def _enforce_max_buffer(self) -> None:
        if len(self._telemetry_events) > self._max_buffer_size:
            excess = len(self._telemetry_events) - self._max_buffer_size
            logger.warning("Buffer exceeded max size, dropping %d oldest event(s)", excess)
            self._telemetry_events = self._telemetry_events[excess:]

    async def close(self) -> None:
        self._telemetry_events.clear()
        self._last_correlation_time = None


def _build_aggregator(builders: list[ContextBuilder]):
    from shared.domain.incident.context.aggregator import IncidentContextAggregator

    return IncidentContextAggregator(builders)
