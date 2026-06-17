"""Telemetry event schema for ingestion and metric forwarding."""

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from shared.contracts.events.enums import Severity


class TelemetryEvent(BaseModel):
    model_version: str = "1.0"
    metric: str = Field(description="Metric name (e.g. cpu.usage, request.latency).")
    value: float = Field(description="Numeric value of the metric.")
    unit: str | None = Field(default=None, description="Unit of measurement (e.g. ms, %, count).")
    tags: dict[str, str] = Field(default_factory=dict, description="Dimension key-value pairs.")
    source: str = Field(description="Service or component that produced the telemetry.")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When the measurement was taken (UTC).",
    )
    trace_id: str | None = Field(default=None, description="Distributed trace identifier.")
    span_id: str | None = Field(default=None, description="Span identifier within the trace (16 hex chars).")
    parent_span_id: str | None = Field(default=None, description="Parent span identifier, if this span is a child.")
    request_id: str | None = Field(default=None, description="Correlated request identifier.")
    severity: Severity | None = Field(default=None, description="Severity level if applicable.")
