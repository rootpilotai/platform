"""Gateway service configuration and settings."""

from pydantic import Field

from shared.config import BaseAppSettings


class GatewayServiceSettings(BaseAppSettings):
    service_name: str = "gateway-service"
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8005, ge=1024, le=65535)
    elasticsearch_hosts: str = Field(default="http://localhost:9200", description="Elasticsearch server URL(s).")
    elasticsearch_username: str | None = Field(default=None, description="Elasticsearch basic auth username.")
    elasticsearch_password: str | None = Field(default=None, description="Elasticsearch basic auth password.")
    api_keys: str = Field(default="", description="Comma-separated list of valid API keys.")
