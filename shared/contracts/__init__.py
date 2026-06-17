"""Shared contracts, schemas, and provider-agnostic interfaces."""

import importlib

from shared.contracts.events import (
    Event,
    IncidentDetectedEvent,
    InvestigationCompletedEvent,
    InvestigationRequestedEvent,
    ServiceName,
    Severity,
    TelemetryEvent,
)
from shared.contracts.schemas import NotificationMessage

_LAZY_INTERFACES: dict[str, str] = {
    "ApiKeyStore": "shared.contracts.interfaces.api_key_store",
    "EventBus": "shared.contracts.interfaces.event_bus",
    "IncidentFilter": "shared.contracts.interfaces.incident_store",
    "IncidentSortField": "shared.contracts.interfaces.incident_store",
    "IncidentSortOrder": "shared.contracts.interfaces.incident_store",
    "IncidentStore": "shared.contracts.interfaces.incident_store",
    "InvestigationFilter": "shared.contracts.interfaces.investigation_store",
    "InvestigationStore": "shared.contracts.interfaces.investigation_store",
    "LLMMessage": "shared.contracts.interfaces.llm_provider",
    "LLMProvider": "shared.contracts.interfaces.llm_provider",
    "LLMResponse": "shared.contracts.interfaces.llm_provider",
    "LogEntry": "shared.contracts.interfaces.log_store",
    "LogFilter": "shared.contracts.interfaces.log_store",
    "LogStore": "shared.contracts.interfaces.log_store",
    "NotificationProvider": "shared.contracts.interfaces.notification_provider",
    "ObservabilityProvider": "shared.contracts.interfaces.observability",
}


def __getattr__(name: str):
    if name in _LAZY_INTERFACES:
        module = importlib.import_module(_LAZY_INTERFACES[name])
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "ApiKeyStore",
    "Event",
    "EventBus",
    "IncidentDetectedEvent",
    "IncidentFilter",
    "IncidentSortField",
    "IncidentSortOrder",
    "IncidentStore",
    "InvestigationCompletedEvent",
    "InvestigationFilter",
    "InvestigationRequestedEvent",
    "InvestigationStore",
    "LLMMessage",
    "LLMProvider",
    "LLMResponse",
    "LogEntry",
    "LogFilter",
    "LogStore",
    "NotificationMessage",
    "NotificationProvider",
    "ObservabilityProvider",
    "ServiceName",
    "Severity",
    "TelemetryEvent",
]
