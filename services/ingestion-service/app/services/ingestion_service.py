import logging
from datetime import datetime, timezone

from app.schemas import IngestRequest
from shared.contracts import Event, EventBus, ServiceName, TelemetryEvent

logger = logging.getLogger(__name__)


class IngestionService:
    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    async def process_telemetry(self, request: IngestRequest) -> str:
        timestamp = self._parse_timestamp(request.timestamp)
        telemetry = TelemetryEvent(
            metric=request.metric,
            value=request.value,
            unit=request.unit,
            tags=request.tags,
            source=request.source,
            timestamp=timestamp,
        )
        envelope = Event(
            source=ServiceName.INGESTION,
            topic="telemetry.ingested",
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
            return datetime.now(timezone.utc)
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            logger.warning("Invalid timestamp format, falling back to now", extra={"raw": raw})
            return datetime.now(timezone.utc)
