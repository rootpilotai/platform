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
    description: str = ""
    trace_id: str | None = None
    request_id: str | None = None
    severity: Severity | None = None
    tags: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, str] = Field(default_factory=dict, description="Arbitrary structured data.")


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


class CorrelationGroupResponse(BaseModel):
    group_id: str = Field(description="Unique correlation group identifier.")
    event_ids: list[str] = Field(description="IDs of the correlated events.")
    composite_score: float = Field(ge=0.0, le=1.0, description="Aggregate correlation confidence.")
    strategy_scores: dict[str, float] = Field(description="Per-strategy contribution scores.")
    common_trace_ids: list[str] = Field(default_factory=list, description="Trace IDs shared across the group.")
    common_request_ids: list[str] = Field(default_factory=list, description="Request IDs shared across the group.")
    services: list[str] = Field(description="Services involved in this group.")
    time_range_start: datetime | None = Field(default=None, description="Earliest event timestamp in the group.")
    time_range_end: datetime | None = Field(default=None, description="Latest event timestamp in the group.")


class CorrelateResponse(BaseModel):
    correlation_id: str = Field(description="Unique correlation result identifier.")
    total_events: int = Field(description="Number of events processed.")
    groups: list[CorrelationGroupResponse] = Field(default_factory=list, description="Detected correlation groups.")
    ungrouped_event_ids: list[str] = Field(default_factory=list, description="Events that did not join any group.")
    strategy_counts: dict[str, int] = Field(default_factory=dict, description="Number of matches produced per strategy.")


class CorrelateRequest(BaseModel):
    events: list[TimelineEventResponse] = Field(description="Timeline events to correlate.", min_length=1)
    min_score: float | None = Field(default=None, ge=0.0, le=1.0, description="Minimum composite score threshold.")
