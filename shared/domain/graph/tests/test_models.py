import pytest
from pydantic import ValidationError

from shared.domain.graph.enums import DependencyType, ServiceStatus
from shared.domain.graph.models import DependencyEdge, DependencyGraph, ServiceNode


class TestServiceNode:
    def test_minimal_node(self) -> None:
        node = ServiceNode(service_name="api-gateway")
        assert node.service_name == "api-gateway"
        assert node.status == ServiceStatus.UNKNOWN
        assert node.metadata == {}
        assert node.tags == []

    def test_node_with_all_fields(self) -> None:
        node = ServiceNode(
            service_name="user-service",
            service_type="api",
            status=ServiceStatus.HEALTHY,
            metadata={"version": "2.1.0"},
            tags=["critical", "auth"],
        )
        assert node.service_name == "user-service"
        assert node.service_type == "api"
        assert node.status == ServiceStatus.HEALTHY
        assert node.metadata["version"] == "2.1.0"

    def test_round_trip_json(self) -> None:
        original = ServiceNode(service_name="cache", service_type="db", status=ServiceStatus.DEGRADED)
        restored = ServiceNode.model_validate_json(original.model_dump_json())
        assert restored == original


class TestDependencyEdge:
    def test_minimal_edge(self) -> None:
        edge = DependencyEdge(source="api", target="auth")
        assert edge.source == "api"
        assert edge.target == "auth"
        assert edge.dependency_type == DependencyType.SYNCHRONOUS
        assert edge.weight == 1.0

    def test_edge_with_all_fields(self) -> None:
        edge = DependencyEdge(
            source="web",
            target="db",
            dependency_type=DependencyType.DATABASE,
            metadata={"port": "5432"},
            weight=0.8,
        )
        assert edge.dependency_type == DependencyType.DATABASE
        assert edge.weight == 0.8

    def test_weight_clamped(self) -> None:
        with pytest.raises(ValidationError):
            DependencyEdge(source="a", target="b", weight=1.5)
        with pytest.raises(ValidationError):
            DependencyEdge(source="a", target="b", weight=-0.1)

    def test_round_trip_json(self) -> None:
        original = DependencyEdge(source="a", target="b", dependency_type=DependencyType.GRPC, weight=0.5)
        restored = DependencyEdge.model_validate_json(original.model_dump_json())
        assert restored == original


class TestDependencyGraph:
    def test_empty_graph(self) -> None:
        graph = DependencyGraph()
        assert graph.node_count == 0
        assert graph.edge_count == 0

    def test_add_node(self) -> None:
        graph = DependencyGraph()
        graph.add_node(ServiceNode(service_name="api"))
        assert graph.node_count == 1
        assert graph.get_node("api") is not None

    def test_add_edge_creates_missing_nodes(self) -> None:
        graph = DependencyGraph()
        graph.add_edge(DependencyEdge(source="api", target="auth"))
        assert graph.node_count == 2
        assert graph.get_node("api") is not None
        assert graph.get_node("auth") is not None

    def test_get_outgoing(self) -> None:
        graph = DependencyGraph()
        graph.add_edge(DependencyEdge(source="api", target="auth"))
        graph.add_edge(DependencyEdge(source="api", target="db"))
        outgoing = graph.get_outgoing("api")
        assert len(outgoing) == 2

    def test_get_incoming(self) -> None:
        graph = DependencyGraph()
        graph.add_edge(DependencyEdge(source="web", target="db"))
        graph.add_edge(DependencyEdge(source="api", target="db"))
        incoming = graph.get_incoming("db")
        assert len(incoming) == 2

    def test_edge_count(self) -> None:
        graph = DependencyGraph()
        graph.add_edge(DependencyEdge(source="a", target="b"))
        graph.add_edge(DependencyEdge(source="b", target="c"))
        assert graph.edge_count == 2

    def test_round_trip_json(self) -> None:
        graph = DependencyGraph()
        graph.add_edge(DependencyEdge(source="web", target="api", weight=0.5))
        graph.add_edge(DependencyEdge(source="api", target="db", weight=0.8))
        restored = DependencyGraph.model_validate_json(graph.model_dump_json())
        assert restored.node_count == 3
        assert restored.edge_count == 2

    def test_get_unknown_node_returns_none(self) -> None:
        graph = DependencyGraph()
        assert graph.get_node("nonexistent") is None
