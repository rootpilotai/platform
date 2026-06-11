"""Telemetry event schema for ingestion and metric forwarding."""

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class TelemetryEvent(BaseModel):
    model_version: str = "1.0"
    metric: str = Field(description="Metric name (e.g. cpu.usage, request.latency).")
    value: float = Field(description="Numeric value of the metric.")
    unit: str | None = Field(default=None, description="Unit of measurement (e.g. ms, %, count).")
    tags: dict[str, str] = Field(default_factory=dict, description="Dimension key-value pairs.")
    source: str = Field(description="Service or component that produced the telemetry.")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the measurement was taken (UTC).",
    )
