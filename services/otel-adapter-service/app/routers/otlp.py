from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, Request, Response

if TYPE_CHECKING:
    from app.services.otel_normalizer import OtelNormalizer
    from app.services.signal_extractor import SignalExtractor
    from shared.contracts import EventBus

from shared.contracts.events.base import Event as BusEvent

logger = logging.getLogger(__name__)

router = APIRouter()


def _try_parse_proto(
    payload: bytes,
    module_path: str,
    message_name: str,
) -> object | None:
    try:
        import importlib

        mod = importlib.import_module(module_path)
        msg_cls = getattr(mod, message_name)
        msg = msg_cls()
        msg.ParseFromString(payload)
        return msg
    except Exception:
        return None


async def _publish_or_log(
    event_bus: EventBus | None,
    normalizer: OtelNormalizer,
    extractor: SignalExtractor | None,
    parsed: object,
    data_type: str,
) -> int:
    if data_type == "metrics":
        raw_events = normalizer.normalize_metrics(parsed.resource_metrics)  # type: ignore
    elif data_type == "traces":
        raw_events = normalizer.normalize_traces(parsed.resource_spans)  # type: ignore
    else:
        raw_events = normalizer.normalize_logs(parsed.resource_logs)  # type: ignore

    if extractor is not None:
        decisions = [(ev, extractor.should_drop(ev)) for ev in raw_events]
        dropped = [ev for ev, d in decisions if d]
        events = [ev for ev, d in decisions if not d]
        if dropped:
            logger.info("Extractor sample dropped: %s", extractor.sample_event(dropped[0]))
        if events:
            logger.info("Extractor sample promoted: %s", extractor.sample_event(events[0]))
            seen_sources_csv = ",".join(sorted(extractor.seen_sources))
            for ev in events:
                ev.tags["_seen_sources"] = seen_sources_csv
    else:
        events = raw_events

    if event_bus is not None:
        for ev in events:
            bus_event = BusEvent(
                source=ev.source,
                topic="telemetry.ingested",
                payload=ev.model_dump(),
                trace_context=None,
            )
            await event_bus.publish(bus_event)
    else:
        for ev in events:
            logger.info("Event: %s", ev.model_dump_json())

    return len(events)


@router.post("/v1/metrics")
async def ingest_metrics(request: Request) -> Response:
    normalizer: OtelNormalizer = request.app.state.normalizer
    extractor: SignalExtractor | None = getattr(request.app.state, "extractor", None)
    event_bus: EventBus | None = request.app.state.event_bus

    raw = await request.body()
    parsed = _try_parse_proto(
        raw,
        "opentelemetry.proto.collector.metrics.v1.metrics_service_pb2",
        "ExportMetricsServiceRequest",
    )
    if parsed is None:
        logger.warning("Failed to parse OTLP metrics request")
        return Response(status_code=400, content="Invalid protobuf payload")

    count = await _publish_or_log(event_bus, normalizer, extractor, parsed, "metrics")
    logger.info("Published %d metric events after extraction", count)
    return Response(status_code=200)


@router.post("/v1/traces")
async def ingest_traces(request: Request) -> Response:
    normalizer: OtelNormalizer = request.app.state.normalizer
    extractor: SignalExtractor | None = getattr(request.app.state, "extractor", None)
    event_bus: EventBus | None = request.app.state.event_bus

    raw = await request.body()
    parsed = _try_parse_proto(
        raw,
        "opentelemetry.proto.collector.trace.v1.trace_service_pb2",
        "ExportTraceServiceRequest",
    )
    if parsed is None:
        logger.warning("Failed to parse OTLP traces request")
        return Response(status_code=400, content="Invalid protobuf payload")

    count = await _publish_or_log(event_bus, normalizer, extractor, parsed, "traces")
    logger.info("Published %d trace events after extraction", count)
    return Response(status_code=200)


@router.post("/v1/logs")
async def ingest_logs(request: Request) -> Response:
    normalizer: OtelNormalizer = request.app.state.normalizer
    extractor: SignalExtractor | None = getattr(request.app.state, "extractor", None)
    event_bus: EventBus | None = request.app.state.event_bus

    raw = await request.body()
    parsed = _try_parse_proto(
        raw,
        "opentelemetry.proto.collector.logs.v1.logs_service_pb2",
        "ExportLogsServiceRequest",
    )
    if parsed is None:
        logger.warning("Failed to parse OTLP logs request")
        return Response(status_code=400, content="Invalid protobuf payload")

    count = await _publish_or_log(event_bus, normalizer, extractor, parsed, "logs")
    logger.info("Published %d log events after extraction", count)
    return Response(status_code=200)
