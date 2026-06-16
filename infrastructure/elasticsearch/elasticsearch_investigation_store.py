"""Elasticsearch InvestigationStore adapter for investigation persistence and retrieval."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from datetime import datetime
from uuid import uuid4

from elasticsearch import AsyncElasticsearch
from pydantic import BaseModel, Field

from infrastructure.elasticsearch.investigation_index_strategy import (
    ILM_POLICY_NAME,
    INDEX_PREFIX,
    TEMPLATE_NAME,
    build_investigation_doc,
    default_ilm_policy,
    default_index_template,
    investigation_index_name,
)
from shared.contracts.interfaces.investigation_store import InvestigationFilter, InvestigationStore
from shared.domain.investigation.models import InvestigationResult

logger = logging.getLogger(__name__)


class InvestigationElasticsearchConfig(BaseModel):
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
        description="Prefix for investigation indices.",
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


class ElasticsearchInvestigationStore(InvestigationStore):
    """InvestigationStore implementation backed by Elasticsearch.

    Manages daily rolling indices (``rp-inv-{yyyy.MM.dd}``) with an index
    template that applies consistent mappings and an ILM policy for
    automated retention.
    """

    def __init__(self, config: InvestigationElasticsearchConfig | None = None) -> None:
        self._config = config or InvestigationElasticsearchConfig()
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
        logger.info("ElasticsearchInvestigationStore started", extra={"hosts": self._config.hosts})

    async def close(self) -> None:
        """Close the Elasticsearch client connection."""
        if self._client is not None:
            await self._client.close()
            self._client = None
            self._bootstrap_done = False
            logger.info("ElasticsearchInvestigationStore closed")

    async def _bootstrap(self) -> None:
        """Create ILM policy and index template if they don't exist."""
        assert self._client is not None

        ilm_exists = await self._client.ilm.get_lifecycle(
            name=self._config.ilm_policy_name,
        )
        if not ilm_exists:
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

    def _generate_id(self) -> str:
        return str(uuid4())

    async def store(self, investigation_id: str, result: InvestigationResult) -> None:
        assert self._client is not None, "ElasticsearchInvestigationStore not started"

        doc = build_investigation_doc(result)
        index = investigation_index_name(result.summary.generated_at)

        await self._client.index(index=index, id=investigation_id, document=doc)

    async def get(self, investigation_id: str) -> InvestigationResult | None:
        assert self._client is not None, "ElasticsearchInvestigationStore not started"

        try:
            response = await self._client.get(
                index=f"{self._config.index_prefix}-*",
                id=investigation_id,
            )
        except Exception:
            return None

        source = response["_source"]
        return _parse_investigation_doc(source)

    async def get_by_incident(self, incident_id: str) -> InvestigationResult | None:
        assert self._client is not None, "ElasticsearchInvestigationStore not started"

        try:
            response = await self._client.search(
                index=f"{self._config.index_prefix}-*",
                body={
                    "size": 1,
                    "query": {"term": {"incident_id": incident_id}},
                    "sort": [{"generated_at": {"order": "desc"}}],
                },
            )
        except Exception:
            return None

        hits = response["hits"]["hits"]
        if not hits:
            return None

        return _parse_investigation_doc(hits[0]["_source"])

    async def search(self, filter: InvestigationFilter) -> AsyncIterator[InvestigationResult]:
        assert self._client is not None, "ElasticsearchInvestigationStore not started"

        body = _build_query_body(filter)
        response = await self._client.search(
            index=f"{self._config.index_prefix}-*",
            body=body,
        )

        for hit in response["hits"]["hits"]:
            yield _parse_investigation_doc(hit["_source"])

    async def count(self, filter: InvestigationFilter) -> int:
        assert self._client is not None, "ElasticsearchInvestigationStore not started"

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

    async def latest(self) -> InvestigationResult | None:
        assert self._client is not None, "ElasticsearchInvestigationStore not started"

        try:
            response = await self._client.search(
                index=f"{self._config.index_prefix}-*",
                body={
                    "size": 1,
                    "query": {"match_all": {}},
                    "sort": [{"generated_at": {"order": "desc"}}],
                },
            )
        except Exception:
            return None

        hits = response["hits"]["hits"]
        if not hits:
            return None

        return _parse_investigation_doc(hits[0]["_source"])

    async def health(self) -> bool:
        if self._client is None:
            return False
        try:
            return await self._client.ping()
        except Exception:
            return False


def _build_query_body(filter: InvestigationFilter) -> dict:
    """Translate an InvestigationFilter into an Elasticsearch query body."""
    must_clauses: list[dict] = []

    if filter.incident_id:
        must_clauses.append({"term": {"incident_id": filter.incident_id}})

    if filter.min_confidence is not None:
        must_clauses.append({"range": {"overall_confidence": {"gte": filter.min_confidence}}})

    if filter.start_time or filter.end_time:
        time_range: dict[str, str] = {}
        if filter.start_time:
            time_range["gte"] = filter.start_time.isoformat()
        if filter.end_time:
            time_range["lte"] = filter.end_time.isoformat()
        must_clauses.append({"range": {"generated_at": time_range}})

    body: dict = {
        "size": filter.limit,
        "from": filter.offset,
        "sort": [{filter.sort_field: {"order": filter.sort_order}}],
    }

    if must_clauses:
        body["query"] = {"bool": {"must": must_clauses}}
    else:
        body["query"] = {"match_all": {}}

    return body


def _parse_investigation_doc(source: dict) -> InvestigationResult:
    """Reconstruct an InvestigationResult from an ES document source."""
    from shared.domain.investigation.models import (
        IncidentProgression,
        RCASummary,
        RemediationStep,
        RootCause,
    )

    rc_summary = RCASummary(
        incident_id=source["incident_id"],
        title=source["title"],
        root_causes=[RootCause(**rc) for rc in source.get("root_causes", [])],
        progression=IncidentProgression(**source["progression"]),
        remediation=[RemediationStep(**rs) for rs in source.get("remediation", [])],
        overall_confidence=source["overall_confidence"],
        generated_at=datetime.fromisoformat(source["generated_at"]),
    )

    return InvestigationResult(
        summary=rc_summary,
        raw_output=None,
        duration_ms=source.get("duration_ms", 0.0),
    )
