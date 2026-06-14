"""Tests for the Elasticsearch IncidentStore adapter."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from infrastructure.elasticsearch.elasticsearch_incident_store import (
    ElasticsearchIncidentStore,
    IncidentElasticsearchConfig,
    _build_query_body,
)
from infrastructure.elasticsearch.incident_index_strategy import (
    INDEX_PREFIX,
    build_context_doc,
    default_ilm_policy,
    default_index_template,
    incident_index_name,
)
from shared.contracts.interfaces.incident_store import (
    IncidentFilter,
    IncidentSortField,
    IncidentSortOrder,
)
from shared.domain.correlation.enums import CorrelationSignal
from shared.domain.incident.context.models import (
    AggregatedCorrelationGroup,
    AggregatedTimeline,
    ImpactAnalysis,
    IncidentContext,
)


@pytest.fixture
def config() -> IncidentElasticsearchConfig:
    return IncidentElasticsearchConfig(hosts="http://localhost:9200")


@pytest.fixture
def context() -> IncidentContext:
    ts = datetime(2026, 6, 14, 12, 0, 0, tzinfo=UTC)
    return IncidentContext(
        incident_id="inc-1",
        primary_service="api",
        severity="CRITICAL",
        title="High error rate on api",
        detected_at=ts,
        event_count=10,
        service_count=2,
        trace_count=1,
        correlation_groups=[
            AggregatedCorrelationGroup(
                group_id="g-1",
                event_ids=["e1", "e2"],
                composite_score=0.85,
                signals=[CorrelationSignal.TRACE_MATCH],
                services=["api", "db"],
            ),
        ],
        ungrouped_events=["e3"],
        impacts=[
            ImpactAnalysis(
                service="db",
                upstream_causes=["api"],
                downstream_impact=["cache"],
            ),
        ],
        aggregated_at=ts,
    )


class TestIndexNaming:
    def test_index_name_format(self) -> None:
        dt = datetime(2026, 6, 14, 12, 0, 0, tzinfo=UTC)
        name = incident_index_name(dt)
        assert name == "rp-inc-2026.06.14"

    def test_index_name_defaults_to_utc_now(self) -> None:
        name = incident_index_name()
        assert name.startswith("rp-inc-")

    def test_index_name_short_prefix(self) -> None:
        assert INDEX_PREFIX == "rp-inc"


class TestDefaultTemplates:
    def test_default_index_template_structure(self) -> None:
        tmpl = default_index_template()
        assert tmpl["index_patterns"] == ["rp-inc-*"]
        assert tmpl["priority"] == 100
        properties = tmpl["template"]["mappings"]["properties"]
        assert "incident_id" in properties
        assert "primary_service" in properties
        assert "severity" in properties
        assert "detected_at" in properties
        assert "correlation_groups" in properties

    def test_default_ilm_policy_has_all_phases(self) -> None:
        policy = default_ilm_policy()
        phases = policy["policy"]["phases"]
        assert "hot" in phases
        assert "warm" in phases
        assert "cold" in phases
        assert "delete" in phases


class TestBuildContextDoc:
    def test_build_doc_structure(self, context: IncidentContext) -> None:
        doc = build_context_doc(context)
        assert doc["incident_id"] == "inc-1"
        assert doc["primary_service"] == "api"
        assert doc["severity"] == "CRITICAL"
        assert doc["event_count"] == 10
        assert doc["max_correlation_score"] == 0.85
        assert doc["service_list"] == ["api", "db"]
        assert len(doc["correlation_groups"]) == 1
        assert doc["correlation_groups"][0]["group_id"] == "g-1"

    def test_build_doc_no_correlation_groups(self) -> None:
        ts = datetime(2026, 6, 14, tzinfo=UTC)
        ctx = IncidentContext(incident_id="inc-2", primary_service="api", detected_at=ts)
        doc = build_context_doc(ctx)
        assert doc["max_correlation_score"] is None
        assert doc["service_list"] == []

    def test_build_doc_includes_timeline(self) -> None:
        ts = datetime(2026, 6, 14, tzinfo=UTC)
        ctx = IncidentContext(
            incident_id="inc-3",
            primary_service="db",
            detected_at=ts,
            timeline=AggregatedTimeline(
                incident_id="inc-3",
                primary_service="db",
                total_events=5,
                window_count=2,
            ),
        )
        doc = build_context_doc(ctx)
        assert doc["timeline"] is not None
        assert doc["timeline"]["incident_id"] == "inc-3"
        assert doc["timeline"]["total_events"] == 5


class TestBuildQueryBody:
    def test_empty_filter_uses_match_all(self) -> None:
        f = IncidentFilter()
        body = _build_query_body(f)
        assert body["query"] == {"match_all": {}}
        assert body["size"] == 100
        assert body["from"] == 0

    def test_filter_by_primary_service(self) -> None:
        f = IncidentFilter(primary_service="api")
        body = _build_query_body(f)
        assert body["query"]["bool"]["must"] == [{"term": {"primary_service": "api"}}]

    def test_filter_by_severity(self) -> None:
        f = IncidentFilter(severity="CRITICAL")
        body = _build_query_body(f)
        assert body["query"]["bool"]["must"] == [{"term": {"severity": "CRITICAL"}}]

    def test_filter_by_min_score(self) -> None:
        f = IncidentFilter(min_score=0.5)
        body = _build_query_body(f)
        assert body["query"]["bool"]["must"] == [{"range": {"max_correlation_score": {"gte": 0.5}}}]

    def test_filter_by_time_range(self) -> None:
        start = datetime(2026, 6, 14, tzinfo=UTC)
        end = datetime(2026, 6, 15, tzinfo=UTC)
        f = IncidentFilter(start_time=start, end_time=end)
        body = _build_query_body(f)
        time_range = body["query"]["bool"]["must"][0]["range"]["detected_at"]
        assert time_range["gte"] == "2026-06-14T00:00:00+00:00"
        assert time_range["lte"] == "2026-06-15T00:00:00+00:00"

    def test_filter_custom_sort(self) -> None:
        f = IncidentFilter(sort_field=IncidentSortField.EVENT_COUNT, sort_order=IncidentSortOrder.ASC)
        body = _build_query_body(f)
        assert body["sort"] == [{"event_count": {"order": "asc"}}]

    def test_filter_with_offset_and_limit(self) -> None:
        f = IncidentFilter(limit=25, offset=50)
        body = _build_query_body(f)
        assert body["size"] == 25
        assert body["from"] == 50

    def test_filter_query_string(self) -> None:
        f = IncidentFilter(query_string="error AND api")
        body = _build_query_body(f)
        assert {"query_string": {"query": "error AND api"}} in body["query"]["bool"]["must"]

    def test_filter_multiple_conditions(self) -> None:
        f = IncidentFilter(
            primary_service="api",
            severity="CRITICAL",
            min_score=0.7,
            query_string="timeout",
        )
        body = _build_query_body(f)
        must = body["query"]["bool"]["must"]
        assert len(must) == 4


class TestIncidentElasticsearchConfig:
    def test_default_hosts(self) -> None:
        cfg = IncidentElasticsearchConfig()
        assert cfg.hosts == "http://localhost:9200"
        assert cfg.username is None
        assert cfg.password is None

    def test_with_auth(self) -> None:
        cfg = IncidentElasticsearchConfig(
            hosts="https://es-cluster:9200",
            username="admin",
            password="secret",
        )
        assert cfg.username == "admin"
        assert cfg.password == "secret"

    def test_default_index_prefix(self) -> None:
        cfg = IncidentElasticsearchConfig()
        assert cfg.index_prefix == "rp-inc"


class TestElasticsearchIncidentStore:
    async def test_start_without_auth(self, config: IncidentElasticsearchConfig) -> None:
        store = ElasticsearchIncidentStore(config=config)
        mock_client = AsyncMock()

        with (
            patch(
                "infrastructure.elasticsearch.elasticsearch_incident_store.AsyncElasticsearch",
                return_value=mock_client,
            ) as mock_es,
            patch.object(store, "_bootstrap", AsyncMock()),
        ):
            await store.start()

        assert store._client is mock_client
        mock_es.assert_called_once_with(
            hosts=["http://localhost:9200"],
            timeout=30,
        )

    async def test_start_with_auth(self) -> None:
        cfg = IncidentElasticsearchConfig(
            hosts="https://es-cluster:9200",
            username="admin",
            password="secret",
        )
        store = ElasticsearchIncidentStore(config=cfg)
        mock_client = AsyncMock()

        with (
            patch(
                "infrastructure.elasticsearch.elasticsearch_incident_store.AsyncElasticsearch",
                return_value=mock_client,
            ) as mock_es,
            patch.object(store, "_bootstrap", AsyncMock()),
        ):
            await store.start()

        mock_es.assert_called_once_with(
            hosts=["https://es-cluster:9200"],
            timeout=30,
            basic_auth=("admin", "secret"),
        )

    async def test_start_is_idempotent(self, config: IncidentElasticsearchConfig) -> None:
        store = ElasticsearchIncidentStore(config=config)
        mock_client = AsyncMock()

        with (
            patch(
                "infrastructure.elasticsearch.elasticsearch_incident_store.AsyncElasticsearch",
                return_value=mock_client,
            ),
            patch.object(store, "_bootstrap", AsyncMock()),
        ):
            await store.start()
            await store.start()

    async def test_close_cleans_up(self, config: IncidentElasticsearchConfig) -> None:
        store = ElasticsearchIncidentStore(config=config)
        mock_client = AsyncMock()
        store._client = mock_client
        store._bootstrap_done = True

        await store.close()

        assert store._client is None
        assert store._bootstrap_done is False
        mock_client.close.assert_awaited_once()

    async def test_close_skips_if_not_started(self, config: IncidentElasticsearchConfig) -> None:
        store = ElasticsearchIncidentStore(config=config)
        await store.close()

    async def test_store_indexes_document(self, config: IncidentElasticsearchConfig, context: IncidentContext) -> None:
        store = ElasticsearchIncidentStore(config=config)
        mock_client = AsyncMock()
        store._client = mock_client

        await store.store(context)

        mock_client.index.assert_awaited_once()
        call_args = mock_client.index.await_args
        assert call_args is not None
        assert call_args.kwargs["index"] == "rp-inc-2026.06.14"
        assert call_args.kwargs["id"] == "inc-1"
        assert call_args.kwargs["document"]["incident_id"] == "inc-1"

    async def test_get_returns_context(self, config: IncidentElasticsearchConfig) -> None:
        store = ElasticsearchIncidentStore(config=config)
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(
            return_value={
                "_source": {
                    "incident_id": "inc-1",
                    "primary_service": "api",
                    "severity": "CRITICAL",
                    "title": "High error rate on api",
                    "detected_at": "2026-06-14T12:00:00+00:00",
                    "aggregated_at": "2026-06-14T12:00:00+00:00",
                    "event_count": 10,
                    "service_count": 2,
                    "trace_count": 1,
                    "correlation_groups": [],
                    "ungrouped_events": [],
                    "impacts": [],
                    "trace_groups": [],
                },
            },
        )
        store._client = mock_client

        result = await store.get("inc-1")

        assert result is not None
        assert result.incident_id == "inc-1"
        assert result.severity == "CRITICAL"

    async def test_get_returns_none_on_miss(self, config: IncidentElasticsearchConfig) -> None:
        store = ElasticsearchIncidentStore(config=config)
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("not found"))
        store._client = mock_client

        result = await store.get("inc-missing")
        assert result is None

    async def test_search_returns_contexts(self, config: IncidentElasticsearchConfig) -> None:
        store = ElasticsearchIncidentStore(config=config)
        mock_client = AsyncMock()
        mock_client.search = AsyncMock(
            return_value={
                "hits": {
                    "hits": [
                        {
                            "_source": {
                                "incident_id": "inc-1",
                                "primary_service": "api",
                                "severity": "CRITICAL",
                                "title": "API down",
                                "detected_at": "2026-06-14T12:00:00+00:00",
                                "aggregated_at": "2026-06-14T12:00:00+00:00",
                                "event_count": 10,
                                "service_count": 2,
                                "trace_count": 1,
                                "correlation_groups": [],
                                "ungrouped_events": [],
                                "impacts": [],
                                "trace_groups": [],
                            },
                        },
                    ],
                },
            },
        )
        store._client = mock_client

        flt = IncidentFilter(severity="CRITICAL")
        results = [c async for c in store.search(flt)]

        assert len(results) == 1
        assert results[0].incident_id == "inc-1"
        assert results[0].severity == "CRITICAL"

    async def test_search_empty_results(self, config: IncidentElasticsearchConfig) -> None:
        store = ElasticsearchIncidentStore(config=config)
        mock_client = AsyncMock()
        mock_client.search = AsyncMock(return_value={"hits": {"hits": []}})
        store._client = mock_client

        results = [c async for c in store.search(IncidentFilter())]
        assert results == []

    async def test_count_returns_count(self, config: IncidentElasticsearchConfig) -> None:
        store = ElasticsearchIncidentStore(config=config)
        mock_client = AsyncMock()
        mock_client.count = AsyncMock(return_value={"count": 5})
        store._client = mock_client

        count = await store.count(IncidentFilter(primary_service="api"))
        assert count == 5

    async def test_delete_calls_delete(self, config: IncidentElasticsearchConfig) -> None:
        store = ElasticsearchIncidentStore(config=config)
        mock_client = AsyncMock()
        store._client = mock_client

        await store.delete("inc-1")

        mock_client.delete.assert_awaited_once_with(
            index="rp-inc-*",
            id="inc-1",
        )

    async def test_delete_swallows_exception(self, config: IncidentElasticsearchConfig) -> None:
        store = ElasticsearchIncidentStore(config=config)
        mock_client = AsyncMock()
        mock_client.delete = AsyncMock(side_effect=Exception("not found"))
        store._client = mock_client

        await store.delete("inc-missing")

    async def test_health_returns_true_when_connected(self, config: IncidentElasticsearchConfig) -> None:
        store = ElasticsearchIncidentStore(config=config)
        mock_client = AsyncMock()
        mock_client.ping = AsyncMock(return_value=True)
        store._client = mock_client

        assert await store.health() is True

    async def test_health_returns_false_when_no_client(self, config: IncidentElasticsearchConfig) -> None:
        store = ElasticsearchIncidentStore(config=config)
        assert await store.health() is False

    async def test_health_returns_false_on_ping_failure(self, config: IncidentElasticsearchConfig) -> None:
        store = ElasticsearchIncidentStore(config=config)
        mock_client = AsyncMock()
        mock_client.ping = AsyncMock(side_effect=Exception("connection failed"))
        store._client = mock_client

        assert await store.health() is False

    async def test_bootstrap_creates_ilm_and_template(self, config: IncidentElasticsearchConfig) -> None:
        store = ElasticsearchIncidentStore(config=config)
        mock_client = AsyncMock()
        mock_client.ilm.get_lifecycle = AsyncMock(return_value=False)
        mock_client.ilm.put_lifecycle = AsyncMock()
        mock_client.indices.exists_index_template = AsyncMock(return_value=False)
        mock_client.indices.put_index_template = AsyncMock()
        store._client = mock_client

        await store._bootstrap()

        mock_client.ilm.put_lifecycle.assert_awaited_once()
        mock_client.indices.put_index_template.assert_awaited_once()

    async def test_bootstrap_skips_if_exists(self, config: IncidentElasticsearchConfig) -> None:
        store = ElasticsearchIncidentStore(config=config)
        mock_client = AsyncMock()
        mock_client.ilm.get_lifecycle = AsyncMock(return_value=True)
        mock_client.ilm.put_lifecycle = AsyncMock()
        mock_client.indices.exists_index_template = AsyncMock(return_value=True)
        mock_client.indices.put_index_template = AsyncMock()
        store._client = mock_client

        await store._bootstrap()

        mock_client.ilm.put_lifecycle.assert_not_awaited()
        mock_client.indices.put_index_template.assert_not_awaited()

    async def test_store_raises_if_not_started(
        self, config: IncidentElasticsearchConfig, context: IncidentContext
    ) -> None:
        store = ElasticsearchIncidentStore(config=config)
        with pytest.raises(AssertionError, match="not started"):
            await store.store(context)

    async def test_search_raises_if_not_started(self, config: IncidentElasticsearchConfig) -> None:
        store = ElasticsearchIncidentStore(config=config)
        flt = IncidentFilter()
        with pytest.raises(AssertionError, match="not started"):
            async for _ in store.search(flt):
                pass
