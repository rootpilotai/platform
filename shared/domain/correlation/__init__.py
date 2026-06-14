"""Telemetry correlation engine models, pipeline, scoring, and strategies."""

from shared.domain.correlation.engine import CorrelationEngine
from shared.domain.correlation.enums import CorrelationSignal, CorrelationStrategyType
from shared.domain.correlation.models import (
    CorrelationContext,
    CorrelationGroup,
    CorrelationMatch,
    CorrelationResult,
    ScoreContribution,
)
from shared.domain.correlation.pipeline import CorrelationPipeline
from shared.domain.correlation.scoring import (
    ConfidenceScorer,
    ScoringPipeline,
    ScoringStrategy,
    WeightedProbabilisticScorer,
)
from shared.domain.correlation.strategies import (
    CorrelationStrategy,
    DependencyStrategy,
    ErrorSignatureStrategy,
    RequestIdStrategy,
    TimeWindowStrategy,
    TraceIdStrategy,
)

__all__ = [
    "ConfidenceScorer",
    "CorrelationContext",
    "CorrelationEngine",
    "CorrelationGroup",
    "CorrelationMatch",
    "CorrelationPipeline",
    "CorrelationResult",
    "CorrelationSignal",
    "CorrelationStrategy",
    "CorrelationStrategyType",
    "DependencyStrategy",
    "ErrorSignatureStrategy",
    "RequestIdStrategy",
    "ScoreContribution",
    "ScoringPipeline",
    "ScoringStrategy",
    "TimeWindowStrategy",
    "TraceIdStrategy",
    "WeightedProbabilisticScorer",
]
