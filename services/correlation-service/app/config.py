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
