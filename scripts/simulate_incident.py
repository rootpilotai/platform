"""Simulate a realistic database latency spike incident end-to-end.

Sends telemetry to the ingestion service (port 8000), then builds an
incident context and runs the investigation pipeline (port 8002).

Usage:
    python -m scripts.simulate_incident
    # or: python scripts/simulate_incident.py
"""

import sys
from datetime import UTC, datetime, timedelta

import httpx

INGESTION_URL = "http://localhost:8000/api/v1/ingest"
INVESTIGATION_URL = "http://localhost:8002/investigate/run"


def _ts(offset_seconds: int = 0) -> str:
    return (datetime.now(UTC) - timedelta(seconds=offset_seconds)).isoformat()


TELEMETRY_BATCH = [
    # ── Phase 1: DB CPU climb (T-120s to T-60s) ──────────────────────
    {"metric": "db.cpu.usage", "value": 72.0, "unit": "%", "source": "postgres-primary", "tags": {"service": "db", "region": "us-east-1"}, "timestamp": _ts(120)},
    {"metric": "db.cpu.usage", "value": 78.0, "unit": "%", "source": "postgres-primary", "tags": {"service": "db", "region": "us-east-1"}, "timestamp": _ts(90)},
    {"metric": "db.cpu.usage", "value": 85.0, "unit": "%", "source": "postgres-primary", "tags": {"service": "db", "region": "us-east-1"}, "timestamp": _ts(60)},
    # ── Phase 2: Query latency degrades (T-60s to T-30s) ─────────────
    {"metric": "db.query.latency", "value": 450.0, "unit": "ms", "source": "postgres-primary", "tags": {"service": "db", "query": "SELECT * FROM orders"}, "timestamp": _ts(60)},
    {"metric": "db.query.latency", "value": 1200.0, "unit": "ms", "source": "postgres-primary", "tags": {"service": "db", "query": "SELECT * FROM orders"}, "timestamp": _ts(45)},
    {"metric": "db.query.latency", "value": 2300.0, "unit": "ms", "source": "postgres-primary", "tags": {"service": "db", "query": "SELECT * FROM orders"}, "timestamp": _ts(30)},
    {"metric": "db.connections.active", "value": 89.0, "unit": "count", "source": "postgres-primary", "tags": {"service": "db", "pool": "primary"}, "timestamp": _ts(30)},
    # ── Phase 3: API timeouts (T-30s to T-10s) ───────────────────────
    {"metric": "api.request.latency", "value": 3200.0, "unit": "ms", "source": "api-gateway", "tags": {"service": "api", "endpoint": "/api/orders"}, "timestamp": _ts(30)},
    {"metric": "api.error.rate", "value": 12.5, "unit": "%", "source": "api-gateway", "tags": {"service": "api", "error": "timeout"}, "timestamp": _ts(25)},
    {"metric": "api.error.rate", "value": 28.0, "unit": "%", "source": "api-gateway", "tags": {"service": "api", "error": "timeout"}, "timestamp": _ts(15)},
    {"metric": "api.request.latency", "value": 5100.0, "unit": "ms", "source": "api-gateway", "tags": {"service": "api", "endpoint": "/api/orders"}, "timestamp": _ts(10)},
    # ── Phase 4: Gateway 502s (T-10s to now) ─────────────────────────
    {"metric": "gateway.upstream.errors", "value": 42.0, "unit": "count", "source": "gateway", "tags": {"service": "gateway", "upstream": "api", "status": "502"}, "timestamp": _ts(10)},
    {"metric": "gateway.upstream.errors", "value": 87.0, "unit": "count", "source": "gateway", "tags": {"service": "gateway", "upstream": "api", "status": "502"}, "timestamp": _ts(5)},
    {"metric": "gateway.latency", "value": 6200.0, "unit": "ms", "source": "gateway", "tags": {"service": "gateway", "endpoint": "/api/orders"}, "timestamp": _ts(3)},
]


