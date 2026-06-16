"""Elasticsearch LogStore adapter for telemetry storage and investigation queries."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from elasticsearch import AsyncElasticsearch, NotFoundError
from elasticsearch.helpers import async_bulk
from pydantic import BaseModel, Field

from shared.contracts.interfaces.log_store import LogEntry, LogFilter, LogStore

logger = logging.getLogger(__name__)

# ── Index naming ──────────────────────────────────────────────────────────
# Daily rolling indices: rp-tl-{yyyy.MM.dd}
#   rp   = RootPilot
#   tl   = telemetry/logs
# Template: rp-tl-template  (applied to rp-tl-*)
# ILM policy: rp-tl-ilm-policy
# ──────────────────────────────────────────────────────────────────────────

INDEX_PREFIX = "rp-tl"
TEMPLATE_NAME = "rp-tl-template"
ILM_POLICY_NAME = "rp-tl-ilm-policy"


def _index_name(dt: datetime | None = None) -> str:
    """Return the target index name for a given timestamp (UTC daily bucket)."""
    ts = dt or datetime.now(UTC)
    return f"{INDEX_PREFIX}-{ts.strftime('%Y.%m.%d')}"


def _build_es_doc(entry: LogEntry) -> dict:
    """Convert a LogEntry into an Elasticsearch document."""
    return {
        "@timestamp": entry.timestamp.isoformat(),
        "event_id": id(entry),
        "service": entry.service,
        "level": entry.level,
        "message": entry.message,
        "trace_id": entry.trace_id,
        "span_id": entry.span_id,
        "metadata": entry.metadata,
    }


# ── Default index template body ──────────────────────────────────────────
# Applied automatically at startup to ensure consistent mappings.
# ─────────────────────────────────────────────────────────────────────────


def _default_index_template() -> dict:
    return {
        "index_patterns": [f"{INDEX_PREFIX}-*"],
        "template": {
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
                "index.lifecycle.name": ILM_POLICY_NAME,
                "index.lifecycle.rollover_alias": INDEX_PREFIX,
            },
            "mappings": {
                "dynamic": "strict",
                "properties": {
                    "@timestamp": {"type": "date"},
                    "event_id": {"type": "keyword"},
                    "service": {"type": "keyword"},
                    "level": {"type": "keyword"},
                    "message": {"type": "text", "analyzer": "english"},
                    "trace_id": {"type": "keyword"},
                    "span_id": {"type": "keyword"},
                    "correlation_id": {"type": "keyword"},
                    "metadata": {"type": "flattened"},
                },
            },
        },
        "priority": 100,
    }


def _default_ilm_policy() -> dict:
    return {
        "policy": {
            "phases": {
                "hot": {
                    "min_age": "0ms",
                    "actions": {
                        "rollover": {"max_age": "1d", "max_primary_shard_size": "50gb"},
                        "set_priority": {"priority": 100},
                    },
                },
                "warm": {
                    "min_age": "7d",
                    "actions": {
                        "set_priority": {"priority": 50},
                        "forcemerge": {"max_num_segments": 1},
                    },
                },
                "cold": {
                    "min_age": "30d",
                    "actions": {
                        "set_priority": {"priority": 0},
                    },
                },
                "delete": {
                    "min_age": "90d",
                    "actions": {
                        "delete": {},
                    },
                },
            },
        },
    }


# ── Query builder ─────────────────────────────────────────────────────────


def _build_query_body(filter: LogFilter) -> dict:
    """Translate a LogFilter into an Elasticsearch query body."""
    must_clauses: list[dict] = []

    if filter.query_string:
        must_clauses.append({"query_string": {"query": filter.query_string}})

    if filter.service:
        must_clauses.append({"term": {"service": filter.service}})

    if filter.level:
        must_clauses.append({"term": {"level": filter.level}})

    if filter.trace_id:
        must_clauses.append({"term": {"trace_id": filter.trace_id}})

    if filter.start_time or filter.end_time:
        time_range: dict[str, str] = {}
        if filter.start_time:
            time_range["gte"] = filter.start_time.isoformat()
        if filter.end_time:
            time_range["lte"] = filter.end_time.isoformat()
        must_clauses.append({"range": {"@timestamp": time_range}})

    body: dict = {
        "size": filter.limit,
        "from": filter.offset,
        "sort": [{"@timestamp": {"order": filter.sort_order.value}}],
    }

    if must_clauses:
        body["query"] = {"bool": {"must": must_clauses}}
    else:
        body["query"] = {"match_all": {}}

    return body


# ── Elasticsearch Configuration ───────────────────────────────────────────


class ElasticsearchConfig(BaseModel):
    hosts: str = Field(
        default="http://localhost:9200",
        description="Elasticsearch server URL(s).",
    )
    index_prefix: str = Field(
        default=INDEX_PREFIX,
        description="Prefix for telemetry indices.",
    )
    ilm_policy_name: str = Field(
        default=ILM_POLICY_NAME,
        description="Name of the ILM policy to apply.",
    )
    template_name: str = Field(
        default=TEMPLATE_NAME,
        description="Name of the index template.",
    )
    number_of_shards: int = Field(default=1, ge=1, description="Primary shard count.")
    number_of_replicas: int = Field(default=0, ge=0, description="Replica count.")
    bulk_batch_size: int = Field(default=500, ge=1, le=10_000, description="Documents per bulk write.")
    request_timeout: int = Field(default=30, ge=5, description="HTTP request timeout in seconds.")


# ── Elasticsearch LogStore Adapter ────────────────────────────────────────


class ElasticsearchLogStore(LogStore):
    """LogStore implementation backed by Elasticsearch.

    Manages daily rolling indices (``rp-tl-{yyyy.MM.dd}``) with an index
    template that applies consistent mappings and an ILM policy for
    automated retention.
    """

    def __init__(self, config: ElasticsearchConfig | None = None) -> None:
        self._config = config or ElasticsearchConfig()
        self._client: AsyncElasticsearch | None = None
        self._bootstrap_done = False

    # ── Lifecycle ─────────────────────────────────────────────────────

    async def start(self) -> None:
        """Connect to Elasticsearch and bootstrap index template + ILM policy."""
        if self._client is not None:
            return

        self._client = AsyncElasticsearch(
            hosts=[self._config.hosts],
            timeout=self._config.request_timeout,
        )

        await self._bootstrap()
        self._bootstrap_done = True
        logger.info("ElasticsearchLogStore started", extra={"hosts": self._config.hosts})

    async def close(self) -> None:
        """Close the Elasticsearch client connection."""
        if self._client is not None:
            await self._client.close()
            self._client = None
            self._bootstrap_done = False
            logger.info("ElasticsearchLogStore closed")

    async def _bootstrap(self) -> None:
        """Create ILM policy and index template if they don't exist."""
        assert self._client is not None

        try:
            await self._client.ilm.get_lifecycle(
                name=self._config.ilm_policy_name,
            )
        except NotFoundError:
            await self._client.ilm.put_lifecycle(
                name=self._config.ilm_policy_name,
                policy=_default_ilm_policy(),
            )
            logger.info("Created ILM policy", extra={"policy": self._config.ilm_policy_name})

        template_exists = await self._client.indices.exists_index_template(
            name=self._config.template_name,
        )
        if not template_exists:
            body = _default_index_template()
            body["template"]["settings"]["number_of_shards"] = self._config.number_of_shards
            body["template"]["settings"]["number_of_replicas"] = self._config.number_of_replicas
            body["template"]["settings"]["index.lifecycle.name"] = self._config.ilm_policy_name
            await self._client.indices.put_index_template(
                name=self._config.template_name,
                body=body,
            )
            logger.info("Created index template", extra={"template": self._config.template_name})

    # ── LogStore Implementation ───────────────────────────────────────

    async def write(self, entry: LogEntry) -> None:
        assert self._client is not None, "ElasticsearchLogStore not started"

        doc = _build_es_doc(entry)
        index = _index_name(entry.timestamp)

        await self._client.index(index=index, document=doc)

    async def write_batch(self, entries: list[LogEntry]) -> None:
        assert self._client is not None, "ElasticsearchLogStore not started"

        async def _generate_actions():
            for entry in entries:
                doc = _build_es_doc(entry)
                index = _index_name(entry.timestamp)
                yield {"_index": index, "_source": doc}

        success: int
        errors: list[Any]
        success, errors = await async_bulk(  # type: ignore[assignment]
            client=self._client,
            actions=_generate_actions(),
            chunk_size=self._config.bulk_batch_size,
            refresh=False,
        )

        if errors:
            logger.warning(
                "Bulk write completed with errors",
                extra={"success": success, "errors": len(errors)},
            )
        else:
            logger.debug("Bulk write succeeded", extra={"count": success})

    async def query(self, filter: LogFilter) -> AsyncIterator[LogEntry]:  # type: ignore[override,misc]
        assert self._client is not None, "ElasticsearchLogStore not started"

        body = _build_query_body(filter)
        response = await self._client.search(
            index=f"{self._config.index_prefix}-*",
            body=body,
        )

        for hit in response["hits"]["hits"]:
            src = hit["_source"]
            yield LogEntry(
                timestamp=datetime.fromisoformat(src["@timestamp"]),
                service=src.get("service", ""),
                level=src.get("level", ""),
                message=src.get("message", ""),
                trace_id=src.get("trace_id"),
                span_id=src.get("span_id"),
                metadata=src.get("metadata", {}),
            )

    async def count(self, filter: LogFilter) -> int:
        assert self._client is not None, "ElasticsearchLogStore not started"

        body = _build_query_body(filter)
        body.pop("size", None)
        body.pop("from", None)
        body.pop("sort", None)
        body["size"] = 0

        response = await self._client.count(
            index=f"{self._config.index_prefix}-*",
            body=body,
        )
        return response["count"]

    async def health(self) -> bool:
        if self._client is None:
            return False
        try:
            return await self._client.ping()
        except Exception:
            return False
