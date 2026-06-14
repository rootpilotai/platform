"""Tracing setup utilities and ASGI middleware for FastAPI services."""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI
from opentelemetry import trace as otel_trace
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from infrastructure.monitoring.otel.otel_tracer_provider import (
    OTelTracerProvider,
    _from_otel_span_context,
)
from shared.config import BaseAppSettings
from shared.observability.tracing import SpanContext, SpanKind

logger = logging.getLogger(__name__)


def setup_tracing(
    app: FastAPI,
    settings: BaseAppSettings,
    endpoint: str | None = None,
) -> OTelTracerProvider:
    provider = OTelTracerProvider(
        service_name=settings.resolved_otel_service_name,
        endpoint=endpoint or settings.otel_exporter_otlp_endpoint,
    )
    app.state.tracer_provider = provider
    app.state.tracer = provider.get_tracer(
        name=settings.resolved_otel_service_name,
        version="0.1.0",
    )
    logger.info(
        "Tracing initialised",
        extra={
            "service_name": settings.resolved_otel_service_name,
            "otlp_endpoint": endpoint or settings.otel_exporter_otlp_endpoint,
        },
    )
    return provider


def get_trace_context() -> SpanContext | None:
    current_span = otel_trace.get_current_span()
    octx = current_span.get_span_context()
    if octx.trace_id == 0:
        return None
    return _from_otel_span_context(octx)


class OpenTelemetryMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        provider: OTelTracerProvider | None = getattr(
            getattr(self.app, "state", None), "tracer_provider", None
        )
        if provider is None:
            await self.app(scope, receive, send)
            return

        headers = _build_header_dict(scope.get("headers", []))
        parent_ctx = provider.extract(headers)

        tracer = provider.get_tracer("rootpilot-http")
        span = tracer.start_span(
            name=f"{scope.get('method', 'UNKNOWN')} {scope.get('path', '/')}",
            context=parent_ctx,
            kind=SpanKind.SERVER,
            attributes={
                "http.method": scope.get("method", "UNKNOWN"),
                "http.url": scope.get("path", "/"),
                "http.scheme": scope.get("scheme", "http"),
                "http.host": _get_header(headers, "host", ""),
                "http.user_agent": _get_header(headers, "user-agent", ""),
            },
        )

        async def _send_wrapper(message: Message) -> None:
            if message.get("type") == "http.response.start":
                status = message.get("status", 0)
                span.set_attribute("http.status_code", status)
                if status >= 500:
                    span.set_status(2, f"HTTP {status}")
                else:
                    span.set_status(1)
            await send(message)

        try:
            await self.app(scope, receive, _send_wrapper)
        except BaseException as exc:
            span.set_status(2, str(exc))
            span.add_event("exception", {"exception.message": str(exc)})
            raise
        finally:
            span.end()


def _build_header_dict(raw_headers: list[tuple[bytes, bytes]]) -> dict[str, str]:
    return {k.decode("utf-8", errors="replace"): v.decode("utf-8", errors="replace") for k, v in raw_headers}


def _get_header(headers: dict[str, str], key: str, default: str = "") -> str:
    return headers.get(key, headers.get(key.replace("-", "_"), default))
