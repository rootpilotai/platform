"""Shared enumerations for RootPilot event contracts."""

from enum import StrEnum


class Severity(StrEnum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ServiceName(StrEnum):
    INGESTION = "ingestion-service"
    CORRELATION = "correlation-service"
    INVESTIGATION = "ai-investigation-service"
    INCIDENT = "incident-service"
    GATEWAY = "gateway-service"
    NOTIFICATION = "notification-service"


class EventTopic(StrEnum):
    TELEMETRY_INGESTED = "telemetry.ingested"
    INCIDENT_DETECTED = "incident.detected"
    INVESTIGATION_REQUESTED = "investigation.requested"
    INVESTIGATION_COMPLETED = "investigation.completed"
    NOTIFICATION_DEAD_LETTER = "notification.dead-letter"
