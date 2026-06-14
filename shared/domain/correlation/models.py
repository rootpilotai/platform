from datetime import UTC, datetime

from pydantic import BaseModel, Field

from shared.domain.correlation.enums import CorrelationSignal, CorrelationStrategyType
from shared.domain.timeline.models import TimelineEvent


class CorrelationMatch(BaseModel):
    event_id_a: str = Field(description="First correlated event ID.")
    event_id_b: str = Field(description="Second correlated event ID.")
    strategy_type: CorrelationStrategyType = Field(description="Strategy that produced this match.")
    signal: CorrelationSignal = Field(description="Specific signal detected.")
    score: float = Field(ge=0.0, le=1.0, description="Match strength from this strategy.")
    metadata: dict[str, str] = Field(default_factory=dict, description="Strategy-specific details.")


class ScoreContribution(BaseModel):
    """Explains a single strategy's contribution to a group's composite score."""

    strategy_name: str = Field(description="Strategy type name (e.g. trace_id).")
    signal: CorrelationSignal = Field(description="Specific signal detected.")
    raw_score: float = Field(ge=0.0, le=1.0, description="Original match score before weighting.")
    weighted_score: float = Field(ge=0.0, le=1.0, description="Score after applying strategy weight.")
    weight: float = Field(ge=0.0, le=1.0, description="Strategy weight used for attenuation.")
    match_count: int = Field(ge=0, description="Number of raw matches contributing under this strategy.")
    event_ids: list[str] = Field(default_factory=list, description="Event IDs involved in these matches.")


class CorrelationGroup(BaseModel):
    group_id: str = Field(description="Unique group identifier.")
    event_ids: list[str] = Field(description="Event IDs in this group.")
    strategies_used: list[CorrelationStrategyType] = Field(description="Strategies that contributed.")
    strategy_scores: dict[str, float] = Field(default_factory=dict, description="Max weighted score per strategy.")
    composite_score: float = Field(ge=0.0, le=1.0, description="Aggregate correlation score.")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence in the correlation quality.")
    contributions: list[ScoreContribution] = Field(default_factory=list, description="Per-strategy scoring breakdown.")
    window_start: datetime | None = Field(default=None, description="Earliest event timestamp.")
    window_end: datetime | None = Field(default=None, description="Latest event timestamp.")


class CorrelationResult(BaseModel):
    groups: list[CorrelationGroup] = Field(default_factory=list, description="Correlated event groups.")
    ungrouped_event_ids: list[str] = Field(default_factory=list, description="Events below correlation threshold.")
    total_events: int = Field(description="Total input event count.")
    grouped_count: int = Field(description="Events assigned to groups.")
    ungrouped_count: int = Field(description="Events not assigned to any group.")
    strategy_counts: dict[str, int] = Field(default_factory=dict, description="Matches per strategy.")
    duration_ms: float = Field(default=0.0, description="Pipeline execution time in ms.")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When the result was produced.",
    )


class CorrelationContext(BaseModel):
    events: list[TimelineEvent] = Field(description="Timeline events to correlate.")
    min_score: float = Field(default=0.2, ge=0.0, le=1.0, description="Minimum composite score threshold.")