def send_telemetry(client: httpx.Client) -> list[str]:
    ids: list[str] = []
    for point in TELEMETRY_BATCH:
        resp = client.post(INGESTION_URL, json=point)
        resp.raise_for_status()
        data = resp.json()
        ids.append(data["event_id"])
        print(f"  ✓ {point['metric']:30s} = {point['value']:>8} {point['unit'] or '':4s}  →  {data['event_id'][:8]}...")
    return ids


def build_incident_context(event_ids: list[str]) -> dict:
    return {
        "incident_id": f"sim-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}",
        "primary_service": "postgres-primary",
        "severity": "CRITICAL",
        "title": "Database latency spike cascading to API timeouts and gateway 502 errors",
        "detected_at": datetime.now(UTC).isoformat(),
        "event_count": len(event_ids),
        "service_count": 3,
        "trace_count": 0,
        "ungrouped_events": [],
        "correlation_groups": [
            {
                "group_id": "g-db",
                "event_ids": event_ids[:7],
                "composite_score": 0.89,
                "signals": ["time_proximity"],
                "services": ["postgres-primary"],
            },
            {
                "group_id": "g-api",
                "event_ids": event_ids[7:11],
                "composite_score": 0.82,
                "signals": ["time_proximity"],
                "services": ["api-gateway"],
            },
            {
                "group_id": "g-gateway",
                "event_ids": event_ids[11:],
                "composite_score": 0.75,
                "signals": ["time_proximity", "dependency_chain"],
                "services": ["gateway"],
            },
        ],
        "impacts": [
            {
                "service": "api-gateway",
                "upstream_causes": ["postgres-primary"],
                "downstream_impact": ["gateway"],
                "propagation_paths": [["postgres-primary", "api-gateway", "gateway"]],
            },
            {
                "service": "gateway",
                "upstream_causes": ["postgres-primary", "api-gateway"],
                "downstream_impact": [],
                "propagation_paths": [],
            },
        ],
    }


def run_investigation(client: httpx.Client, context: dict) -> dict:
    resp = client.post(INVESTIGATION_URL, json=context, timeout=120)
    resp.raise_for_status()
    return resp.json()


def check_service(url: str, name: str) -> bool:
    try:
        resp = httpx.get(url.replace("/api/v1/ingest", "/health").replace("/investigate/run", "/health"), timeout=5)
        return resp.is_success
    except httpx.RequestError as e:
        print(f"  ✗ {name} unreachable ({e})")
        return False


def main() -> None:
    print("Checking services...")
    health_ok = (
        check_service(INGESTION_URL, "ingestion (port 8000)")
        and check_service(INVESTIGATION_URL, "investigation (port 8002)")
    )
    if not health_ok:
        sys.exit(1)

    print("\n── Scenario: Database Latency Spike ──────────────────────")
    print("    Primary database CPU spikes → query latency jumps to 2.3s\n")

    with httpx.Client() as client:
        print("Sending 14 telemetry points to ingestion...")
        event_ids = send_telemetry(client)
        print(f"\n  ✓ {len(event_ids)} events accepted\n")

        print("Building incident context and running investigation...")
        context = build_incident_context(event_ids)
        result = run_investigation(client, context)

        print(f"\n── Investigation Result ──────────────────────────────")
        summary = result["summary"]
        print(f"  Incident:   {summary['incident_id']}")
        print(f"  Title:      {summary['title']}")
        print(f"  Duration:   {result['duration_ms']:.0f}ms")
        print(f"  Confidence: {summary['overall_confidence']:.0%}")
        print(f"\n  Root Causes ({len(summary['root_causes'])}):")
        for rc in summary["root_causes"]:
            print(f"    • {rc['service']:25s}  ({rc['confidence']:.0%} confidence)")
            print(f"      {rc['explanation'][:150]}")
        print(f"\n  Remediation ({len(summary.get('remediation', []))}):")
        for step in summary.get("remediation", []):
            print(f"    • [{step['priority']:>8}] {step['action']}")
        print(f"\n  Timeline:")
        print(f"    {summary['progression']['timeline_summary'][:200]}")
        print(f"\nDone.")


if __name__ == "__main__":
    main()
