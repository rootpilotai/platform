from pydantic import Field

from shared.config import BaseAppSettings


class OtelAdapterSettings(BaseAppSettings):
    service_name: str = "otel-adapter-service"
    host: str = Field(default="0.0.0.0", description="Bind address for the HTTP server.")
    port: int = Field(default=8004, ge=1024, le=65535, description="Bind port for the HTTP server.")
    event_bus_url: str = Field(
        default="amqp://rootpilot:rootpilot@localhost:5672/",
        description="Event bus connection URL.",
    )
    anomaly_latency_threshold_ms: float = Field(
        default=1000.0,
        ge=0.0,
        description="Span duration above this (ms) is classified as a latency anomaly.",
    )
    otel_http_port: int = Field(
        default=4318,
        description="Standard OTLP HTTP port (documentation use).",
    )
    source_name: str = Field(
        default="otel-adapter",
        description="Source name stamped on normalized TelemetryEvents.",
    )
    drop_collector_self_monitoring: bool = Field(
        default=True,
        description="Drop telemetry from the OTEL collector itself (otelcol-contrib).",
    )
