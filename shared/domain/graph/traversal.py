from collections import deque

from shared.domain.graph.store import GraphStore


class GraphTraversal:
    def __init__(self, store: GraphStore) -> None:
        self._store = store

    async def get_upstream(self, service_name: str) -> list[str]:
        visited: set[str] = set()
        queue: deque[str] = deque()
        queue.append(service_name)

        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)
            for edge in await self._store.get_incoming(current):
                if edge.source not in visited:
                    queue.append(edge.source)

        visited.discard(service_name)
        return list(visited)

    async def get_downstream(self, service_name: str) -> list[str]:
        visited: set[str] = set()
        queue: deque[str] = deque()
        queue.append(service_name)

        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)
            for edge in await self._store.get_outgoing(current):
                if edge.target not in visited:
                    queue.append(edge.target)

        visited.discard(service_name)
        return list(visited)

    async def find_paths(self, source: str, target: str, max_depth: int = 10) -> list[list[str]]:
        paths: list[list[str]] = []
        await self._dfs(source, target, [source], paths, max_depth)
        return paths

    async def _dfs(
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
        for edge in await self._store.get_outgoing(current):
            if edge.target not in path:
                path.append(edge.target)
                await self._dfs(edge.target, target, path, paths, max_depth)
                path.pop()

    async def get_leaf_nodes(self) -> list[str]:
        all_nodes = await self._store.get_all_node_names()
        leaves: list[str] = []
        for name in all_nodes:
            outgoing = await self._store.get_outgoing(name)
            if not outgoing:
                leaves.append(name)
        return leaves

    async def get_root_nodes(self) -> list[str]:
        all_targets = await self._store.get_all_edge_targets()
        all_nodes = await self._store.get_all_node_names()
        return [name for name in all_nodes if name not in all_targets]

    async def get_impact_chain(self, service_name: str) -> list[str]:
        return await self.get_downstream(service_name)
