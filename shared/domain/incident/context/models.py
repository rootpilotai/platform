from datetime import datetime

from pydantic import BaseModel, Field

from shared.domain.correlation.enums import CorrelationSignal
from shared.domain.correlation.grouping.models import TraceGroup
from shared.domain.timeline.models import TimelineWindow


class AggregatedCorrelationGroup(BaseModel):
    """A correlation group enriched with service and trace metadata."""

    group_id: str = Field(description="Correlation group identifier.")
    event_ids: list[str] = Field(description="Event IDs belonging to this group.")
    composite_score: float = Field(ge=0.0, le=1.0, description="Aggregate correlation score.")
    signals: list[CorrelationSignal] = Field(
        default_factory=list, description="Detection signals that formed this group."
    )
    services: list[str] = Field(default_factory=list, description="Unique service names in this group.")
    trace_id: str | None = Field(default=None, description="Shared trace identifier, if any.")
    span_count: int = Field(default=0, description="Number of distinct spans across group events.")
    window_start: datetime | None = Field(default=None, description="Earliest event timestamp.")
    window_end: datetime | None = Field(default=None, description="Latest event timestamp.")


class AggregatedTimeline(BaseModel):
    """An incident timeline with computed duration and event density."""

    incident_id: str = Field(description="Incident identifier.")
    primary_service: str = Field(description="Primary affected service.")
    windows: list[TimelineWindow] = Field(default_factory=list, description="Time-windowed event buckets.")
    total_events: int = Field(default=0, description="Total event count.")
    window_count: int = Field(default=0, description="Number of time windows.")
    start_time: datetime | None = Field(default=None, description="Earliest event across all windows.")
    end_time: datetime | None = Field(default=None, description="Latest event across all windows.")
    duration_seconds: float | None = Field(default=None, description="Total incident duration in seconds.")


class ImpactAnalysis(BaseModel):
    """Upstream causes and downstream blast radius for an affected service."""

    service: str = Field(description="The affected service.")
    upstream_causes: list[str] = Field(
        default_factory=list, description="Services that could be root causes (ancestors)."
    )
    downstream_impact: list[str] = Field(
        default_factory=list, description="Services affected by this failure (descendants)."
    )
    propagation_paths: list[list[str]] = Field(
        default_factory=list, description="Explicit dependency propagation paths."
    )


class IncidentContext(BaseModel):
    """Complete, AI-ready incident context assembled by the aggregation pipeline."""

    incident_id: str = Field(description="Incident identifier.")
    primary_service: str = Field(description="Service where the incident was detected.")
    severity: str = Field(default="UNKNOWN", description="Incident severity level.")
    title: str = Field(default="", description="Short human-readable incident summary.")
    detected_at: datetime = Field(description="When the incident was detected (UTC).")

    timeline: AggregatedTimeline | None = Field(default=None, description="Structured timeline of events.")
    correlation_groups: list[AggregatedCorrelationGroup] = Field(
        default_factory=list, description="Correlated event groups."
    )
    ungrouped_events: list[str] = Field(
        default_factory=list, description="Event IDs that fell below correlation threshold."
    )

    impacts: list[ImpactAnalysis] = Field(default_factory=list, description="Impact analysis per affected service.")
    trace_groups: list[TraceGroup] = Field(default_factory=list, description="Span trees found in the event set.")

    event_count: int = Field(default=0, description="Total input event count.")
    service_count: int = Field(default=0, description="Unique services involved.")
    trace_count: int = Field(default=0, description="Unique traces found.")
    aggregated_at: datetime = Field(
        default_factory=lambda: datetime.now(), description="When this context was assembled."
    )
