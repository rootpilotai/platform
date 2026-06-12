from pathlib import Path

from pydantic import Field
import pytest

from shared.config import BaseAppSettings, load_settings


@pytest.fixture(autouse=True)
def clear_settings_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "SERVICE_NAME",
        "ENVIRONMENT",
        "DEBUG",
        "LOG_LEVEL",
        "OTEL_SERVICE_NAME",
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "EVENT_BUS_URL",
    ):
        monkeypatch.delenv(key, raising=False)


class ExampleServiceSettings(BaseAppSettings):
    service_name: str = "ingestion-service"
    event_bus_url: str = Field(default="amqp://localhost:5672")


def test_base_settings_defaults_are_typed() -> None:
    settings = BaseAppSettings()

    assert settings.service_name == "rootpilot-service"
    assert settings.environment == "local"
    assert settings.debug is False
    assert settings.log_level == "INFO"
    assert settings.resolved_otel_service_name == "rootpilot-service"


def test_load_settings_supports_service_specific_subclasses() -> None:
    settings = load_settings(
        ExampleServiceSettings,
        event_bus_url="memory://events",
    )

    assert settings.service_name == "ingestion-service"
    assert settings.event_bus_url == "memory://events"


def test_load_settings_reads_env_file(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "SERVICE_NAME=gateway-service",
                "ENVIRONMENT=test",
                "DEBUG=true",
                "LOG_LEVEL=DEBUG",
                "OTEL_SERVICE_NAME=rootpilot-gateway",
            ]
        ),
        encoding="utf-8",
    )

    settings = load_settings(BaseAppSettings, env_file=env_file)

    assert settings.service_name == "gateway-service"
    assert settings.environment == "test"
    assert settings.debug is True
    assert settings.log_level == "DEBUG"
    assert settings.resolved_otel_service_name == "rootpilot-gateway"
