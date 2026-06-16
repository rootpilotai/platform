"""Elasticsearch IncidentStore adapter for incident persistence and retrieval."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from elasticsearch import AsyncElasticsearch, NotFoundError
from pydantic import BaseModel, Field

from infrastructure.elasticsearch.incident_index_strategy import (
    ILM_POLICY_NAME,
    INDEX_PREFIX,
    TEMPLATE_NAME,
    build_context_doc,
    default_ilm_policy,
    default_index_template,
    incident_index_name,
)
from shared.contracts.interfaces.incident_store import IncidentFilter, IncidentStore
from shared.domain.incident.context.models import IncidentContext

logger = logging.getLogger(__name__)


class IncidentElasticsearchConfig(BaseModel):
    hosts: str = Field(
        default="http://localhost:9200",
        description="Elasticsearch server URL(s).",
    )
    username: str | None = Field(
        default=None,
        description="Elasticsearch basic auth username (null = no auth).",
    )
    password: str | None = Field(
        default=None,
        description="Elasticsearch basic auth password (null = no auth).",
    )
    index_prefix: str = Field(
        default=INDEX_PREFIX,
        description="Prefix for incident indices.",
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
    request_timeout: int = Field(default=30, ge=5, description="HTTP request timeout in seconds.")


class ElasticsearchIncidentStore(IncidentStore):
    """IncidentStore implementation backed by Elasticsearch.

    Manages daily rolling indices (``rp-inc-{yyyy.MM.dd}``) with an index
    template that applies consistent mappings and an ILM policy for
    automated retention.
    """

    def __init__(self, config: IncidentElasticsearchConfig | None = None) -> None:
        self._config = config or IncidentElasticsearchConfig()
        self._client: AsyncElasticsearch | None = None
        self._bootstrap_done = False

    async def start(self) -> None:
        """Connect to Elasticsearch and bootstrap index template + ILM policy."""
        if self._client is not None:
            return

        kwargs: dict = {
            "hosts": [self._config.hosts],
            "timeout": self._config.request_timeout,
        }
        if self._config.username is not None and self._config.password is not None:
            kwargs["basic_auth"] = (self._config.username, self._config.password)

        self._client = AsyncElasticsearch(**kwargs)

        await self._bootstrap()
        self._bootstrap_done = True
        logger.info("ElasticsearchIncidentStore started", extra={"hosts": self._config.hosts})

    async def close(self) -> None:
        """Close the Elasticsearch client connection."""
        if self._client is not None:
            await self._client.close()
            self._client = None
            self._bootstrap_done = False
            logger.info("ElasticsearchIncidentStore closed")

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
                policy=default_ilm_policy(),
            )
            logger.info("Created ILM policy", extra={"policy": self._config.ilm_policy_name})

        template_exists = await self._client.indices.exists_index_template(
            name=self._config.template_name,
        )
        if not template_exists:
            body = default_index_template()
            body["template"]["settings"]["number_of_shards"] = self._config.number_of_shards
            body["template"]["settings"]["number_of_replicas"] = self._config.number_of_replicas
            body["template"]["settings"]["index.lifecycle.name"] = self._config.ilm_policy_name
            await self._client.indices.put_index_template(
                name=self._config.template_name,
                body=body,
            )
            logger.info("Created index template", extra={"template": self._config.template_name})

    async def store(self, context: IncidentContext) -> None:
        assert self._client is not None, "ElasticsearchIncidentStore not started"

        doc = build_context_doc(context)
        index = incident_index_name(context.detected_at)

        await self._client.index(index=index, id=context.incident_id, document=doc)

    async def get(self, incident_id: str) -> IncidentContext | None:
        assert self._client is not None, "ElasticsearchIncidentStore not started"

        try:
            response = await self._client.get(
                index=f"{self._config.index_prefix}-*",
                id=incident_id,
            )
        except Exception:
            return None

        source = response["_source"]
        return IncidentContext.model_validate(source)

    async def search(self, filter: IncidentFilter) -> AsyncIterator[IncidentContext]:  # type: ignore[override,misc]
        assert self._client is not None, "ElasticsearchIncidentStore not started"

        body = _build_query_body(filter)
        response = await self._client.search(
            index=f"{self._config.index_prefix}-*",
            body=body,
        )

        for hit in response["hits"]["hits"]:
            yield IncidentContext.model_validate(hit["_source"])

    async def count(self, filter: IncidentFilter) -> int:
        assert self._client is not None, "ElasticsearchIncidentStore not started"

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

    async def delete(self, incident_id: str) -> None:
        assert self._client is not None, "ElasticsearchIncidentStore not started"

        try:
            await self._client.delete(
                index=f"{self._config.index_prefix}-*",
                id=incident_id,
            )
        except Exception:
            logger.warning("Failed to delete incident", extra={"incident_id": incident_id})

    async def health(self) -> bool:
        if self._client is None:
            return False
        try:
            return await self._client.ping()
        except Exception:
            return False


def _build_query_body(filter: IncidentFilter) -> dict:
    """Translate an IncidentFilter into an Elasticsearch query body."""
    must_clauses: list[dict] = []

    if filter.query_string:
        must_clauses.append({"query_string": {"query": filter.query_string}})

    if filter.primary_service:
        must_clauses.append({"term": {"primary_service": filter.primary_service}})

    if filter.severity:
        must_clauses.append({"term": {"severity": filter.severity}})

    if filter.min_score is not None:
        must_clauses.append({"range": {"max_correlation_score": {"gte": filter.min_score}}})

    if filter.start_time or filter.end_time:
        time_range: dict[str, str] = {}
        if filter.start_time:
            time_range["gte"] = filter.start_time.isoformat()
        if filter.end_time:
            time_range["lte"] = filter.end_time.isoformat()
        must_clauses.append({"range": {"detected_at": time_range}})

    body: dict = {
        "size": filter.limit,
        "from": filter.offset,
        "sort": [{filter.sort_field.value: {"order": filter.sort_order.value}}],
    }

    if must_clauses:
        body["query"] = {"bool": {"must": must_clauses}}
    else:
        body["query"] = {"match_all": {}}

    return body
