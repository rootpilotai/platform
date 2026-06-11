"""Investigation event schema for AI-driven root cause analysis."""

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


class InvestigationRequestedEvent(BaseModel):
    model_version: str = "1.0"
    investigation_id: str = Field(description="Unique investigation identifier.")
    incident_id: str = Field(description="Incident identifier this investigation relates to.")
    context: dict[str, Any] = Field(
        default_factory=dict, description="Additional context for the investigation (logs, traces, etc.)."
    )
    depth: Literal["quick", "standard", "deep"] = Field(
        default="standard", description="Investigation depth: quick summary, standard analysis, or deep dive."
    )
    requested_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the investigation was requested (UTC).",
    )
