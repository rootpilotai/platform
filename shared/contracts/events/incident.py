"""Incident event schemas for detection and lifecycle."""

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from shared.contracts.events.enums import Severity


class IncidentDetectedEvent(BaseModel):
    model_version: str = "1.0"
    incident_id: str = Field(description="Unique incident identifier.")
    severity: Severity = Field(description="Severity level of the incident.")
    service: str = Field(description="Affected service name.")
    title: str = Field(description="Short human-readable incident summary.")
    description: str = Field(default="", description="Detailed incident description.")
    source_event_ids: list[str] = Field(
        default_factory=list, description="IDs of the source telemetry events that triggered this."
    )
    detected_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When the incident was first detected (UTC).",
    )
