"""Base event type for provider-agnostic messaging."""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from shared.observability.tracing.models import SpanContext


def _new_id() -> str:
    return uuid4().hex


class Event(BaseModel):
    source: str = Field(description="Name of the service or component that emitted the event.")
    topic: str = Field(description="Routing key or topic the event was published on.")
    payload: dict[str, Any] = Field(default_factory=dict, description="Arbitrary event data.")
    id: str = Field(default_factory=_new_id, description="Unique event identifier (auto-generated hex UUID).")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the event was created (UTC).",
    )
    trace_context: SpanContext | None = Field(
        default=None,
        description="Carried trace context for distributed tracing propagation.",
    )
