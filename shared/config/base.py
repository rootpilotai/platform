"""Base settings used by RootPilot services."""

from pathlib import Path
from typing import Any, Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "development", "staging", "production", "test"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class BaseAppSettings(BaseSettings):
    """Common strongly typed configuration shared by RootPilot services."""

    service_name: str = Field(
        default="rootpilot-service",
        description="Logical service name used in logs, traces, metrics, and health checks.",
    )
    environment: Environment = Field(
        default="local",
        description="Runtime environment for this service instance.",
    )
    debug: bool = Field(
        default=False,
        description="Enable development diagnostics. Do not enable in production.",
    )
    log_level: LogLevel = Field(
        default="INFO",
        description="Minimum application log level.",
    )
    otel_service_name: str | None = Field(
        default=None,
        description="Optional OpenTelemetry service name override.",
    )
    otel_exporter_otlp_endpoint: str | None = Field(
        default=None,
        description="Optional OTLP endpoint for traces and metrics.",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def resolved_otel_service_name(self) -> str:
        """Return the explicit OpenTelemetry name or fall back to the service name."""

        return self.otel_service_name or self.service_name


def load_settings[SettingsT: BaseAppSettings](
    settings_cls: type[SettingsT] = BaseAppSettings,  # type: ignore[assignment]
    *,
    env_file: str | Path | None = None,
    **overrides: Any,
) -> SettingsT:
    """Create a settings instance without blocking async request paths.

    Services can call this once during startup and inject the resulting object into
    routes, consumers, and workflows.
    """

    if env_file is not None:
        overrides["_env_file"] = env_file

    return settings_cls(**overrides)
