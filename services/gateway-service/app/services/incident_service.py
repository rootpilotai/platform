"""Incident service — maps domain models to response schemas."""

from app.schemas import IncidentResponse
from shared.domain.incident.context.models import IncidentContext


def map_incident_to_response(context: IncidentContext) -> IncidentResponse:
    return IncidentResponse(
        incident_id=context.incident_id,
        primary_service=context.primary_service,
        severity=context.severity,
        title=context.title,
        detected_at=context.detected_at,
        aggregated_at=context.aggregated_at,
        event_count=context.event_count,
        service_count=context.service_count,
        trace_count=context.trace_count,
        max_correlation_score=(
            max(g.composite_score for g in context.correlation_groups) if context.correlation_groups else None
        ),
        service_list=sorted({svc for g in context.correlation_groups for svc in g.services}),
    )
