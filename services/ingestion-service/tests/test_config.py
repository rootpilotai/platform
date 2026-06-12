import pytest
from pydantic import Field

from app.config import IngestionServiceSettings
from shared.config import BaseAppSettings, load_settings


class TestIngestionServiceSettings:
    def test_default_service_name(self) -> None:
        settings = IngestionServiceSettings()
        assert settings.service_name == "ingestion-service"

    def test_default_host_and_port(self) -> None:
        settings = IngestionServiceSettings()
        assert settings.host == "0.0.0.0"
        assert settings.port == 8000

    def test_default_event_bus_url(self) -> None:
        settings = IngestionServiceSettings()
        assert settings.event_bus_url == "amqp://rootpilot:rootpilot@localhost:5672/"

    def test_max_payload_size_default(self) -> None:
        settings = IngestionServiceSettings()
        assert settings.max_payload_size == 1_048_576

    def test_environment_default(self) -> None:
        settings = IngestionServiceSettings()
        assert settings.environment == "local"
        assert settings.debug is False

    def test_can_be_loaded_via_factory(self) -> None:
    settings = load_settings(
        IngestionServiceSettings,
        host="127.0.0.1",
        port=9000,
    )
        assert settings.host == "127.0.0.1"
        assert settings.port == 9000
        assert settings.service_name == "ingestion-service"

    def test_is_subclass_of_base(self) -> None:
        assert issubclass(IngestionServiceSettings, BaseAppSettings)
