from abc import ABC, abstractmethod
from typing import Any

from shared.observability.tracing.models import SpanContext, SpanKind, SpanStatus


class Span(ABC):
    """Represents a single unit of work within a distributed trace."""

    @abstractmethod
    def set_attribute(self, key: str, value: str | bool | float | int) -> None:
        ...

    @abstractmethod
    def set_status(self, status: SpanStatus | int, description: str | None = None) -> None:
        ...

    @abstractmethod
    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        ...

    @abstractmethod
    def end(self) -> None:
        ...

    @property
    @abstractmethod
    def context(self) -> SpanContext:
        ...


class Tracer(ABC):
    """Creates spans and manages trace context."""

    @abstractmethod
    def start_span(
        self,
        name: str,
        context: SpanContext | None = None,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: dict[str, Any] | None = None,
    ) -> Span:
        ...


class TracerProvider(ABC):
    """Provider-agnostic entry point for distributed tracing."""

    @abstractmethod
    def get_tracer(self, name: str, version: str | None = None) -> Tracer:
        ...

    @abstractmethod
    def inject(self, context: SpanContext, headers: dict[str, str]) -> dict[str, str]:
        ...

    @abstractmethod
    def extract(self, headers: dict[str, str]) -> SpanContext | None:
        ...

    @abstractmethod
    async def force_flush(self) -> None:
        ...

    @abstractmethod
    async def shutdown(self) -> None:
        ...
