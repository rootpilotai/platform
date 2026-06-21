"""IncidentContextAggregator — the orchestrator for the aggregation pipeline."""

from datetime import UTC, datetime

from shared.domain.incident.context.builders import ContextBuilder, ContextBuilderState
from shared.domain.incident.context.models import IncidentContext
from shared.domain.timeline.models import TimelineEvent


class IncidentContextAggregator:
    """Aggregate telemetry events into a full investigation-ready incident context."""

    def __init__(self, builders: list[ContextBuilder] | None = None) -> None:
        self._builders = sorted(builders or [], key=lambda b: b.weight)

    async def aggregate(
        self,
        incident_id: str,
        primary_service: str,
        events: list[TimelineEvent],
        severity: str = "UNKNOWN",
        title: str = "",
        detected_at: datetime | None = None,
        reachable_services: set[str] | None = None,
    ) -> IncidentContext:
        state = ContextBuilderState(
            incident_id=incident_id,
            primary_service=primary_service,
            severity=severity,
            title=title,
            detected_at=detected_at,
            events=events,
            reachable_services=sorted(reachable_services or []),
        )

        for builder in self._builders:
            await builder.build(state)

        return IncidentContext(
            incident_id=incident_id,
            primary_service=primary_service,
            severity=severity,
            title=title,
            detected_at=detected_at or datetime.now(UTC),
            timeline=state.timeline,
            correlation_groups=state.correlation_groups,
            ungrouped_events=state.ungrouped_events,
            impacts=state.impacts,
            trace_groups=state.trace_groups,
            reachable_services=state.reachable_services,
            event_count=len(events),
            service_count=len({ev.service_name for ev in events if ev.service_name}),
            trace_count=len({ev.trace_id for ev in events if ev.trace_id}),
            aggregated_at=datetime.now(UTC),
        )
