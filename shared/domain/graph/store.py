"""Graph storage abstraction for provider-agnostic dependency graph persistence."""

from abc import ABC, abstractmethod

from shared.domain.graph.models import DependencyEdge, DependencyGraph, ServiceNode


class GraphStore(ABC):
    @abstractmethod
    async def add_node(self, node: ServiceNode) -> None: ...

    @abstractmethod
    async def add_edge(self, edge: DependencyEdge) -> None: ...

    @abstractmethod
    async def get_node(self, service_name: str) -> ServiceNode | None: ...

    @abstractmethod
    async def get_outgoing(self, service_name: str) -> list[DependencyEdge]: ...

    @abstractmethod
    async def get_incoming(self, service_name: str) -> list[DependencyEdge]: ...

    @abstractmethod
    async def get_all_node_names(self) -> list[str]: ...

    @abstractmethod
    async def get_all_edge_targets(self) -> set[str]: ...

    @abstractmethod
    async def node_count(self) -> int: ...

    @abstractmethod
    async def edge_count(self) -> int: ...


class InMemoryGraphStore(GraphStore):
    def __init__(self, graph: DependencyGraph | None = None) -> None:
        self._graph = graph if graph is not None else DependencyGraph()

    async def add_node(self, node: ServiceNode) -> None:
        self._graph.nodes[node.service_name] = node

    async def add_edge(self, edge: DependencyEdge) -> None:
        if edge.source not in self._graph.edges:
            self._graph.edges[edge.source] = []
        self._graph.edges[edge.source].append(edge)
        if edge.target not in self._graph.nodes:
            self._graph.nodes[edge.target] = ServiceNode(service_name=edge.target)
        if edge.source not in self._graph.nodes:
            self._graph.nodes[edge.source] = ServiceNode(service_name=edge.source)

    async def get_node(self, service_name: str) -> ServiceNode | None:
        return self._graph.nodes.get(service_name)

    async def get_outgoing(self, service_name: str) -> list[DependencyEdge]:
        return self._graph.edges.get(service_name, [])

    async def get_incoming(self, service_name: str) -> list[DependencyEdge]:
        result: list[DependencyEdge] = []
        for edges in self._graph.edges.values():
            for edge in edges:
                if edge.target == service_name:
                    result.append(edge)
        return result

    async def get_all_node_names(self) -> list[str]:
        return list(self._graph.nodes.keys())

    async def get_all_edge_targets(self) -> set[str]:
        targets: set[str] = set()
        for edges in self._graph.edges.values():
            for edge in edges:
                targets.add(edge.target)
        return targets

    async def node_count(self) -> int:
        return len(self._graph.nodes)

    async def edge_count(self) -> int:
        return sum(len(edges) for edges in self._graph.edges.values())
