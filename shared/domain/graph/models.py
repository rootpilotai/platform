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

    def add_node(self, node: ServiceNode) -> None:
        self.nodes[node.service_name] = node

    def add_edge(self, edge: DependencyEdge) -> None:
        if edge.source not in self.edges:
            self.edges[edge.source] = []
        self.edges[edge.source].append(edge)
        if edge.target not in self.nodes:
            self.nodes[edge.target] = ServiceNode(service_name=edge.target)
        if edge.source not in self.nodes:
            self.nodes[edge.source] = ServiceNode(service_name=edge.source)

    def get_node(self, service_name: str) -> ServiceNode | None:
        return self.nodes.get(service_name)

    def get_outgoing(self, service_name: str) -> list[DependencyEdge]:
        return self.edges.get(service_name, [])

    def get_incoming(self, service_name: str) -> list[DependencyEdge]:
        result: list[DependencyEdge] = []
        for edges in self.edges.values():
            for edge in edges:
                if edge.target == service_name:
                    result.append(edge)
        return result

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return sum(len(edges) for edges in self.edges.values())
