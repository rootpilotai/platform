"""Extensible context builders for the incident aggregation pipeline."""

from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel, Field

from shared.domain.correlation.engine import CorrelationEngine
from shared.domain.correlation.enums import CorrelationSignal
from shared.domain.correlation.grouping import TraceGroupingService
from shared.domain.correlation.grouping.models import TraceGroup
from shared.domain.incident.context.models import (
    AggregatedCorrelationGroup,
    AggregatedTimeline,
    ImpactAnalysis,
)
from shared.domain.timeline.models import TimelineEvent
from shared.domain.timeline.services.reconstructor import TimelineReconstructor

_STRATEGY_TO_SIGNAL: dict[str, CorrelationSignal] = {
    "time_window": CorrelationSignal.TIME_PROXIMITY,
    "trace_id": CorrelationSignal.TRACE_MATCH,
    "span_relation": CorrelationSignal.SPAN_PARENT_CHILD,
    "request_id": CorrelationSignal.REQUEST_MATCH,
    "dependency": CorrelationSignal.DEPENDENCY_CHAIN,
    "error_signature": CorrelationSignal.ERROR_PATTERN,
}


class ContextBuilderState(BaseModel):
    """Mutable state carried through the builder pipeline."""

    incident_id: str = ""
    primary_service: str = ""
    severity: str = "UNKNOWN"
    title: str = ""
    detected_at: datetime | None = None
    events: list[TimelineEvent] = Field(default_factory=list)

    timeline: AggregatedTimeline | None = None
    correlation_groups: list[AggregatedCorrelationGroup] = Field(default_factory=list)
    ungrouped_events: list[str] = Field(default_factory=list)
    impacts: list[ImpactAnalysis] = Field(default_factory=list)
    trace_groups: list[TraceGroup] = Field(default_factory=list)


class ContextBuilder(ABC):
    """Extensible step in the aggregation pipeline."""

    weight: int = 0

    @abstractmethod
    async def build(self, state: ContextBuilderState) -> None:
        """Mutate *state* by adding or enriching context fields."""


class TimelineBuilder(ContextBuilder):
    """Build the incident timeline from raw events."""

    weight = 10

    def __init__(self, reconstructor: TimelineReconstructor | None = None) -> None:
        self._reconstructor = reconstructor or TimelineReconstructor()

    async def build(self, state: ContextBuilderState) -> None:
        if not state.events:
            return
        timeline = self._reconstructor.build_timeline(
            incident_id=state.incident_id,
            service=state.primary_service,
            events=state.events,
        )
        state.timeline = AggregatedTimeline(
            incident_id=timeline.incident_id,
            primary_service=timeline.service,
            windows=timeline.windows,
            total_events=timeline.event_count,
            window_count=timeline.window_count,
            start_time=timeline.start_time,
            end_time=timeline.end_time,
            duration_seconds=(
                (timeline.end_time - timeline.start_time).total_seconds()
                if timeline.start_time and timeline.end_time
                else None
            ),
        )


class CorrelationBuilder(ContextBuilder):
    """Run the correlation engine and transform results into aggregated groups."""

    weight = 20

    def __init__(self, engine: CorrelationEngine | None = None) -> None:
        self._engine = engine or CorrelationEngine()

    async def build(self, state: ContextBuilderState) -> None:
        if not state.events:
            return
        result = await self._engine.correlate(state.events)
        if not result.groups and not result.ungrouped_event_ids:
            return

        groups = [
            AggregatedCorrelationGroup(
                group_id=g.group_id,
                event_ids=g.event_ids,
                composite_score=g.composite_score,
                signals=[_STRATEGY_TO_SIGNAL[s] for s in g.strategy_scores if s in _STRATEGY_TO_SIGNAL],
                services=list(
                    {ev.service_name for ev in state.events if ev.event_id in g.event_ids and ev.service_name}
                ),
                window_start=g.window_start,
                window_end=g.window_end,
            )
            for g in result.groups
        ]
        state.correlation_groups = groups
        state.ungrouped_events = result.ungrouped_event_ids


class TraceBuilder(ContextBuilder):
    """Build trace groups from events with trace identifiers."""

    weight = 30

    def __init__(self, grouping_service: TraceGroupingService | None = None) -> None:
        self._grouping = grouping_service or TraceGroupingService()

    async def build(self, state: ContextBuilderState) -> None:
        if not any(ev.trace_id for ev in state.events):
            return
        state.trace_groups = self._grouping.build_trace_groups(state.events)


class ImpactBuilder(ContextBuilder):
    """Analyze upstream causes and downstream impact for affected services."""

    weight = 40

    def __init__(self, traversal) -> None:
        self._traversal = traversal

    async def build(self, state: ContextBuilderState) -> None:
        if state.timeline is None or not state.timeline.windows:
            return

        affected_services: set[str] = set()
        for window in state.timeline.windows:
            for ev in window.events:
                if ev.service_name:
                    affected_services.add(ev.service_name)

        if not affected_services:
            return

        impacts: list[ImpactAnalysis] = []
        for svc in sorted(affected_services):
            upstream = await self._traversal.get_upstream(svc)
            downstream = await self._traversal.get_downstream(svc)
            paths: list[list[str]] = []
            for cause in upstream:
                found = await self._traversal.find_paths(cause, svc, max_depth=10)
                paths.extend(found)
            impacts.append(
                ImpactAnalysis(
                    service=svc,
                    upstream_causes=upstream,
                    downstream_impact=downstream,
                    propagation_paths=paths,
                )
            )
        state.impacts = impacts
