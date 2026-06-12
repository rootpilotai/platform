import pytest

from shared.domain.graph.enums import DependencyType
from shared.domain.graph.models import DependencyEdge
from shared.domain.graph.store import InMemoryGraphStore
from shared.domain.graph.traversal import GraphTraversal


@pytest.fixture
async def store() -> InMemoryGraphStore:
    s = InMemoryGraphStore()
    await s.add_edge(DependencyEdge(source="web", target="api", dependency_type=DependencyType.SYNCHRONOUS))
    await s.add_edge(DependencyEdge(source="api", target="auth", dependency_type=DependencyType.SYNCHRONOUS))
    await s.add_edge(DependencyEdge(source="api", target="db", dependency_type=DependencyType.DATABASE))
    await s.add_edge(DependencyEdge(source="auth", target="db", dependency_type=DependencyType.DATABASE))
    await s.add_edge(DependencyEdge(source="worker", target="db", dependency_type=DependencyType.DATABASE))
    return s


class TestUpstream:
    async def test_upstream_of_leaf(self, store: InMemoryGraphStore) -> None:
        t = GraphTraversal(store)
        upstream = await t.get_upstream("db")
        assert sorted(upstream) == sorted(["api", "auth", "web", "worker"])

    async def test_upstream_of_root(self, store: InMemoryGraphStore) -> None:
        t = GraphTraversal(store)
        assert await t.get_upstream("web") == []

    async def test_upstream_of_middle(self, store: InMemoryGraphStore) -> None:
        t = GraphTraversal(store)
        upstream = await t.get_upstream("auth")
        assert sorted(upstream) == sorted(["api", "web"])


class TestDownstream:
    async def test_downstream_of_root(self, store: InMemoryGraphStore) -> None:
        t = GraphTraversal(store)
        downstream = await t.get_downstream("web")
        assert sorted(downstream) == sorted(["api", "auth", "db"])

    async def test_downstream_of_leaf(self, store: InMemoryGraphStore) -> None:
        t = GraphTraversal(store)
        assert await t.get_downstream("db") == []

    async def test_downstream_of_middle(self, store: InMemoryGraphStore) -> None:
        t = GraphTraversal(store)
        downstream = await t.get_downstream("api")
        assert sorted(downstream) == sorted(["auth", "db"])


class TestFindPaths:
    async def test_direct_path(self, store: InMemoryGraphStore) -> None:
        t = GraphTraversal(store)
        paths = await t.find_paths("web", "api")
        assert paths == [["web", "api"]]

    async def test_single_path(self, store: InMemoryGraphStore) -> None:
        t = GraphTraversal(store)
        paths = await t.find_paths("web", "auth")
        assert paths == [["web", "api", "auth"]]

    async def test_multiple_paths(self, store: InMemoryGraphStore) -> None:
        t = GraphTraversal(store)
        paths = await t.find_paths("web", "db")
        assert len(paths) == 2
        assert ["web", "api", "db"] in paths
        assert ["web", "api", "auth", "db"] in paths

    async def test_no_path(self, store: InMemoryGraphStore) -> None:
        t = GraphTraversal(store)
        paths = await t.find_paths("db", "web")
        assert paths == []

    async def test_max_depth_respected(self, store: InMemoryGraphStore) -> None:
        t = GraphTraversal(store)
        paths = await t.find_paths("web", "db", max_depth=2)
        assert len(paths) == 1
        assert paths == [["web", "api", "db"]]


class TestRootAndLeaf:
    async def test_root_nodes(self, store: InMemoryGraphStore) -> None:
        t = GraphTraversal(store)
        roots = await t.get_root_nodes()
        assert sorted(roots) == sorted(["web", "worker"])

    async def test_leaf_nodes(self, store: InMemoryGraphStore) -> None:
        t = GraphTraversal(store)
        leaves = await t.get_leaf_nodes()
        assert leaves == ["db"]

    async def test_impact_chain(self, store: InMemoryGraphStore) -> None:
        t = GraphTraversal(store)
        chain = await t.get_impact_chain("api")
        assert sorted(chain) == sorted(["auth", "db"])
