from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, Request, Response

if TYPE_CHECKING:
    from app.services.otel_normalizer import OtelNormalizer
    from shared.contracts import EventBus

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


@router.post("/v1/metrics")
async def ingest_metrics(request: Request) -> Response:
    normalizer: OtelNormalizer = request.app.state.normalizer
    event_bus: EventBus = request.app.state.event_bus

    raw = await request.body()
    parsed = _try_parse_proto(
        raw,
        "opentelemetry.proto.collector.metrics.v1.metrics_service_pb2",
        "ExportMetricsServiceRequest",
    )
    if parsed is None:
        logger.warning("Failed to parse OTLP metrics request")
        return Response(status_code=400, content="Invalid protobuf payload")

    events = normalizer.normalize_metrics(parsed.resource_metrics)
    for ev in events:
        await event_bus.publish("telemetry.ingested", ev)

    logger.info("Ingested %d metric events", len(events))
    return Response(status_code=200)


@router.post("/v1/traces")
async def ingest_traces(request: Request) -> Response:
    normalizer: OtelNormalizer = request.app.state.normalizer
    event_bus: EventBus = request.app.state.event_bus

    raw = await request.body()
    parsed = _try_parse_proto(
        raw,
        "opentelemetry.proto.collector.trace.v1.trace_service_pb2",
        "ExportTraceServiceRequest",
    )
    if parsed is None:
        logger.warning("Failed to parse OTLP traces request")
        return Response(status_code=400, content="Invalid protobuf payload")

    events = normalizer.normalize_traces(parsed.resource_spans)
    for ev in events:
        await event_bus.publish("telemetry.ingested", ev)

    logger.info("Ingested %d trace events", len(events))
    return Response(status_code=200)


@router.post("/v1/logs")
async def ingest_logs(request: Request) -> Response:
    normalizer: OtelNormalizer = request.app.state.normalizer
    event_bus: EventBus = request.app.state.event_bus

    raw = await request.body()
    parsed = _try_parse_proto(
        raw,
        "opentelemetry.proto.collector.logs.v1.logs_service_pb2",
        "ExportLogsServiceRequest",
    )
    if parsed is None:
        logger.warning("Failed to parse OTLP logs request")
        return Response(status_code=400, content="Invalid protobuf payload")

    events = normalizer.normalize_logs(parsed.resource_logs)
    for ev in events:
        await event_bus.publish("telemetry.ingested", ev)

    logger.info("Ingested %d log events", len(events))
    return Response(status_code=200)
