"""Service for building trace trees from timeline events."""

from collections import defaultdict

from shared.domain.correlation.grouping.models import SpanNode, TraceGroup, TraceTree
from shared.domain.timeline.models import TimelineEvent


class TraceGroupingService:
    """Groups timeline events by trace ID and reconstructs span hierarchies."""

    def build_trace_trees(self, events: list[TimelineEvent]) -> list[TraceTree]:
        """Build a list of TraceTree objects from a set of timeline events."""
        by_trace: dict[str, list[TimelineEvent]] = defaultdict(list)
        for ev in events:
            if ev.trace_id:
                by_trace[ev.trace_id].append(ev)

        return [self._build_single_tree(trace_id, evs) for trace_id, evs in by_trace.items()]

    def build_trace_groups(self, events: list[TimelineEvent]) -> list[TraceGroup]:
        """Build TraceGroup objects (lighter weight than full trees when spans aren't needed)."""
        by_trace: dict[str, list[TimelineEvent]] = defaultdict(list)
        for ev in events:
            if ev.trace_id:
                by_trace[ev.trace_id].append(ev)

        groups: list[TraceGroup] = []
        for trace_id, evs in by_trace.items():
            span_ids = {ev.span_id for ev in evs if ev.span_id}
            services = list({ev.service_name for ev in evs})
            tree = self._build_single_tree(trace_id, evs)
            groups.append(
                TraceGroup(
                    trace_id=trace_id,
                    event_ids=[ev.event_id for ev in evs],
                    tree=tree,
                    service_names=services,
                    span_count=len(span_ids),
                )
            )
        return groups

    def _build_single_tree(self, trace_id: str, events: list[TimelineEvent]) -> TraceTree:
        """Reconstruct a TraceTree from events belonging to a single trace."""
        span_map: dict[str, SpanNode] = {}
        event_map: dict[str, list[str]] = defaultdict(list)
        services: set[str] = set()
        all_event_ids: list[str] = []

        for ev in events:
            all_event_ids.append(ev.event_id)
            if ev.service_name:
                services.add(ev.service_name)
            if ev.span_id:
                event_map[ev.span_id].append(ev.event_id)
            else:
                continue

        for ev in events:
            if not ev.span_id:
                continue
            if ev.span_id not in span_map:
                span_map[ev.span_id] = SpanNode(
                    span_id=ev.span_id,
                    trace_id=trace_id,
                    parent_span_id=ev.parent_span_id,
                    service_name=ev.service_name or "",
                    event_ids=event_map.get(ev.span_id, []),
                )

        children_map: dict[str, list[SpanNode]] = defaultdict(list)
        for span in span_map.values():
            if span.parent_span_id and span.parent_span_id in span_map:
                children_map[span.parent_span_id].append(span)

        for span in span_map.values():
            span.children = children_map.get(span.span_id, [])

        root_spans = [s for s in span_map.values() if s.parent_span_id is None or s.parent_span_id not in span_map]

        return TraceTree(
            trace_id=trace_id,
            root_spans=root_spans,
            all_spans=list(span_map.values()),
            event_ids=all_event_ids,
            service_names=sorted(services),
        )
