from pydantic import BaseModel, Field

from shared.domain.timeline.models import TimelineEvent


class SpanNode(BaseModel):
    """A span node in a trace tree, with parent-child relationships."""

    span_id: str = Field(description="Span identifier (16 hex chars).")
    trace_id: str = Field(description="Trace identifier (32 hex chars).")
    parent_span_id: str | None = Field(default=None, description="Parent span ID, if this is a child span.")
    service_name: str = Field(default="", description="Service that produced this span.")
    event_ids: list[str] = Field(default_factory=list, description="TimelineEvent IDs mapped to this span.")
    children: list["SpanNode"] = Field(default_factory=list, description="Child spans.")

    @property
    def is_root(self) -> bool:
        return self.parent_span_id is None


class TraceTree(BaseModel):
    """A reconstructed trace tree from a set of timeline events."""

    trace_id: str = Field(description="Trace identifier (32 hex chars).")
    root_spans: list[SpanNode] = Field(default_factory=list, description="Root spans (no parent).")
    all_spans: list[SpanNode] = Field(default_factory=list, description="Flat list of all spans.")
    event_ids: list[str] = Field(default_factory=list, description="All event IDs belonging to this trace.")
    service_names: list[str] = Field(default_factory=list, description="Unique services involved.")

    @property
    def span_count(self) -> int:
        return len(self.all_spans)

    @property
    def depth(self) -> int:
        if not self.root_spans:
            return 0
        return max(_max_depth(r) for r in self.root_spans)


class TraceGroup(BaseModel):
    """A group of events sharing the same trace, with optional span relationship metadata."""

    trace_id: str = Field(description="Trace identifier.")
    event_ids: list[str] = Field(description="Event IDs in this trace group.")
    tree: TraceTree | None = Field(default=None, description="Reconstructed span tree, if available.")
    service_names: list[str] = Field(default_factory=list, description="Services involved.")
    span_count: int = Field(default=0, description="Number of distinct spans.")


def _max_depth(node: SpanNode) -> int:
    if not node.children:
        return 1
    return 1 + max(_max_depth(c) for c in node.children)
