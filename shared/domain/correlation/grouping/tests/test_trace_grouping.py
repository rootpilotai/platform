from datetime import UTC, datetime

from shared.domain.correlation.grouping import TraceGroupingService
from shared.domain.timeline.enums import TimelineEventCategory, TimelineEventSource
from shared.domain.timeline.models import TimelineEvent


def _event(
    event_id: str,
    trace_id: str | None = None,
    span_id: str | None = None,
    parent_span_id: str | None = None,
    service: str = "api",
    _ts_offset: int = 0,
) -> TimelineEvent:
    base = datetime(2026, 6, 14, 10, 0, 0, tzinfo=UTC)
    return TimelineEvent(
        event_id=event_id,
        category=TimelineEventCategory.METRIC_ANOMALY,
        source=TimelineEventSource.TELEMETRY,
        timestamp=base,
        service_name=service,
        title=f"event {event_id}",
        trace_id=trace_id,
        span_id=span_id,
        parent_span_id=parent_span_id,
    )


class TestTraceGroupingService:
    def setup_method(self) -> None:
        self.service = TraceGroupingService()

    async def test_empty_events_returns_empty(self) -> None:
        trees = self.service.build_trace_trees([])
        assert trees == []

    async def test_events_without_trace_id_are_ignored(self) -> None:
        trees = self.service.build_trace_trees([_event("a"), _event("b")])
        assert trees == []

    async def test_single_trace_single_span(self) -> None:
        trees = self.service.build_trace_trees(
            [
                _event("a", trace_id="t1", span_id="s1"),
            ]
        )
        assert len(trees) == 1
        tree = trees[0]
        assert tree.trace_id == "t1"
        assert tree.span_count == 1
        assert len(tree.root_spans) == 1
        assert tree.root_spans[0].span_id == "s1"

    async def test_parent_child_span_hierarchy(self) -> None:
        trees = self.service.build_trace_trees(
            [
                _event("a", trace_id="t1", span_id="s1"),
                _event("b", trace_id="t1", span_id="s2", parent_span_id="s1"),
                _event("c", trace_id="t1", span_id="s3", parent_span_id="s2"),
            ]
        )
        assert len(trees) == 1
        tree = trees[0]
        assert tree.span_count == 3
        assert len(tree.root_spans) == 1
        root = tree.root_spans[0]
        assert root.span_id == "s1"
        assert len(root.children) == 1
        assert root.children[0].span_id == "s2"
        assert len(root.children[0].children) == 1
        assert root.children[0].children[0].span_id == "s3"

    async def test_multiple_root_spans(self) -> None:
        trees = self.service.build_trace_trees(
            [
                _event("a", trace_id="t1", span_id="s1"),
                _event("b", trace_id="t1", span_id="s2"),
            ]
        )
        assert len(trees) == 1
        tree = trees[0]
        assert len(tree.root_spans) == 2

    async def test_multiple_traces(self) -> None:
        trees = self.service.build_trace_trees(
            [
                _event("a", trace_id="t1", span_id="s1"),
                _event("b", trace_id="t2", span_id="s2"),
            ]
        )
        assert len(trees) == 2
        trace_ids = {t.trace_id for t in trees}
        assert trace_ids == {"t1", "t2"}

    async def test_multiple_events_per_span(self) -> None:
        trees = self.service.build_trace_trees(
            [
                _event("a", trace_id="t1", span_id="s1"),
                _event("b", trace_id="t1", span_id="s1"),
            ]
        )
        assert len(trees) == 1
        tree = trees[0]
        root = tree.root_spans[0]
        assert sorted(root.event_ids) == ["a", "b"]

    async def test_depth_calculation(self) -> None:
        trees = self.service.build_trace_trees(
            [
                _event("a", trace_id="t1", span_id="s1"),
                _event("b", trace_id="t1", span_id="s2", parent_span_id="s1"),
                _event("c", trace_id="t1", span_id="s3", parent_span_id="s2"),
            ]
        )
        assert trees[0].depth == 3


class TestTraceGroup:
    def setup_method(self) -> None:
        self.service = TraceGroupingService()

    async def test_build_trace_groups(self) -> None:
        groups = self.service.build_trace_groups(
            [
                _event("a", trace_id="t1", span_id="s1", service="api"),
                _event("b", trace_id="t1", span_id="s2", service="db"),
            ]
        )
        assert len(groups) == 1
        group = groups[0]
        assert group.trace_id == "t1"
        assert sorted(group.event_ids) == ["a", "b"]
        assert sorted(group.service_names) == ["api", "db"]
        assert group.span_count == 2
        assert group.tree is not None

    async def test_trace_group_no_spans(self) -> None:
        groups = self.service.build_trace_groups(
            [
                _event("a", trace_id="t1"),
                _event("b", trace_id="t1"),
            ]
        )
        assert len(groups) == 1
        assert groups[0].span_count == 0
