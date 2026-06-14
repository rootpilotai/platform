import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from app.dependencies import get_engine
from app.schemas import (
    CorrelateRequest,
    CorrelateResponse,
    CorrelationGroupResponse,
    TimelineEventResponse,
)
from shared.domain.correlation.engine import CorrelationEngine
from shared.domain.timeline.models import TimelineEvent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/correlate", tags=["correlation"])


@router.post("", response_model=CorrelateResponse)
async def correlate_events(
    body: CorrelateRequest,
    engine: CorrelationEngine = Depends(get_engine),
) -> CorrelateResponse:
    domain_events = [_request_event_to_domain(ev) for ev in body.events]

    ctx = await engine.correlate(
        events=domain_events,
        min_score=body.min_score,
    )

    event_map = {ev.event_id: ev for ev in domain_events}
    group_responses = []
    for g in ctx.groups:
        group_events = [event_map[eid] for eid in g.event_ids if eid in event_map]
        trace_ids = sorted({e.trace_id for e in group_events if e.trace_id})
        request_ids = sorted({e.request_id for e in group_events if e.request_id})
        services = sorted({e.service_name for e in group_events})
        timestamps = [e.timestamp for e in group_events if e.timestamp]
        group_responses.append(
            CorrelationGroupResponse(
                group_id=g.group_id,
                event_ids=list(g.event_ids),
                composite_score=g.composite_score,
                strategy_scores=dict(g.strategy_scores),
                common_trace_ids=trace_ids,
                common_request_ids=request_ids,
                services=services,
                time_range_start=min(timestamps) if timestamps else None,
                time_range_end=max(timestamps) if timestamps else None,
            )
        )

    return CorrelateResponse(
        correlation_id=f"corr-{datetime.now(UTC).isoformat()}",
        total_events=ctx.total_events,
        groups=group_responses,
        ungrouped_event_ids=list(ctx.ungrouped_event_ids),
        strategy_counts=dict(ctx.strategy_counts),
    )


def _request_event_to_domain(ev: TimelineEventResponse) -> TimelineEvent:
    return TimelineEvent(
        event_id=ev.event_id,
        category=ev.category,
        source=ev.source,
        timestamp=ev.timestamp,
        service_name=ev.service_name,
        title=ev.title,
        description=ev.description,
        trace_id=ev.trace_id,
        request_id=ev.request_id,
        severity=ev.severity,
        tags=ev.tags,
        metadata=ev.metadata,
    )
