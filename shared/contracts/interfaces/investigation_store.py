"""Investigation store abstraction for provider-agnostic async investigation persistence."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from datetime import datetime

from pydantic import BaseModel, Field

from shared.domain.investigation.models import InvestigationResult


class InvestigationSortField:
    GENERATED_AT = "generated_at"
    CONFIDENCE = "overall_confidence"
    DURATION_MS = "duration_ms"


class InvestigationFilter(BaseModel):
    incident_id: str | None = Field(default=None, description="Filter by incident ID.")
    start_time: datetime | None = Field(default=None, description="Earliest generated_at (inclusive).")
    end_time: datetime | None = Field(default=None, description="Latest generated_at (inclusive).")
    min_confidence: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Minimum overall confidence threshold."
    )
    limit: int = Field(default=20, ge=1, le=10_000, description="Maximum results to return.")
    offset: int = Field(default=0, ge=0, description="Number of results to skip for pagination.")
    sort_field: str = Field(default=InvestigationSortField.GENERATED_AT, description="Field to sort by.")
    sort_order: str = Field(default="desc", description="Sort order (asc or desc).")


class InvestigationStore(ABC):
    """Abstract store for persisting and retrieving investigation results."""

    @abstractmethod
    async def store(self, investigation_id: str, result: InvestigationResult) -> None:
        """Persist an investigation result."""

    @abstractmethod
    async def get(self, investigation_id: str) -> InvestigationResult | None:
        """Retrieve an investigation result by ID."""

    @abstractmethod
    async def get_by_incident(self, incident_id: str) -> InvestigationResult | None:
        """Retrieve the latest investigation for a given incident."""

    @abstractmethod
    def search(self, filter: InvestigationFilter) -> AsyncIterator[InvestigationResult]:
        """Yield investigation results matching the given filter."""

    @abstractmethod
    async def count(self, filter: InvestigationFilter) -> int:
        """Return the number of investigations matching the filter."""

    @abstractmethod
    async def latest(self) -> InvestigationResult | None:
        """Return the most recent investigation result across all incidents."""

    @abstractmethod
    async def health(self) -> bool:
        """Return True if the store is reachable and operational."""
