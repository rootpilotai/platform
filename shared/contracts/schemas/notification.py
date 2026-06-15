"""Notification message schemas for provider-agnostic delivery."""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class NotificationMessage(BaseModel):
    topic: str = Field(description="Event topic that triggered this notification.")
    title: str = Field(description="Short notification title.")
    body: str = Field(description="Notification body text.")
    fields: dict[str, str] = Field(default_factory=dict, description="Key-value fields for structured display.")
    severity: str = Field(default="info", description="Notification severity level.")
    source: str = Field(description="Source service that generated the notification.")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata for provider-specific formatting."
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When the notification was created (UTC).",
    )
