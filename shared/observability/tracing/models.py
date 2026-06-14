from enum import StrEnum

from pydantic import BaseModel, Field


class SpanContext(BaseModel):
    """Serializable trace context for propagation across service boundaries."""

    trace_id: str = Field(description="32-character hex-encoded trace ID.")
    span_id: str = Field(description="16-character hex-encoded span ID.")
    trace_flags: int = Field(default=1, ge=0, le=255, description="W3C trace flags byte.")


class SpanKind(StrEnum):
    INTERNAL = "internal"
    SERVER = "server"
    CLIENT = "client"
    PRODUCER = "producer"
    CONSUMER = "consumer"


SpanStatusValue = int | str


class SpanStatus:
    """Status representation for a span."""

    UNSET: SpanStatusValue = 0
    OK: SpanStatusValue = 1
    ERROR: SpanStatusValue = 2

    def __init__(self, status_code: SpanStatusValue, description: str = "") -> None:
        self.status_code = status_code
        self.description = description
