"""Elasticsearch index strategy for incident documents.

Index naming convention:
  rp-inc-{yyyy.MM.dd}
  rp   = RootPilot
  inc  = incidents

Template: rp-inc-template  (applied to rp-inc-*)
ILM policy: rp-inc-ilm-policy
"""

from datetime import UTC, datetime

from shared.domain.incident.context.models import IncidentContext

INDEX_PREFIX = "rp-inc"
TEMPLATE_NAME = "rp-inc-template"
ILM_POLICY_NAME = "rp-inc-ilm-policy"


def incident_index_name(dt: datetime | None = None) -> str:
    """Return the target index name for a given timestamp (UTC daily bucket)."""
    ts = dt or datetime.now(UTC)
    return f"{INDEX_PREFIX}-{ts.strftime('%Y.%m.%d')}"


def build_context_doc(context: IncidentContext) -> dict:
    """Convert an IncidentContext into an Elasticsearch document."""
    return {
        "@timestamp": context.detected_at.isoformat(),
        "incident_id": context.incident_id,
        "primary_service": context.primary_service,
        "severity": context.severity,
        "title": context.title,
        "detected_at": context.detected_at.isoformat(),
        "aggregated_at": context.aggregated_at.isoformat(),
        "event_count": context.event_count,
        "service_count": context.service_count,
        "trace_count": context.trace_count,
        "correlation_group_count": len(context.correlation_groups),
        "ungrouped_event_count": len(context.ungrouped_events),
        "impact_count": len(context.impacts),
        "max_correlation_score": (
            max(g.composite_score for g in context.correlation_groups) if context.correlation_groups else None
        ),
        "service_list": sorted({svc for g in context.correlation_groups for svc in g.services}),
        "timeline": context.timeline.model_dump(mode="json") if context.timeline else None,
        "correlation_groups": [g.model_dump(mode="json") for g in context.correlation_groups],
        "ungrouped_events": context.ungrouped_events,
        "impacts": [i.model_dump(mode="json") for i in context.impacts],
        "trace_groups": [t.model_dump(mode="json") for t in context.trace_groups],
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
                    "primary_service": {"type": "keyword"},
                    "severity": {"type": "keyword"},
                    "title": {"type": "text", "analyzer": "english"},
                    "detected_at": {"type": "date"},
                    "aggregated_at": {"type": "date"},
                    "event_count": {"type": "integer"},
                    "service_count": {"type": "integer"},
                    "trace_count": {"type": "integer"},
                    "correlation_group_count": {"type": "integer"},
                    "ungrouped_event_count": {"type": "integer"},
                    "impact_count": {"type": "integer"},
                    "max_correlation_score": {"type": "float"},
                    "service_list": {"type": "keyword"},
                    "timeline": {"type": "object", "enabled": False},
                    "correlation_groups": {"type": "object", "enabled": False},
                    "ungrouped_events": {"type": "keyword"},
                    "impacts": {"type": "object", "enabled": False},
                    "trace_groups": {"type": "object", "enabled": False},
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
