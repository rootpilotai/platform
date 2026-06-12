from datetime import datetime, timezone

from pydantic import BaseModel, Field

from shared.contracts.events.enums import Severity
from shared.domain.timeline.enums import TimelineEventCategory, TimelineEventSource


class TimelineEvent(BaseModel):
    event_id: str = Field(description="Unique event identifier.")
    category: TimelineEventCategory = Field(description="Type of event in the timeline.")
    source: TimelineEventSource = Field(description="Origin of this event.")
    timestamp: datetime = Field(description="When the event occurred (UTC).")
    service_name: str = Field(description="Affected service.")
    title: str = Field(description="Short human-readable event summary.")
    description: str = Field(default="", description="Detailed event description.")
    trace_id: str | None = Field(default=None, description="Correlated trace identifier.")
    request_id: str | None = Field(default=None, description="Correlated request identifier.")
    severity: Severity | None = Field(default=None, description="Severity level if applicable.")
    tags: dict[str, str] = Field(default_factory=dict, description="Dimension key-value pairs.")
    metadata: dict[str, str] = Field(default_factory=dict, description="Arbitrary structured data.")


class TimelineWindow(BaseModel):
    window_start: datetime = Field(description="Start of the time window (UTC).")
    window_end: datetime = Field(description="End of the time window (UTC).")
    events: list[TimelineEvent] = Field(default_factory=list, description="Events in this window, sorted chronologically.")

    @property
    def duration_seconds(self) -> float:
        return (self.window_end - self.window_start).total_seconds()

    @property
    def event_count(self) -> int:
        return len(self.events)


class IncidentTimeline(BaseModel):
    incident_id: str = Field(description="Unique incident identifier.")
    service: str = Field(description="Primary affected service.")
    windows: list[TimelineWindow] = Field(default_factory=list, description="Time-windowed event groups.")
    window_duration_seconds: int = Field(default=300, ge=1, description="Size of each time window in seconds.")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the timeline was built (UTC).",
    )

    @property
    def events(self) -> list[TimelineEvent]:
        flattened: list[TimelineEvent] = []
        for window in self.windows:
            flattened.extend(window.events)
        return flattened

    @property
    def event_count(self) -> int:
        return sum(w.event_count for w in self.windows)

    @property
    def window_count(self) -> int:
        return len(self.windows)

    @property
    def start_time(self) -> datetime | None:
        return self.windows[0].window_start if self.windows else None

    @property
    def end_time(self) -> datetime | None:
        return self.windows[-1].window_end if self.windows else None
