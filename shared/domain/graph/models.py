from pydantic import BaseModel, Field

from shared.domain.graph.enums import DependencyType, ServiceStatus


class ServiceNode(BaseModel):
    service_name: str = Field(description="Unique logical service identifier.")
    service_type: str | None = Field(default=None, description="Optional service category (e.g. api, worker, db).")
    status: ServiceStatus = Field(default=ServiceStatus.UNKNOWN, description="Current health status.")
    metadata: dict[str, str] = Field(default_factory=dict, description="Arbitrary key-value metadata.")
    tags: list[str] = Field(default_factory=list, description="Searchable tags for filtering.")


class DependencyEdge(BaseModel):
    source: str = Field(description="Upstream service this edge originates from.")
    target: str = Field(description="Downstream service this edge points to.")
    dependency_type: DependencyType = Field(default=DependencyType.SYNCHRONOUS, description="Communication pattern.")
    metadata: dict[str, str] = Field(default_factory=dict, description="Arbitrary key-value metadata.")
    weight: float = Field(default=1.0, ge=0.0, le=1.0, description="Relative impact weight for traversal ordering.")


class DependencyGraph(BaseModel):
    nodes: dict[str, ServiceNode] = Field(default_factory=dict, description="Nodes keyed by service_name.")
    edges: dict[str, list[DependencyEdge]] = Field(default_factory=dict, description="Outgoing edges keyed by source.")
