from datetime import datetime

from pydantic import BaseModel, Field

from shared.contracts.events.enums import Severity
from shared.domain.timeline.enums import TimelineEventCategory, TimelineEventSource


class TimelineEventResponse(BaseModel):
    event_id: str
    category: TimelineEventCategory
    source: TimelineEventSource
    timestamp: datetime
    service_name: str
    title: str
    description: str
    trace_id: str | None
    request_id: str | None
    severity: Severity | None
    tags: dict[str, str]


class TimelineWindowResponse(BaseModel):
    window_start: datetime
    window_end: datetime
    events: list[TimelineEventResponse]
    event_count: int
    duration_seconds: float


class IncidentTimelineResponse(BaseModel):
    incident_id: str
    service: str
    windows: list[TimelineWindowResponse]
    event_count: int
    window_count: int
    window_duration_seconds: int
    created_at: datetime
    start_time: datetime | None
    end_time: datetime | None


class ReconstructRequest(BaseModel):
    incident_id: str = Field(description="Unique incident identifier.")
    service: str = Field(description="Primary affected service.")
    events: list[TimelineEventResponse] = Field(description="Timeline events to reconstruct.")
    window_duration_seconds: int | None = Field(default=None, description="Optional window duration override.")
