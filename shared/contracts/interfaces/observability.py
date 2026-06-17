"""Observability setup abstraction for provider-agnostic tracing / metrics."""

from abc import ABC, abstractmethod

from fastapi import FastAPI


class ObservabilityProvider(ABC):
    @abstractmethod
    def setup(self, app: FastAPI) -> None:
        """Configure tracing, middleware, and metrics for a FastAPI application."""
