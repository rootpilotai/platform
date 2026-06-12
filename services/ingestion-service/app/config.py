from pydantic import Field

from shared.config import BaseAppSettings


class IngestionServiceSettings(BaseAppSettings):
    service_name: str = "ingestion-service"
    host: str = Field(default="0.0.0.0", description="Bind address for the HTTP server.")
    port: int = Field(default=8000, ge=1024, le=65535, description="Bind port for the HTTP server.")
    event_bus_url: str = Field(
        default="amqp://rootpilot:rootpilot@localhost:5672/",
        description="Event bus connection URL.",
    )
    max_payload_size: int = Field(
        default=1_048_576,
        ge=1,
        le=10_485_760,
        description="Maximum telemetry payload size in bytes.",
    )
