"""Scoring intermediate models for explainable correlation scoring."""

from pydantic import BaseModel, Field

from shared.domain.correlation.enums import CorrelationStrategyType
from shared.domain.correlation.models import ScoreContribution


class ScoringResult(BaseModel):
    """The computed scoring output for a single correlation group."""

    composite_score: float = Field(ge=0.0, le=1.0, description="Aggregate weighted correlation score.")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in the correlation quality.")
    contributions: list[ScoreContribution] = Field(default_factory=list, description="Per-strategy breakdown.")
    strategy_scores: dict[str, float] = Field(default_factory=dict, description="Max weighted score per strategy.")
    strategies_used: list[CorrelationStrategyType] = Field(
        default_factory=list, description="Strategies that contributed."
    )
