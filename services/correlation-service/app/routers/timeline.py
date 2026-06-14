import logging

from fastapi import APIRouter, Depends

from app.dependencies import get_reconstructor
from app.schemas import IncidentTimelineResponse, ReconstructRequest, TimelineEventResponse, TimelineWindowResponse
from shared.domain.timeline.models import IncidentTimeline, TimelineEvent
from shared.domain.timeline.services import TimelineReconstructor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/timeline", tags=["timeline"])


@router.post("/reconstruct", response_model=IncidentTimelineResponse)
async def reconstruct_timeline(
    body: ReconstructRequest,
    reconstructor: TimelineReconstructor = Depends(get_reconstructor),
) -> IncidentTimelineResponse:
    domain_events = [_request_event_to_domain(ev) for ev in body.events]

    window_duration = body.window_duration_seconds or 300
    r = TimelineReconstructor(window_duration_seconds=window_duration)
    timeline = r.build_timeline(
        incident_id=body.incident_id,
        service=body.service,
        events=domain_events,
    )

    return _domain_timeline_to_response(timeline)


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
    )


def _domain_timeline_to_response(timeline: IncidentTimeline) -> IncidentTimelineResponse:
    return IncidentTimelineResponse(
        incident_id=timeline.incident_id,
        service=timeline.service,
        windows=[
            TimelineWindowResponse(
                window_start=w.window_start,
                window_end=w.window_end,
                events=[
                    TimelineEventResponse(
                        event_id=e.event_id,
                        category=e.category,
                        source=e.source,
                        timestamp=e.timestamp,
                        service_name=e.service_name,
                        title=e.title,
                        description=e.description,
                        trace_id=e.trace_id,
                        request_id=e.request_id,
                        severity=e.severity,
                        tags=e.tags,
                    )
                    for e in w.events
                ],
                event_count=w.event_count,
                duration_seconds=w.duration_seconds,
            )
            for w in timeline.windows
        ],
        event_count=timeline.event_count,
        window_count=timeline.window_count,
        window_duration_seconds=timeline.window_duration_seconds,
        created_at=timeline.created_at,
        start_time=timeline.start_time,
        end_time=timeline.end_time,
    )
