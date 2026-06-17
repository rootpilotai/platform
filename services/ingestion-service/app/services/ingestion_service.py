import logging
from datetime import UTC, datetime

from app.schemas import IngestRequest
from shared.contracts import Event, EventBus, ServiceName, TelemetryEvent
from shared.contracts.events import EventTopic
from shared.contracts.events.enums import Severity

logger = logging.getLogger(__name__)


class IngestionService:
    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    async def process_telemetry(self, request: IngestRequest) -> str:
        timestamp = self._parse_timestamp(request.timestamp)
        severity = self._parse_severity(request.severity)
        telemetry = TelemetryEvent(
            metric=request.metric,
            value=request.value,
            unit=request.unit,
            tags=request.tags,
            source=request.source,
            timestamp=timestamp,
            trace_id=request.trace_id,
            span_id=request.span_id,
            parent_span_id=request.parent_span_id,
            request_id=request.request_id,
            severity=severity,
        )
        envelope = Event(
            source=ServiceName.INGESTION,
            topic=EventTopic.TELEMETRY_INGESTED,
            payload=telemetry.model_dump(),
        )
        await self._event_bus.publish(envelope)

        logger.info(
            "Telemetry ingested",
            extra={"event_id": envelope.id, "metric": telemetry.metric, "source": telemetry.source},
        )
        return envelope.id

    def _parse_timestamp(self, raw: str | None) -> datetime:
        if raw is None:
            return datetime.now(UTC)
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            logger.warning("Invalid timestamp format, falling back to now", extra={"raw": raw})
            return datetime.now(UTC)

    @staticmethod
    def _parse_severity(raw: str | None) -> Severity | None:
        if raw is None:
            return None
        try:
            return Severity(raw.lower())
        except ValueError:
            logger.warning("Invalid severity value, ignoring", extra={"raw": raw})
            return None
