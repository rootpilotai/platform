from shared.domain.graph.enums import DependencyType
from shared.domain.graph.models import DependencyEdge, DependencyGraph
from shared.domain.graph.traversal import GraphTraversal


def make_graph() -> DependencyGraph:
    g = DependencyGraph()
    g.add_edge(DependencyEdge(source="web", target="api", dependency_type=DependencyType.SYNCHRONOUS))
    g.add_edge(DependencyEdge(source="api", target="auth", dependency_type=DependencyType.SYNCHRONOUS))
    g.add_edge(DependencyEdge(source="api", target="db", dependency_type=DependencyType.DATABASE))
    g.add_edge(DependencyEdge(source="auth", target="db", dependency_type=DependencyType.DATABASE))
    g.add_edge(DependencyEdge(source="worker", target="db", dependency_type=DependencyType.DATABASE))
    return g


class TestUpstream:
    def test_upstream_of_leaf(self) -> None:
        graph = make_graph()
        t = GraphTraversal(graph)
        upstream = t.get_upstream("db")
        assert sorted(upstream) == sorted(["api", "auth", "web", "worker"])

    def test_upstream_of_root(self) -> None:
        graph = make_graph()
        t = GraphTraversal(graph)
        assert t.get_upstream("web") == []

    def test_upstream_of_middle(self) -> None:
        graph = make_graph()
        t = GraphTraversal(graph)
        upstream = t.get_upstream("auth")
        assert sorted(upstream) == sorted(["api", "web"])


class TestDownstream:
    def test_downstream_of_root(self) -> None:
        graph = make_graph()
        t = GraphTraversal(graph)
        downstream = t.get_downstream("web")
        assert sorted(downstream) == sorted(["api", "auth", "db"])

    def test_downstream_of_leaf(self) -> None:
        graph = make_graph()
        t = GraphTraversal(graph)
        assert t.get_downstream("db") == []

    def test_downstream_of_middle(self) -> None:
        graph = make_graph()
        t = GraphTraversal(graph)
        downstream = t.get_downstream("api")
        assert sorted(downstream) == sorted(["auth", "db"])


class TestFindPaths:
    def test_direct_path(self) -> None:
        graph = make_graph()
        t = GraphTraversal(graph)
        paths = t.find_paths("web", "api")
        assert paths == [["web", "api"]]

    def test_single_path(self) -> None:
        graph = make_graph()
        t = GraphTraversal(graph)
        paths = t.find_paths("web", "auth")
        assert paths == [["web", "api", "auth"]]

    def test_multiple_paths(self) -> None:
        graph = make_graph()
        t = GraphTraversal(graph)
        paths = t.find_paths("web", "db")
        assert len(paths) == 2
        assert ["web", "api", "db"] in paths
        assert ["web", "api", "auth", "db"] in paths

    def test_no_path(self) -> None:
        graph = make_graph()
        t = GraphTraversal(graph)
        paths = t.find_paths("db", "web")
        assert paths == []

    def test_max_depth_respected(self) -> None:
        graph = make_graph()
        t = GraphTraversal(graph)
        paths = t.find_paths("web", "db", max_depth=2)
        assert len(paths) == 1
        assert paths == [["web", "api", "db"]]


class TestRootAndLeaf:
    def test_root_nodes(self) -> None:
        graph = make_graph()
        t = GraphTraversal(graph)
        roots = t.get_root_nodes()
        assert sorted(roots) == sorted(["web", "worker"])

    def test_leaf_nodes(self) -> None:
        graph = make_graph()
        t = GraphTraversal(graph)
        leaves = t.get_leaf_nodes()
        assert leaves == ["db"]

    def test_impact_chain(self) -> None:
        graph = make_graph()
        t = GraphTraversal(graph)
        chain = t.get_impact_chain("api")
        assert sorted(chain) == sorted(["auth", "db"])
