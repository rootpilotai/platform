"""Correlation scoring model for weighted, explainable, and confidence-aware ranking."""

from shared.domain.correlation.models import ScoreContribution
from shared.domain.correlation.scoring.confidence import ConfidenceScorer
from shared.domain.correlation.scoring.models import ScoringResult
from shared.domain.correlation.scoring.pipeline import ScoringPipeline
from shared.domain.correlation.scoring.strategies import (
    ScoringStrategy,
    WeightedProbabilisticScorer,
)

__all__ = [
    "ConfidenceScorer",
    "ScoreContribution",
    "ScoringPipeline",
    "ScoringResult",
    "ScoringStrategy",
    "WeightedProbabilisticScorer",
]
