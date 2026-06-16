"""Elasticsearch index strategy for investigation documents.

Index naming convention:
  rp-inv-{yyyy.MM.dd}
  rp   = RootPilot
  inv  = investigations

Template: rp-inv-template  (applied to rp-inv-*)
ILM policy: rp-inv-ilm-policy
"""

from datetime import UTC, datetime

from shared.domain.investigation.models import InvestigationResult

INDEX_PREFIX = "rp-inv"
TEMPLATE_NAME = "rp-inv-template"
ILM_POLICY_NAME = "rp-inv-ilm-policy"


def investigation_index_name(dt: datetime | None = None) -> str:
    """Return the target index name for a given timestamp (UTC daily bucket)."""
    ts = dt or datetime.now(UTC)
    return f"{INDEX_PREFIX}-{ts.strftime('%Y.%m.%d')}"


def build_investigation_doc(result: InvestigationResult) -> dict:
    """Convert an InvestigationResult into an Elasticsearch document."""
    summary = result.summary
    return {
        "@timestamp": summary.generated_at.isoformat(),
        "incident_id": summary.incident_id,
        "title": summary.title,
        "overall_confidence": summary.overall_confidence,
        "generated_at": summary.generated_at.isoformat(),
        "duration_ms": result.duration_ms,
        "has_raw_output": result.raw_output is not None,
        "root_cause_count": len(summary.root_causes),
        "remediation_count": len(summary.remediation),
        "root_causes": [rc.model_dump(mode="json") for rc in summary.root_causes],
        "progression": summary.progression.model_dump(mode="json"),
        "remediation": [rs.model_dump(mode="json") for rs in summary.remediation],
    }


def default_index_template() -> dict:
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
                    "incident_id": {"type": "keyword"},
                    "title": {"type": "text", "analyzer": "english"},
                    "overall_confidence": {"type": "float"},
                    "generated_at": {"type": "date"},
                    "duration_ms": {"type": "float"},
                    "has_raw_output": {"type": "boolean"},
                    "root_cause_count": {"type": "integer"},
                    "remediation_count": {"type": "integer"},
                    "root_causes": {"type": "object", "enabled": False},
                    "progression": {"type": "object", "enabled": False},
                    "remediation": {"type": "object", "enabled": False},
                },
            },
        },
        "priority": 100,
    }


def default_ilm_policy() -> dict:
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
