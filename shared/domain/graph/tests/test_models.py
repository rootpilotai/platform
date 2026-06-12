import pytest
from pydantic import ValidationError

from shared.domain.graph.enums import DependencyType, ServiceStatus
from shared.domain.graph.models import DependencyEdge, DependencyGraph, ServiceNode
from shared.domain.graph.store import InMemoryGraphStore


class TestServiceNode:
    async def test_minimal_node(self) -> None:
        node = ServiceNode(service_name="api-gateway")
        assert node.service_name == "api-gateway"
        assert node.status == ServiceStatus.UNKNOWN
        assert node.metadata == {}
        assert node.tags == []

    async def test_node_with_all_fields(self) -> None:
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

    async def test_round_trip_json(self) -> None:
        original = ServiceNode(service_name="cache", service_type="db", status=ServiceStatus.DEGRADED)
        restored = ServiceNode.model_validate_json(original.model_dump_json())
        assert restored == original


class TestDependencyEdge:
    async def test_minimal_edge(self) -> None:
        edge = DependencyEdge(source="api", target="auth")
        assert edge.source == "api"
        assert edge.target == "auth"
        assert edge.dependency_type == DependencyType.SYNCHRONOUS
        assert edge.weight == 1.0

    async def test_edge_with_all_fields(self) -> None:
        edge = DependencyEdge(
            source="web",
            target="db",
            dependency_type=DependencyType.DATABASE,
            metadata={"port": "5432"},
            weight=0.8,
        )
        assert edge.dependency_type == DependencyType.DATABASE
        assert edge.weight == 0.8

    async def test_weight_clamped(self) -> None:
        with pytest.raises(ValidationError):
            DependencyEdge(source="a", target="b", weight=1.5)
        with pytest.raises(ValidationError):
            DependencyEdge(source="a", target="b", weight=-0.1)

    async def test_round_trip_json(self) -> None:
        original = DependencyEdge(source="a", target="b", dependency_type=DependencyType.GRPC, weight=0.5)
        restored = DependencyEdge.model_validate_json(original.model_dump_json())
        assert restored == original


class TestDependencyGraph:
    async def test_empty_graph(self) -> None:
        graph = DependencyGraph()
        assert len(graph.nodes) == 0
        assert len(graph.edges) == 0

    async def test_json_round_trip(self) -> None:
        g = DependencyGraph(
            nodes={
                "api": ServiceNode(service_name="api"),
                "db": ServiceNode(service_name="db"),
            },
            edges={
                "api": [DependencyEdge(source="api", target="db")],
            },
        )
        restored = DependencyGraph.model_validate_json(g.model_dump_json())
        assert restored.model_dump() == g.model_dump()

    async def test_serialized_graph_can_seed_store(self) -> None:
        g = DependencyGraph(
            nodes={
                "web": ServiceNode(service_name="web"),
                "api": ServiceNode(service_name="api"),
            },
            edges={
                "web": [DependencyEdge(source="web", target="api")],
            },
        )
        store = InMemoryGraphStore(graph=g)
        assert await store.node_count() == 2
        assert await store.edge_count() == 1


class TestInMemoryGraphStore:
    async def test_empty_store(self) -> None:
        store = InMemoryGraphStore()
        assert await store.node_count() == 0
        assert await store.edge_count() == 0

    async def test_add_node(self) -> None:
        store = InMemoryGraphStore()
        await store.add_node(ServiceNode(service_name="api"))
        assert await store.node_count() == 1
        node = await store.get_node("api")
        assert node is not None
        assert node.service_name == "api"

    async def test_add_edge_creates_missing_nodes(self) -> None:
        store = InMemoryGraphStore()
        await store.add_edge(DependencyEdge(source="api", target="auth"))
        assert await store.node_count() == 2
        assert await store.get_node("api") is not None
        assert await store.get_node("auth") is not None

    async def test_get_outgoing(self) -> None:
        store = InMemoryGraphStore()
        await store.add_edge(DependencyEdge(source="api", target="auth"))
        await store.add_edge(DependencyEdge(source="api", target="db"))
        outgoing = await store.get_outgoing("api")
        assert len(outgoing) == 2

    async def test_get_incoming(self) -> None:
        store = InMemoryGraphStore()
        await store.add_edge(DependencyEdge(source="web", target="db"))
        await store.add_edge(DependencyEdge(source="api", target="db"))
        incoming = await store.get_incoming("db")
        assert len(incoming) == 2

    async def test_edge_count(self) -> None:
        store = InMemoryGraphStore()
        await store.add_edge(DependencyEdge(source="a", target="b"))
        await store.add_edge(DependencyEdge(source="b", target="c"))
        assert await store.edge_count() == 2

    async def test_get_unknown_node_returns_none(self) -> None:
        store = InMemoryGraphStore()
        assert await store.get_node("nonexistent") is None

    async def test_get_all_node_names(self) -> None:
        store = InMemoryGraphStore()
        await store.add_edge(DependencyEdge(source="a", target="b"))
        await store.add_edge(DependencyEdge(source="b", target="c"))
        names = await store.get_all_node_names()
        assert sorted(names) == sorted(["a", "b", "c"])

    async def test_get_all_edge_targets(self) -> None:
        store = InMemoryGraphStore()
        await store.add_edge(DependencyEdge(source="a", target="b"))
        await store.add_edge(DependencyEdge(source="b", target="c"))
        targets = await store.get_all_edge_targets()
        assert targets == {"b", "c"}
