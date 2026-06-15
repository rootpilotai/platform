from pydantic import Field
from pydantic_settings import SettingsConfigDict

from shared.config import BaseAppSettings


class InvestigationServiceConfig(BaseAppSettings):
    model_config = SettingsConfigDict(
        env_prefix="INVESTIGATION_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    service_name: str = "ai-investigation-service"
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 4096
    event_bus_url: str = Field(
        default="amqp://rootpilot:rootpilot@localhost:5672/",
        description="Event bus connection URL.",
    )
