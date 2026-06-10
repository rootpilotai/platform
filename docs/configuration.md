# Shared Configuration

RootPilot services use a shared configuration layer in `shared.config`.

The layer is built on Pydantic Settings so services can load strongly typed
values from environment variables, local `.env` files, and future production
deployment environments without binding business logic to a provider-specific
configuration source.

## Base Settings

`BaseAppSettings` defines common fields every service can use:

* `service_name`
* `environment`
* `debug`
* `log_level`
* `otel_service_name`
* `otel_exporter_otlp_endpoint`

Environment variables are case-insensitive and `.env` files are loaded by
default from the current working directory.

## Service Settings Example

```python
from pydantic import Field

from shared.config import BaseAppSettings, load_settings


class IngestionSettings(BaseAppSettings):
    service_name: str = "ingestion-service"
    event_bus_url: str = Field(default="amqp://localhost:5672")


settings = load_settings(IngestionSettings)
```

Example `.env`:

```env
SERVICE_NAME=ingestion-service
ENVIRONMENT=local
DEBUG=true
LOG_LEVEL=DEBUG
EVENT_BUS_URL=amqp://guest:guest@localhost:5672/
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
```

Services should create settings during startup and pass the settings object into
routes, consumers, workflows, and infrastructure adapters. Avoid reading
environment variables directly in business logic.
