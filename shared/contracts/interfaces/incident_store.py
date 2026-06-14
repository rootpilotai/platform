"""Incident store abstraction for provider-agnostic async incident persistence."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from shared.domain.incident.context.models import IncidentContext


class IncidentSortField(StrEnum):
    DETECTED_AT = "detected_at"
    SEVERITY = "severity"
    EVENT_COUNT = "event_count"
    SERVICE_COUNT = "service_count"


class IncidentSortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"


class IncidentFilter(BaseModel):
    primary_service: str | None = Field(default=None, description="Filter by primary service name.")
    severity: str | None = Field(default=None, description="Filter by severity level (e.g. CRITICAL, WARNING).")
    min_score: float | None = Field(default=None, ge=0.0, le=1.0, description="Minimum composite score threshold.")
    start_time: datetime | None = Field(default=None, description="Earliest detected_at (inclusive).")
    end_time: datetime | None = Field(default=None, description="Latest detected_at (inclusive).")
    limit: int = Field(default=100, ge=1, le=10_000, description="Maximum results to return.")
    offset: int = Field(default=0, ge=0, description="Number of results to skip for pagination.")
    sort_field: IncidentSortField = Field(default=IncidentSortField.DETECTED_AT, description="Field to sort by.")
    sort_order: IncidentSortOrder = Field(default=IncidentSortOrder.DESC, description="Sort order.")
    query_string: str | None = Field(default=None, description="Full-text search query (Lucene syntax).")


class IncidentStore(ABC):
    """Abstract store for persisting and retrieving incident contexts."""

    @abstractmethod
    async def store(self, context: IncidentContext) -> None:
        """Persist an incident context."""

    @abstractmethod
    async def get(self, incident_id: str) -> IncidentContext | None:
        """Retrieve an incident context by ID."""

    @abstractmethod
    async def search(self, filter: IncidentFilter) -> AsyncIterator[IncidentContext]:
        """Yield incident contexts matching the given filter."""

    @abstractmethod
    async def count(self, filter: IncidentFilter) -> int:
        """Return the number of incidents matching the filter."""

    @abstractmethod
    async def delete(self, incident_id: str) -> None:
        """Delete an incident context by ID."""

    @abstractmethod
    async def health(self) -> bool:
        """Return True if the store is reachable and operational."""
