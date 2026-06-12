from collections import deque

from shared.domain.graph.models import DependencyEdge, DependencyGraph


class GraphTraversal:
    def __init__(self, graph: DependencyGraph) -> None:
        self._graph = graph

    def get_upstream(self, service_name: str) -> list[str]:
        visited: set[str] = set()
        queue: deque[str] = deque()
        queue.append(service_name)

        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)
            for edge in self._graph.get_incoming(current):
                if edge.source not in visited:
                    queue.append(edge.source)

        visited.discard(service_name)
        return list(visited)

    def get_downstream(self, service_name: str) -> list[str]:
        visited: set[str] = set()
        queue: deque[str] = deque()
        queue.append(service_name)

        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)
            for edge in self._graph.get_outgoing(current):
                if edge.target not in visited:
                    queue.append(edge.target)

        visited.discard(service_name)
        return list(visited)

    def find_paths(self, source: str, target: str, max_depth: int = 10) -> list[list[str]]:
        paths: list[list[str]] = []
        self._dfs(source, target, [source], paths, max_depth)
        return paths

    def _dfs(
        self,
        current: str,
        target: str,
        path: list[str],
        paths: list[list[str]],
        max_depth: int,
    ) -> None:
        if len(path) - 1 > max_depth:
            return
        if current == target:
            paths.append(path[:])
            return
        for edge in self._graph.get_outgoing(current):
            if edge.target not in path:
                path.append(edge.target)
                self._dfs(edge.target, target, path, paths, max_depth)
                path.pop()

    def get_leaf_nodes(self) -> list[str]:
        all_targets: set[str] = set()
        for edges in self._graph.edges.values():
            for edge in edges:
                all_targets.add(edge.target)
        return [name for name in self._graph.nodes if name not in self._graph.edges]

    def get_root_nodes(self) -> list[str]:
        all_targets: set[str] = set()
        for edges in self._graph.edges.values():
            for edge in edges:
                all_targets.add(edge.target)
        return [name for name in self._graph.nodes if name not in all_targets]

    def get_impact_chain(self, service_name: str) -> list[str]:
        return self.get_downstream(service_name)
