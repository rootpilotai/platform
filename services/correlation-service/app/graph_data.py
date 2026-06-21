"""Service dependency topology for the OpenTelemetry Astronomy Shop demo.

This graph is used by the ImpactBuilder to detect silent dependencies —
services that are known downstream dependencies but produced zero events,
helping the AI investigation identify unreachable services as root causes.
"""

from shared.domain.graph.enums import DependencyType
from shared.domain.graph.models import DependencyEdge, ServiceNode
from shared.domain.graph.store import InMemoryGraphStore


def _edge(source: str, target: str) -> DependencyEdge:
    return DependencyEdge(source=source, target=target, dependency_type=DependencyType.SYNCHRONOUS, weight=1.0)


ASTRONOMY_SHOP_SERVICES: list[ServiceNode] = [
    ServiceNode(service_name="frontend-proxy", service_type="proxy", tags=["proxy"]),
    ServiceNode(service_name="frontend", service_type="web", tags=["web"]),
    ServiceNode(service_name="checkout", service_type="api", tags=["api"]),
    ServiceNode(service_name="cart", service_type="api", tags=["api"]),
    ServiceNode(service_name="product-catalog", service_type="api", tags=["api"]),
    ServiceNode(service_name="payment", service_type="api", tags=["api"]),
    ServiceNode(service_name="shipping", service_type="api", tags=["api"]),
    ServiceNode(service_name="email", service_type="worker", tags=["worker"]),
    ServiceNode(service_name="ad", service_type="api", tags=["api"]),
    ServiceNode(service_name="image-provider", service_type="api", tags=["api"]),
    ServiceNode(service_name="quote", service_type="api", tags=["api"]),
    ServiceNode(service_name="telemetry-docs", service_type="web", tags=["web"]),
    ServiceNode(service_name="product-reviews", service_type="api", tags=["api"]),
    ServiceNode(service_name="recommendation", service_type="api", tags=["api"]),
]

ASTRONOMY_SHOP_EDGES: list[DependencyEdge] = [
    _edge("frontend-proxy", "frontend"),
    _edge("frontend-proxy", "product-catalog"),
    _edge("frontend-proxy", "cart"),
    _edge("frontend-proxy", "checkout"),
    _edge("frontend-proxy", "payment"),
    _edge("frontend-proxy", "shipping"),
    _edge("frontend-proxy", "ad"),
    _edge("frontend-proxy", "image-provider"),
    _edge("checkout", "payment"),
    _edge("checkout", "shipping"),
    _edge("checkout", "cart"),
    _edge("checkout", "email"),
    _edge("cart", "product-catalog"),
    _edge("cart", "quote"),
    _edge("frontend", "product-catalog"),
    _edge("frontend", "cart"),
    _edge("frontend", "checkout"),
    _edge("frontend", "payment"),
    _edge("frontend", "shipping"),
    _edge("frontend", "ad"),
    _edge("frontend", "image-provider"),
    _edge("frontend", "product-reviews"),
    _edge("frontend", "recommendation"),
    _edge("product-reviews", "product-catalog"),
    _edge("recommendation", "product-catalog"),
    _edge("frontend-proxy", "telemetry-docs"),
]


def build_astronomy_shop_graph() -> InMemoryGraphStore:
    store = InMemoryGraphStore()
    for node in ASTRONOMY_SHOP_SERVICES:
        store._graph.nodes[node.service_name] = node
    for edge in ASTRONOMY_SHOP_EDGES:
        if edge.source not in store._graph.edges:
            store._graph.edges[edge.source] = []
        store._graph.edges[edge.source].append(edge)
        if edge.target not in store._graph.nodes:
            store._graph.nodes[edge.target] = ServiceNode(service_name=edge.target)
    return store
