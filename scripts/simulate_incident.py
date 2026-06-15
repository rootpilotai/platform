"""Simulate a realistic database latency spike incident end-to-end.

Two modes:
  1) Event-driven (default) — sends telemetry to ingestion; the automated
     pipeline (correlation → investigation → notification) handles the rest.
  2) Direct — calls the investigation REST endpoint directly for testing
     without RabbitMQ/full stack.

Usage:
    python -m scripts.simulate_incident              # event-driven mode
    python -m scripts.simulate_incident --direct      # bypass event bus
"""

import argparse
import sys
import time
from datetime import UTC, datetime, timedelta

import httpx

HEALTH_URLS = {
    "ingestion (8000)": "http://localhost:8000/health",
    "notification (8003)": "http://localhost:8003/health",
}

TELEMETRY_URL = "http://localhost:8000/api/v1/ingest"
INVESTIGATION_URL = "http://localhost:8002/investigate/run"
NOTIFICATION_HEALTH_URL = "http://localhost:8003/health"


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
        resp = client.post(TELEMETRY_URL, json=point)
        resp.raise_for_status()
        data = resp.json()
        ids.append(data["event_id"])
        print(f"  ✓ {point['metric']:30s} = {point['value']:>8} {point['unit'] or '':4s}  →  {data['event_id'][:8]}...")
    return ids


# ── Direct mode (manual investigation via REST) ─────────────────────────


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


def print_result(result: dict) -> None:
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


def run_direct(client: httpx.Client, context: dict) -> dict:
    resp = client.post(INVESTIGATION_URL, json=context, timeout=120)
    resp.raise_for_status()
    return resp.json()


# ── Event-driven mode (via RabbitMQ) ───────────────────────────────────


def wait_for_notification(timeout_seconds: int = 30) -> bool:
    """Poll the notification health endpoint until providers become active."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            resp = httpx.get(NOTIFICATION_HEALTH_URL, timeout=3)
            if resp.is_success:
                data = resp.json()
                providers = data.get("providers", [])
                if providers:
                    print(f"  ✓ Notification providers active: {[p['name'] for p in providers]}")
                return True
        except httpx.RequestError:
            pass
        print("  . waiting for event-driven pipeline...")
        time.sleep(3)
    return False


# ── Shared helpers ─────────────────────────────────────────────────────


def check_services() -> bool:
    ok = True
    for name, url in HEALTH_URLS.items():
        try:
            resp = httpx.get(url, timeout=5)
            if resp.is_success:
                print(f"  ✓ {name}")
            else:
                print(f"  ✗ {name} ({resp.status_code})")
                ok = False
        except httpx.RequestError:
            print(f"  ✗ {name} (unreachable)")
            ok = False
    return ok


def main() -> None:
    parser = argparse.ArgumentParser(description="RootPilot incident simulation")
    parser.add_argument("--direct", action="store_true", help="Bypass event bus and call investigation REST endpoint directly")
    args = parser.parse_args()

    print("── Checking services ────────────────────────────────────")
    if not check_services():
        print("\nSome services are unavailable. Starting ingestion only...")
    print()

    print("── Scenario: Database Latency Spike ─────────────────────")
    print("    Primary database CPU spikes → query latency jumps to 2.3s\n")

    with httpx.Client() as client:
        print("Sending 14 telemetry points to ingestion...")
        event_ids = send_telemetry(client)
        print(f"\n  ✓ {len(event_ids)} events accepted\n")

        if args.direct:
            print("Direct mode — building incident context and calling investigation REST endpoint...")
            context = build_incident_context(event_ids)
            result = run_direct(client, context)
            print(f"\n── Investigation Result ────────────────────────────")
            print_result(result)
        else:
            print("Event-driven mode — telemetry flows through the automated pipeline:")
            print("    ingestion → correlation → investigation → notification")
            print(f"\n  Waiting for the pipeline to process ({'checking notification service'})...")
            if wait_for_notification(timeout_seconds=30):
                print("\n  ✓ Pipeline completed. Notifications dispatched (check Slack/Discord).")
            else:
                print("\n  ⚠ Notification service still waiting for events.")
                print("    Ensure RabbitMQ and all services are running with `docker compose up`.")
                print("    Fallback: run with `--direct` to test investigation without RabbitMQ.")

    print("\nDone.")


if __name__ == "__main__":
    main()
