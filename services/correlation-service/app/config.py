from pydantic import Field

from shared.config import BaseAppSettings


class CorrelationServiceSettings(BaseAppSettings):
    service_name: str = "correlation-service"
    host: str = Field(default="0.0.0.0", description="Bind address for the HTTP server.")
    port: int = Field(default=8001, ge=1024, le=65535, description="Bind port for the HTTP server.")
    event_bus_url: str = Field(
        default="amqp://rootpilot:rootpilot@localhost:5672/",
        description="Event bus connection URL.",
    )
    timeline_window_duration: int = Field(
        default=300,
        ge=1,
        description="Default timeline window duration in seconds.",
    )
    correlation_window_seconds: int = Field(
        default=300,
        ge=1,
        description="Time window in seconds for telemetry event accumulation before correlation.",
    )
    correlation_min_events: int = Field(
        default=3,
        ge=1,
        description="Minimum accumulated events before correlation is triggered.",
    )
    correlation_min_score: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description="Minimum composite score threshold for correlation groups.",
    )
    correlation_incident_severity: str = Field(
        default="ERROR",
        description="Default severity assigned to incidents created by the correlation pipeline.",
    )
    elasticsearch_hosts: str = Field(
        default="http://localhost:9200",
        description="Elasticsearch server URL(s).",
    )
    elasticsearch_username: str | None = Field(
        default=None,
        description="Elasticsearch basic auth username.",
    )
    elasticsearch_password: str | None = Field(
        default=None,
        description="Elasticsearch basic auth password.",
    )
