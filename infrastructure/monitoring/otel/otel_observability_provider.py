"""Concrete OpenTelemetry-based ObservabilityProvider."""

import logging

from fastapi import FastAPI

from infrastructure.monitoring.otel import OpenTelemetryMiddleware, setup_tracing
from shared.config import BaseAppSettings
from shared.contracts.interfaces.observability import ObservabilityProvider

logger = logging.getLogger(__name__)


class OTelObservabilityProvider(ObservabilityProvider):
    def __init__(self, settings: BaseAppSettings) -> None:
        self._settings = settings

    def setup(self, app: FastAPI) -> None:
        setup_tracing(app, self._settings)
        app.add_middleware(OpenTelemetryMiddleware)
        logger.info("OpenTelemetry observability configured", extra={"service": self._settings.service_name})
