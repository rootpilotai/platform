"""Confidence scoring for correlation groups.

Combines composite score with diversity, coverage, and recency factors.
"""

from datetime import UTC, datetime

from shared.domain.correlation.scoring.models import ScoringResult


class ConfidenceScorer:
    """Computes a confidence score for a correlation group.

    Confidence is a weighted combination of:
      - composite_score (40%): the base scoring quality
      - diversity_factor (30%): how many distinct strategies matched
      - coverage_factor (20%): how many events in the group were matched
      - recency_factor (10%): how recent the events are
    """

    def compute(
        self,
        result: ScoringResult,
        total_events_in_group: int,
        event_timestamps: list[datetime] | None = None,
    ) -> float:
        composite = result.composite_score

        diversity = self._diversity_factor(result)
        coverage = self._coverage_factor(result, total_events_in_group)
        recency = self._recency_factor(event_timestamps)

        confidence = 0.4 * composite + 0.3 * diversity + 0.2 * coverage + 0.1 * recency
        return round(min(max(confidence, 0.0), 1.0), 4)

    @staticmethod
    def _diversity_factor(result: ScoringResult) -> float:
        """Score based on how many distinct strategies contributed.

        More strategies = higher confidence.
        0 strategies -> 0.0
        1+ strategies -> scales toward 1.0, with diminishing returns.
        """
        count = len(result.strategies_used)
        if count == 0:
            return 0.0
        return min(count / 4.0, 1.0)

    @staticmethod
    def _coverage_factor(result: ScoringResult, total_events_in_group: int) -> float:
        """Score based on what fraction of group events have match data.

        Higher coverage = higher confidence.
        """
        if total_events_in_group == 0:
            return 0.0
        matched_events: set[str] = set()
        for c in result.contributions:
            matched_events.update(c.event_ids)
        return len(matched_events) / total_events_in_group

    @staticmethod
    def _recency_factor(event_timestamps: list[datetime] | None) -> float:
        """Score based on recency of events.

        Events within the last hour = 1.0.
        Events older than 24 hours = 0.0.
        Linear decay in between.
        """
        if not event_timestamps:
            return 1.0

        now = datetime.now(UTC)
        newest = max(event_timestamps)
        age_seconds = (now - newest).total_seconds()

        if age_seconds <= 3600:  # 1 hour
            return 1.0
        if age_seconds >= 86400:  # 24 hours
            return 0.0
        return round(1.0 - (age_seconds - 3600) / (86400 - 3600), 4)
