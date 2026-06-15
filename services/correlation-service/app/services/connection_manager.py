"""Manages incoming telemetry events, triggers correlation, and publishes investigation requests."""

import logging
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from shared.contracts import Event, EventBus
from shared.contracts.events import EventTopic, InvestigationRequestedEvent, ServiceName
from shared.contracts.events.telemetry import TelemetryEvent
from shared.domain.correlation.engine import CorrelationEngine
from shared.domain.incident.context.builders import (
    ContextBuilder,
    CorrelationBuilder,
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
        window_seconds: int = 300,
        min_events: int = 3,
        min_score: float = 0.2,
        incident_severity: str = "ERROR",
    ) -> None:
        self._engine = engine
        self._reconstructor = reconstructor
        self._event_bus = event_bus
        self._window_seconds = window_seconds
        self._min_events = min_events
        self._min_score = min_score
        self._incident_severity = incident_severity
        self._telemetry_events: list[TelemetryEvent] = []

    async def handle_telemetry_event(self, event: Event) -> None:
        telemetry = TelemetryEvent(**event.payload)
        self._telemetry_events.append(telemetry)
        self._prune_old_events()

        logger.debug(
            "Buffered telemetry event",
            extra={"metric": telemetry.metric, "buffer_size": len(self._telemetry_events)},
        )

        if len(self._telemetry_events) < self._min_events:
            return

        await self._run_correlation()

    async def _run_correlation(self) -> None:
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

        builders: list[ContextBuilder] = [
            TimelineBuilder(self._reconstructor),
            CorrelationBuilder(self._engine),
            TraceBuilder(),
        ]
        aggregator = _build_aggregator(builders)
        context = await aggregator.aggregate(
            incident_id=incident_id,
            primary_service=primary_service,
            events=timeline_events,
            severity=self._incident_severity,
            title=f"Correlated incident detected across {len(services)} service(s)",
            detected_at=datetime.now(UTC),
        )

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

    def _prune_old_events(self) -> None:
        cutoff = datetime.now(UTC) - timedelta(seconds=self._window_seconds)
        self._telemetry_events = [ev for ev in self._telemetry_events if ev.timestamp >= cutoff]

    async def close(self) -> None:
        self._telemetry_events.clear()


def _build_aggregator(builders: list[ContextBuilder]):
    from shared.domain.incident.context.aggregator import IncidentContextAggregator

    return IncidentContextAggregator(builders)
