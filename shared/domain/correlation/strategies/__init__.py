"""Pluggable correlation strategies for the telemetry engine."""

from shared.domain.correlation.strategies.base import CorrelationStrategy
from shared.domain.correlation.strategies.dependency import DependencyStrategy
from shared.domain.correlation.strategies.error_signature import ErrorSignatureStrategy
from shared.domain.correlation.strategies.request_id import RequestIdStrategy
from shared.domain.correlation.strategies.time_window import TimeWindowStrategy
from shared.domain.correlation.strategies.trace_id import TraceIdStrategy

__all__ = [
    "CorrelationStrategy",
    "DependencyStrategy",
    "ErrorSignatureStrategy",
    "RequestIdStrategy",
    "TimeWindowStrategy",
    "TraceIdStrategy",
]
