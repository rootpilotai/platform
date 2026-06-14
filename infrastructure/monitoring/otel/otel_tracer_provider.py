"""Concrete OpenTelemetry implementation of the TracerProvider abstraction."""

from typing import Any

from opentelemetry import context as otel_context
from opentelemetry import trace as otel_trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.propagators.composite import CompositeHTTPPropagator
from opentelemetry.propagators.textmap import Setter, TextMapPropagator
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider as OTelSDKTracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import NonRecordingSpan
from opentelemetry.trace import SpanContext as OTelSpanContext
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from shared.observability.tracing import Span, SpanContext, SpanKind, SpanStatus, Tracer, TracerProvider

_OTEL_KIND_MAP: dict[SpanKind, otel_trace.SpanKind] = {
    SpanKind.INTERNAL: otel_trace.SpanKind.INTERNAL,
    SpanKind.SERVER: otel_trace.SpanKind.SERVER,
    SpanKind.CLIENT: otel_trace.SpanKind.CLIENT,
    SpanKind.PRODUCER: otel_trace.SpanKind.PRODUCER,
    SpanKind.CONSUMER: otel_trace.SpanKind.CONSUMER,
}

_OTEL_STATUS_MAP: dict[int, otel_trace.StatusCode] = {
    0: otel_trace.StatusCode.UNSET,
    1: otel_trace.StatusCode.OK,
    2: otel_trace.StatusCode.ERROR,
}


def _to_otel_kind(kind: SpanKind) -> otel_trace.SpanKind:
    return _OTEL_KIND_MAP.get(kind, otel_trace.SpanKind.INTERNAL)


def _to_otel_status_code(code: int) -> otel_trace.StatusCode:
    return _OTEL_STATUS_MAP.get(code, otel_trace.StatusCode.UNSET)


def _to_span_context(sc: SpanContext) -> OTelSpanContext | None:
    try:
        trace_id = int(sc.trace_id, 16)
        span_id = int(sc.span_id, 16)
    except ValueError:
        return None
    return OTelSpanContext(
        trace_id=trace_id,
        span_id=span_id,
        is_remote=False,
        trace_flags=otel_trace.TraceFlags(sc.trace_flags),
    )


def _from_otel_span_context(octx: OTelSpanContext) -> SpanContext:
    return SpanContext(
        trace_id=format(octx.trace_id, "032x"),
        span_id=format(octx.span_id, "016x"),
        trace_flags=octx.trace_flags,
    )


class _DictSetter(Setter[dict[str, str]]):
    def set(self, carrier: dict[str, str], key: str, value: str) -> None:
        carrier[key] = value


class OTelSpan(Span):
    def __init__(self, otel_span_instance: otel_trace.Span) -> None:
        self._span = otel_span_instance

    def set_attribute(self, key: str, value: str | bool | float | int) -> None:
        self._span.set_attribute(key, value)

    def set_status(self, status: SpanStatus | int, description: str | None = None) -> None:
        if isinstance(status, SpanStatus):
            sc = _to_otel_status_code(int(status.status_code))
            self._span.set_status(otel_trace.Status(status_code=sc, description=status.description))
        else:
            sc = _to_otel_status_code(status)
            self._span.set_status(otel_trace.Status(status_code=sc, description=description or ""))

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        self._span.add_event(name, attributes or {})

    def end(self) -> None:
        self._span.end()

    @property
    def context(self) -> SpanContext:
        octx = self._span.get_span_context()
        return _from_otel_span_context(octx)


class OTelTracer(Tracer):
    def __init__(self, otel_tracer_instance: otel_trace.Tracer) -> None:
        self._tracer = otel_tracer_instance

    def start_span(
        self,
        name: str,
        context: SpanContext | None = None,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: dict[str, Any] | None = None,
    ) -> Span:
        otel_ctx: otel_context.Context | None = None
        if context is not None:
            parent_octx = _to_span_context(context)
            if parent_octx is not None:
                otel_ctx = otel_trace.set_span_in_context(NonRecordingSpan(parent_octx))

        otel_span = self._tracer.start_span(
            name=name,
            context=otel_ctx,
            kind=_to_otel_kind(kind),
            attributes=attributes,
        )

        return OTelSpan(otel_span)


class OTelTracerProvider(TracerProvider):
    def __init__(
        self,
        service_name: str,
        endpoint: str | None = None,
    ) -> None:
        resource = Resource.create({"service.name": service_name})
        sdk_provider = OTelSDKTracerProvider(resource=resource)

        if endpoint:
            exporter = OTLPSpanExporter(endpoint=endpoint)
            span_processor = BatchSpanProcessor(exporter)
            sdk_provider.add_span_processor(span_processor)

        self._provider = sdk_provider
        self._propagator: TextMapPropagator = CompositeHTTPPropagator(
            [
                TraceContextTextMapPropagator(),
            ]
        )

        otel_trace.set_tracer_provider(sdk_provider)

    def get_tracer(self, name: str, version: str | None = None) -> Tracer:
        otel_tracer = self._provider.get_tracer(name, version or "")
        return OTelTracer(otel_tracer)

    def inject(self, context: SpanContext, headers: dict[str, str]) -> dict[str, str]:
        octx = _to_span_context(context)
        if octx is None:
            return headers
        carrier: dict[str, str] = {}
        otel_ctx = otel_trace.set_span_in_context(NonRecordingSpan(octx))
        self._propagator.inject(carrier, context=otel_ctx, setter=_DictSetter())
        headers.update(carrier)
        return headers

    def extract(self, headers: dict[str, str]) -> SpanContext | None:
        otel_ctx = self._propagator.extract(carrier=headers)
        otel_span = otel_trace.get_current_span(otel_ctx)
        octx = otel_span.get_span_context()
        if octx.trace_id == 0:
            return None
        return _from_otel_span_context(octx)

    async def force_flush(self) -> None:
        self._provider.force_flush()

    async def shutdown(self) -> None:
        self._provider.shutdown()
