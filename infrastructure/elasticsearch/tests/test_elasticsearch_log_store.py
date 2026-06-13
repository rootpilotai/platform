"""Tests for the Elasticsearch LogStore adapter."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from infrastructure.elasticsearch.elasticsearch_log_store import (
    ElasticsearchConfig,
    ElasticsearchLogStore,
    _build_es_doc,
    _build_query_body,
    _default_ilm_policy,
    _default_index_template,
    _index_name,
)
from shared.contracts.interfaces.log_store import LogEntry, LogFilter, SortOrder


@pytest.fixture
def config() -> ElasticsearchConfig:
    return ElasticsearchConfig(hosts="http://localhost:9200")


@pytest.fixture
def entry() -> LogEntry:
    return LogEntry(
        timestamp=datetime(2026, 6, 13, 12, 0, 0, tzinfo=timezone.utc),
        service="ingestion-service",
        level="ERROR",
        message="Connection refused",
        trace_id="abc123",
        span_id="span456",
        metadata={"retry_count": 3, "endpoint": "/api/v1/ingest"},
    )


class TestIndexNaming:
    def test_index_name_format(self) -> None:
        dt = datetime(2026, 6, 13, 12, 0, 0, tzinfo=timezone.utc)
        name = _index_name(dt)
        assert name == "rp-tl-2026.06.13"

    def test_index_name_defaults_to_utc_now(self) -> None:
        name = _index_name()
        assert name.startswith("rp-tl-")

    def test_index_name_pads_single_digit_month(self) -> None:
        dt = datetime(2026, 1, 5, tzinfo=timezone.utc)
        assert _index_name(dt) == "rp-tl-2026.01.05"

    def test_index_name_pads_single_digit_day(self) -> None:
        dt = datetime(2026, 12, 1, tzinfo=timezone.utc)
        assert _index_name(dt) == "rp-tl-2026.12.01"


class TestBuildEsDoc:
    def test_build_doc_structure(self, entry: LogEntry) -> None:
        doc = _build_es_doc(entry)
        assert doc["@timestamp"] == "2026-06-13T12:00:00+00:00"
        assert doc["service"] == "ingestion-service"
        assert doc["level"] == "ERROR"
        assert doc["message"] == "Connection refused"
        assert doc["trace_id"] == "abc123"
        assert doc["span_id"] == "span456"
        assert doc["metadata"] == {"retry_count": 3, "endpoint": "/api/v1/ingest"}
        assert "event_id" in doc

    def test_build_doc_without_trace_span(self) -> None:
        entry = LogEntry(
            timestamp=datetime(2026, 6, 13, tzinfo=timezone.utc),
            service="test",
            level="INFO",
            message="hello",
        )
        doc = _build_es_doc(entry)
        assert doc["trace_id"] is None
        assert doc["span_id"] is None


class TestDefaultTemplates:
    def test_default_index_template_structure(self) -> None:
        tmpl = _default_index_template()
        assert tmpl["index_patterns"] == ["rp-tl-*"]
        assert "template" in tmpl
        assert "settings" in tmpl["template"]
        assert "mappings" in tmpl["template"]
        assert tmpl["priority"] == 100

    def test_default_ilm_policy_has_all_phases(self) -> None:
        policy = _default_ilm_policy()
        phases = policy["policy"]["phases"]
        assert "hot" in phases
        assert "warm" in phases
        assert "cold" in phases
        assert "delete" in phases
        assert phases["hot"]["actions"]["rollover"]["max_age"] == "1d"

    def test_ilm_delete_phase_age(self) -> None:
        policy = _default_ilm_policy()
        assert policy["policy"]["phases"]["delete"]["min_age"] == "90d"


class TestBuildQueryBody:
    def test_empty_filter_uses_match_all(self) -> None:
        f = LogFilter()
        body = _build_query_body(f)
        assert body["query"] == {"match_all": {}}
        assert body["size"] == 100
        assert body["from"] == 0
        assert body["sort"] == [{"@timestamp": {"order": "desc"}}]

    def test_filter_by_service(self) -> None:
        f = LogFilter(service="ingestion-service")
        body = _build_query_body(f)
        assert body["query"]["bool"]["must"] == [{"term": {"service": "ingestion-service"}}]

    def test_filter_by_level(self) -> None:
        f = LogFilter(level="ERROR")
        body = _build_query_body(f)
        assert body["query"]["bool"]["must"] == [{"term": {"level": "ERROR"}}]

    def test_filter_by_trace_id(self) -> None:
        f = LogFilter(trace_id="abc123")
        body = _build_query_body(f)
        assert body["query"]["bool"]["must"] == [{"term": {"trace_id": "abc123"}}]

    def test_filter_by_time_range(self) -> None:
        start = datetime(2026, 6, 13, tzinfo=timezone.utc)
        end = datetime(2026, 6, 14, tzinfo=timezone.utc)
        f = LogFilter(start_time=start, end_time=end)
        body = _build_query_body(f)
        time_range = body["query"]["bool"]["must"][0]["range"]["@timestamp"]
        assert time_range["gte"] == "2026-06-13T00:00:00+00:00"
        assert time_range["lte"] == "2026-06-14T00:00:00+00:00"

    def test_filter_ascending_sort(self) -> None:
        f = LogFilter(sort_order=SortOrder.ASC)
        body = _build_query_body(f)
        assert body["sort"] == [{"@timestamp": {"order": "asc"}}]

    def test_filter_with_offset_and_limit(self) -> None:
        f = LogFilter(limit=50, offset=200)
        body = _build_query_body(f)
        assert body["size"] == 50
        assert body["from"] == 200

    def test_filter_query_string(self) -> None:
        f = LogFilter(query_string="connection AND refused")
        body = _build_query_body(f)
        assert {"query_string": {"query": "connection AND refused"}} in body["query"]["bool"]["must"]

    def test_filter_multiple_conditions(self) -> None:
        f = LogFilter(
            service="ingestion-service",
            level="ERROR",
            trace_id="abc",
            query_string="timeout",
        )
        body = _build_query_body(f)
        must = body["query"]["bool"]["must"]
        assert len(must) == 4
        assert {"term": {"service": "ingestion-service"}} in must
        assert {"term": {"level": "ERROR"}} in must
        assert {"term": {"trace_id": "abc"}} in must
        assert {"query_string": {"query": "timeout"}} in must


class TestElasticsearchConfig:
    def test_default_hosts(self) -> None:
        cfg = ElasticsearchConfig()
        assert cfg.hosts == "http://localhost:9200"

    def test_default_index_prefix(self) -> None:
        cfg = ElasticsearchConfig()
        assert cfg.index_prefix == "rp-tl"

    def test_custom_hosts(self) -> None:
        cfg = ElasticsearchConfig(hosts="https://es-cluster:9200")
        assert cfg.hosts == "https://es-cluster:9200"


class TestElasticsearchLogStore:
    async def test_start_connects_and_bootstraps(self, config: ElasticsearchConfig) -> None:
        store = ElasticsearchLogStore(config=config)

        mock_client = AsyncMock()
        mock_client.ping = AsyncMock(return_value=True)

        with (
            patch(
                "infrastructure.elasticsearch.elasticsearch_log_store.AsyncElasticsearch",
                return_value=mock_client,
            ),
            patch.object(store, "_bootstrap", AsyncMock()) as mock_bootstrap,
        ):
            await store.start()

        assert store._client is mock_client
        mock_bootstrap.assert_awaited_once()

    async def test_start_is_idempotent(self, config: ElasticsearchConfig) -> None:
        store = ElasticsearchLogStore(config=config)

        mock_client = AsyncMock()
        with (
            patch(
                "infrastructure.elasticsearch.elasticsearch_log_store.AsyncElasticsearch",
                return_value=mock_client,
            ),
            patch.object(store, "_bootstrap", AsyncMock()),
        ):
            await store.start()
            await store.start()

    async def test_close_cleans_up(self, config: ElasticsearchConfig) -> None:
        store = ElasticsearchLogStore(config=config)
        mock_client = AsyncMock()
        store._client = mock_client
        store._bootstrap_done = True

        await store.close()

        assert store._client is None
        assert store._bootstrap_done is False
        mock_client.close.assert_awaited_once()

    async def test_close_skips_if_not_started(self, config: ElasticsearchConfig) -> None:
        store = ElasticsearchLogStore(config=config)
        await store.close()

    async def test_write_indexes_document(self, config: ElasticsearchConfig, entry: LogEntry) -> None:
        store = ElasticsearchLogStore(config=config)
        mock_client = AsyncMock()
        store._client = mock_client

        await store.write(entry)

        mock_client.index.assert_awaited_once()
        call_args = mock_client.index.await_args
        assert call_args is not None
        assert call_args.kwargs["index"] == "rp-tl-2026.06.13"
        assert call_args.kwargs["document"]["service"] == "ingestion-service"
        assert call_args.kwargs["document"]["level"] == "ERROR"

    async def test_write_batch_calls_async_bulk(self, config: ElasticsearchConfig, entry: LogEntry) -> None:
        store = ElasticsearchLogStore(config=config)
        mock_client = AsyncMock()
        store._client = mock_client

        entries = [entry, entry]

        with patch(
            "infrastructure.elasticsearch.elasticsearch_log_store.async_bulk",
            AsyncMock(return_value=(2, [])),
        ) as mock_bulk:
            await store.write_batch(entries)
            mock_bulk.assert_awaited_once()

    async def test_query_searches_and_yields_entries(self, config: ElasticsearchConfig) -> None:
        store = ElasticsearchLogStore(config=config)
        mock_client = AsyncMock()
        mock_client.search = AsyncMock(
            return_value={
                "hits": {
                    "hits": [
                        {
                            "_source": {
                                "@timestamp": "2026-06-13T12:00:00+00:00",
                                "service": "ingestion-service",
                                "level": "ERROR",
                                "message": "Connection refused",
                                "trace_id": "abc123",
                                "span_id": "span456",
                                "metadata": {"retry_count": 3},
                            },
                        },
                    ],
                },
            },
        )
        store._client = mock_client

        flt = LogFilter(trace_id="abc123")
        results = [e async for e in store.query(flt)]

        assert len(results) == 1
        assert results[0].service == "ingestion-service"
        assert results[0].level == "ERROR"
        assert results[0].trace_id == "abc123"

        mock_client.search.assert_awaited_once_with(
            index="rp-tl-*",
            body={
                "size": 100,
                "from": 0,
                "sort": [{"@timestamp": {"order": "desc"}}],
                "query": {"bool": {"must": [{"term": {"trace_id": "abc123"}}]}},
            },
        )

    async def test_query_empty_results(self, config: ElasticsearchConfig) -> None:
        store = ElasticsearchLogStore(config=config)
        mock_client = AsyncMock()
        mock_client.search = AsyncMock(return_value={"hits": {"hits": []}})
        store._client = mock_client

        results = [e async for e in store.query(LogFilter())]
        assert results == []

    async def test_count_returns_document_count(self, config: ElasticsearchConfig) -> None:
        store = ElasticsearchLogStore(config=config)
        mock_client = AsyncMock()
        mock_client.count = AsyncMock(return_value={"count": 42})
        store._client = mock_client

        count = await store.count(LogFilter(service="test"))

        assert count == 42
        mock_client.count.assert_awaited_once()

    async def test_health_returns_true_when_connected(self, config: ElasticsearchConfig) -> None:
        store = ElasticsearchLogStore(config=config)
        mock_client = AsyncMock()
        mock_client.ping = AsyncMock(return_value=True)
        store._client = mock_client

        assert await store.health() is True

    async def test_health_returns_false_when_no_client(self, config: ElasticsearchConfig) -> None:
        store = ElasticsearchLogStore(config=config)
        assert await store.health() is False

    async def test_health_returns_false_on_ping_failure(self, config: ElasticsearchConfig) -> None:
        store = ElasticsearchLogStore(config=config)
        mock_client = AsyncMock()
        mock_client.ping = AsyncMock(side_effect=Exception("connection failed"))
        store._client = mock_client

        assert await store.health() is False

    async def test_bootstrap_creates_ilm_and_template(self, config: ElasticsearchConfig) -> None:
        store = ElasticsearchLogStore(config=config)
        mock_client = AsyncMock()
        mock_client.ilm.get_lifecycle = AsyncMock(return_value=False)
        mock_client.ilm.put_lifecycle = AsyncMock()
        mock_client.indices.exists_index_template = AsyncMock(return_value=False)
        mock_client.indices.put_index_template = AsyncMock()
        store._client = mock_client

        await store._bootstrap()

        mock_client.ilm.get_lifecycle.assert_awaited_once_with(name="rp-tl-ilm-policy")
        mock_client.ilm.put_lifecycle.assert_awaited_once()
        mock_client.indices.exists_index_template.assert_awaited_once_with(name="rp-tl-template")
        mock_client.indices.put_index_template.assert_awaited_once()

    async def test_bootstrap_skips_if_ilm_exists(self, config: ElasticsearchConfig) -> None:
        store = ElasticsearchLogStore(config=config)
        mock_client = AsyncMock()
        mock_client.ilm.get_lifecycle = AsyncMock(return_value=True)
        mock_client.ilm.put_lifecycle = AsyncMock()
        mock_client.indices.exists_index_template = AsyncMock(return_value=True)
        mock_client.indices.put_index_template = AsyncMock()
        store._client = mock_client

        await store._bootstrap()

        mock_client.ilm.put_lifecycle.assert_not_awaited()
        mock_client.indices.put_index_template.assert_not_awaited()

    async def test_write_raises_if_not_started(self, config: ElasticsearchConfig, entry: LogEntry) -> None:
        store = ElasticsearchLogStore(config=config)
        with pytest.raises(AssertionError, match="not started"):
            await store.write(entry)

    async def test_query_raises_if_not_started(self, config: ElasticsearchConfig) -> None:
        store = ElasticsearchLogStore(config=config)
        flt = LogFilter()
        with pytest.raises(AssertionError, match="not started"):
            async for _ in store.query(flt):
                pass
