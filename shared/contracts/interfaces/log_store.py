"""Log store abstraction for provider-agnostic async telemetry storage."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class LogEntry(BaseModel):
    timestamp: datetime = Field(description="When the log was written (UTC).")
    service: str = Field(description="Logical service name that emitted the log.")
    level: str = Field(description="Log severity level (e.g. INFO, ERROR).")
    message: str = Field(description="Human-readable log message.")
    trace_id: str | None = Field(default=None, description="OpenTelemetry trace ID.")
    span_id: str | None = Field(default=None, description="OpenTelemetry span ID.")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Arbitrary structured context.")


class SortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"


class LogFilter(BaseModel):
    service: str | None = Field(default=None, description="Filter by service name.")
    level: str | None = Field(default=None, description="Filter by severity level.")
    trace_id: str | None = Field(default=None, description="Filter by trace ID.")
    start_time: datetime | None = Field(default=None, description="Earliest log timestamp (inclusive).")
    end_time: datetime | None = Field(default=None, description="Latest log timestamp (inclusive).")
    limit: int = Field(default=100, ge=1, le=10_000, description="Maximum results to return.")
    offset: int = Field(default=0, ge=0, description="Number of results to skip for pagination.")
    sort_order: SortOrder = Field(default=SortOrder.DESC, description="Sort order by timestamp.")
    query_string: str | None = Field(default=None, description="Full-text search query (Lucene syntax).")


class LogStore(ABC):
    @abstractmethod
    async def write(self, entry: LogEntry) -> None: ...

    @abstractmethod
    async def write_batch(self, entries: list[LogEntry]) -> None:
        """Write multiple log entries in a single batch operation."""

    @abstractmethod
    async def query(self, filter: LogFilter) -> AsyncIterator[LogEntry]: ...

    @abstractmethod
    async def count(self, filter: LogFilter) -> int:
        """Return the number of entries matching the filter."""

    @abstractmethod
    async def health(self) -> bool: ...
