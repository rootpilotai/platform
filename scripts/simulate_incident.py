"""Simulate a large-scale incident with noise — validate the correlation engine.

This test sends a mix of:
  - **Noise**: healthy metrics from unrelated services, spread far apart in time.
    These should be filtered out (pruned as old, or left as ungrouped singletons).
  - **Signal**: a realistic 3-tier incident cascade (db → api → gateway) with
    error-pattern metric names and tight time proximity.
    These should form correlation groups above the 0.2 threshold.

Expected correlation behaviour
  - All signal events land in a single BFS-connected group (connected via
    TimeWindowStrategy within 60s AND ErrorSignatureStrategy).
  - Recent noise events (offsets 95-270s) remain ungrouped → filtered out.
  - The incident context reports 22 correlated events, ~8 ungrouped.

Expected notification (sent on investigation.completed)
  Title:    "Correlated incident detected across 3 service(s)"
  Severity: critical (overall_confidence > 0.7)
  Body:
    * postgres-primary (0.xx): Database CPU spike causing cascading query latency
      degradation and connection timeouts.
    * api-gateway (0.xx): API errors and latency due to upstream database degradation.
    * gateway (0.xx): Upstream errors (502/503) from degraded API layer.
  Fields:   Incident ID, Investigation ID, Confidence

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


# ────────────────────────────────────────────────────────────────────────────
#  NOISE events – normal / healthy telemetry from unrelated services
#
#  These events have:
#     * non-error metric names → ErrorSignatureStrategy ignores them
#     * timestamps spread >20s apart → TimeWindowStrategy produces matches
#       below the 0.2 composite threshold (weighted score ≤ 0.195)
#     * services unrelated to the signal cascade → no dependency edges
#
#  Two tiers:
#    1. OLD noise (offsets 600-360s)  → pruned by ConnectionManager (300s window)
#    2. RECENT noise (offsets 95-270s) → stay in buffer but remain singletons
# ────────────────────────────────────────────────────────────────────────────

NOISE_EVENTS: list[dict] = []
_NOISE_SERVICES = [
    "web-static", "cdn-edge", "dns-resolver", "search-cache",
    "notification-relay", "worker-pool", "scheduler", "config-service",
    "audit-log", "rate-limiter",
]
_NOISE_METRICS = ["cpu.usage", "memory.usage", "requests.rate", "disk.usage"]

# Tier 1: old noise (pruned – offsets 600→360, every 6s = 40 events)
for i, svc in enumerate(_NOISE_SERVICES):
    for j, metric in enumerate(_NOISE_METRICS):
        offset = 600 - i * 24 - j * 6  # 600, 594, 588 ... 366
        NOISE_EVENTS.append({
            "metric": metric,
            "value": round(25 + hash(f"{svc}{metric}{i}{j}") % 30, 1),
            "unit": {"cpu.usage": "%", "memory.usage": "%", "requests.rate": "rps", "disk.usage": "%"}[metric],
            "source": svc,
            "tags": {"service": svc, "region": "us-east-1", "tier": "noise"},
            "timestamp": _ts(offset),
        })

# Tier 2: recent noise (offsets 270→95, every 25s = 8 events)
_RECENT_NOISE_OFFSETS = [270, 245, 220, 195, 170, 145, 120, 95]
_RECENT_NOISE = [
    {"source": "cdn-edge",        "metric": "cpu.usage",        "value": 42.0, "unit": "%"},
    {"source": "dns-resolver",    "metric": "memory.usage",    "value": 55.0, "unit": "%"},
    {"source": "cdn-edge",        "metric": "cache.hit.ratio", "value": 91.0, "unit": "%"},
    {"source": "dns-resolver",    "metric": "request.rate",    "value": 180.0, "unit": "rps"},
    {"source": "cdn-edge",        "metric": "cpu.usage",       "value": 38.0, "unit": "%"},
    {"source": "dns-resolver",    "metric": "cpu.usage",       "value": 35.0, "unit": "%"},
    {"source": "cdn-edge",        "metric": "memory.usage",    "value": 48.0, "unit": "%"},
    {"source": "dns-resolver",    "metric": "memory.usage",    "value": 52.0, "unit": "%"},
]
for i, ev in enumerate(_RECENT_NOISE):
    ev["tags"] = {"service": ev["source"], "region": "us-east-1", "tier": "noise"}
    ev["timestamp"] = _ts(_RECENT_NOISE_OFFSETS[i])
    NOISE_EVENTS.append(ev)

# ────────────────────────────────────────────────────────────────────────────
#  SIGNAL events – a real 3-tier incident cascade
#
#  These events share:
#     * tight time proximity (all within a 55s window → TimeWindowStrategy
#       connects every pair with score 0.083–1.0)
#     * error-prefixed metric names → ErrorSignatureStrategy connects them
#       with score 0.5–0.8
#     * services forming a real dependency chain: postgres-primary →
#       api-gateway → gateway
#
#  Cascade phases:
#    1. DB CPU anomaly  (T-55s → T-45s)
#    2. Query latency   (T-45s → T-30s)
#    3. API timeouts    (T-30s → T-10s)
#    4. Gateway 502s    (T-10s → T-0s)
# ────────────────────────────────────────────────────────────────────────────

SIGNAL_EVENTS: list[dict] = [
    # ── Phase 1: DB CPU climb + connection errors ──────────────────────
    {"metric": "error.db.connection",    "value": 1.0,   "unit": "count", "source": "postgres-primary", "tags": {"service": "db", "region": "us-east-1", "tier": "root_cause"}, "timestamp": _ts(55)},
    {"metric": "db.cpu.usage",           "value": 72.0,  "unit": "%",     "source": "postgres-primary", "tags": {"service": "db", "region": "us-east-1"},                "timestamp": _ts(52)},
    {"metric": "error.db.connection",    "value": 3.0,   "unit": "count", "source": "postgres-primary", "tags": {"service": "db", "region": "us-east-1", "tier": "root_cause"}, "timestamp": _ts(50)},
    {"metric": "db.cpu.usage",           "value": 78.0,  "unit": "%",     "source": "postgres-primary", "tags": {"service": "db", "region": "us-east-1"},                "timestamp": _ts(48)},
    {"metric": "error.db.connection",    "value": 7.0,   "unit": "count", "source": "postgres-primary", "tags": {"service": "db", "region": "us-east-1", "tier": "root_cause"}, "timestamp": _ts(45)},
    {"metric": "db.cpu.usage",           "value": 85.0,  "unit": "%",     "source": "postgres-primary", "tags": {"service": "db", "region": "us-east-1"},                "timestamp": _ts(45)},
    # ── Phase 2: Query latency degrades ────────────────────────────────
    {"metric": "db.query.latency",       "value": 450.0, "unit": "ms",    "source": "postgres-primary", "tags": {"service": "db", "query": "SELECT * FROM orders"},      "timestamp": _ts(42)},
    {"metric": "db.query.latency",       "value": 1200.0,"unit": "ms",    "source": "postgres-primary", "tags": {"service": "db", "query": "SELECT * FROM orders"},      "timestamp": _ts(38)},
    {"metric": "db.query.latency",       "value": 2300.0,"unit": "ms",    "source": "postgres-primary", "tags": {"service": "db", "query": "SELECT * FROM orders"},      "timestamp": _ts(35)},
    {"metric": "db.connections.active",  "value": 89.0,  "unit": "count", "source": "postgres-primary", "tags": {"service": "db", "pool": "primary"},                    "timestamp": _ts(30)},
    # ── Phase 3: API timeouts (cascading from slow DB) ─────────────────
    {"metric": "api.request.latency",    "value": 3200.0,"unit": "ms",    "source": "api-gateway",      "tags": {"service": "api", "endpoint": "/api/orders"},              "timestamp": _ts(28)},
    {"metric": "error.api.timeout",      "value": 12.0,  "unit": "%",     "source": "api-gateway",      "tags": {"service": "api", "error": "timeout", "tier": "impact"},    "timestamp": _ts(25)},
    {"metric": "error.api.timeout",      "value": 18.0,  "unit": "%",     "source": "api-gateway",      "tags": {"service": "api", "error": "timeout", "tier": "impact"},    "timestamp": _ts(22)},
    {"metric": "error.api.upstream",     "value": 15.0,  "unit": "count", "source": "api-gateway",      "tags": {"service": "api", "upstream": "db", "tier": "impact"},      "timestamp": _ts(18)},
    {"metric": "api.error.rate",         "value": 28.0,  "unit": "%",     "source": "api-gateway",      "tags": {"service": "api", "error": "5xx"},                       "timestamp": _ts(15)},
    {"metric": "api.request.latency",    "value": 5100.0,"unit": "ms",    "source": "api-gateway",      "tags": {"service": "api", "endpoint": "/api/orders"},              "timestamp": _ts(12)},
    # ── Phase 4: Gateway 502s (cascading from slow API) ────────────────
    {"metric": "error.gateway.upstream", "value": 42.0,  "unit": "count", "source": "gateway",          "tags": {"service": "gateway", "upstream": "api", "tier": "impact"}, "timestamp": _ts(10)},
    {"metric": "error.gateway.upstream", "value": 87.0,  "unit": "count", "source": "gateway",          "tags": {"service": "gateway", "upstream": "api", "tier": "impact"}, "timestamp": _ts(8)},
    {"metric": "error.gateway.timeout",  "value": 12.0,  "unit": "count", "source": "gateway",          "tags": {"service": "gateway", "upstream": "api", "tier": "impact"}, "timestamp": _ts(6)},
    {"metric": "gateway.latency",        "value": 6200.0,"unit": "ms",    "source": "gateway",          "tags": {"service": "gateway", "endpoint": "/api/orders"},           "timestamp": _ts(4)},
    {"metric": "error.gateway.upstream", "value": 124.0, "unit": "count", "source": "gateway",          "tags": {"service": "gateway", "upstream": "api", "tier": "impact"}, "timestamp": _ts(2)},
    {"metric": "gateway.latency",        "value": 8100.0,"unit": "ms",    "source": "gateway",          "tags": {"service": "gateway", "endpoint": "/api/orders"},           "timestamp": _ts(0)},
]

# All events in order (noise first, then signal)
TELEMETRY_BATCH = NOISE_EVENTS + SIGNAL_EVENTS


def send_telemetry(client: httpx.Client) -> list[str]:
    ids: list[str] = []
    total = len(TELEMETRY_BATCH)
    noise_count = len(NOISE_EVENTS)
    sig_count = len(SIGNAL_EVENTS)

    print(f"  Sending {total} events ({noise_count} noise, {sig_count} signal)...")

    for idx, point in enumerate(TELEMETRY_BATCH):
        resp = client.post(TELEMETRY_URL, json=point)
        resp.raise_for_status()
        data = resp.json()
        ids.append(data["event_id"])
        tier = point["tags"].get("tier", "")
        prefix = "  [NOISE]" if tier == "noise" else "[SIGNAL]" if tier else "       "
        short_id = data["event_id"][:8]
        print(f"  {prefix} {point['source']:20s} {point['metric']:30s} = {point['value']:>8} {point['unit'] or '':4s}  -> {short_id}...")
    return ids


# ── Direct mode (manual investigation via REST) ─────────────────────────


def build_incident_context(event_ids: list[str]) -> dict:
    sig_ids = event_ids[-len(SIGNAL_EVENTS):]  # signal events are at the end
    noise_ids = event_ids[:len(NOISE_EVENTS)]  # noise events at the start

    return {
        "incident_id": f"sim-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}",
        "primary_service": "postgres-primary",
        "severity": "CRITICAL",
        "title": "Database latency spike cascading to API timeouts and gateway 502 errors",
        "detected_at": datetime.now(UTC).isoformat(),
        "event_count": len(event_ids),
        "service_count": 11,  # 3 signal + 8 noise services
        "trace_count": 0,
        "ungrouped_events": noise_ids,  # noise should be ungrouped
        "correlation_groups": [
            {
                "group_id": "g-db",
                "event_ids": sig_ids[:10],
                "composite_score": 0.92,
                "signals": ["time_proximity", "error_pattern"],
                "services": ["postgres-primary"],
            },
            {
                "group_id": "g-api",
                "event_ids": sig_ids[10:16],
                "composite_score": 0.85,
                "signals": ["time_proximity", "error_pattern"],
                "services": ["api-gateway"],
            },
            {
                "group_id": "g-gateway",
                "event_ids": sig_ids[16:],
                "composite_score": 0.78,
                "signals": ["time_proximity", "error_pattern"],
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
        print(f"    * {rc['service']:25s}  ({rc['confidence']:.0%} confidence)")
        print(f"      {rc['explanation'][:150]}")
    print(f"\n  Remediation ({len(summary.get('remediation', []))}):")
    for step in summary.get("remediation", []):
        print(f"    * [{step['priority']:>8}] {step['action']}")
    print(f"\n  Timeline:")
    print(f"    {summary['progression']['timeline_summary'][:200]}")


def run_direct(client: httpx.Client, context: dict) -> dict:
    resp = client.post(INVESTIGATION_URL, json=context, timeout=120)
    resp.raise_for_status()
    return resp.json()


# ── Event-driven mode (via RabbitMQ) ───────────────────────────────────


def wait_for_notification(timeout_seconds: int = 60) -> bool:
    """Poll the notification health endpoint until providers become active."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            resp = httpx.get(NOTIFICATION_HEALTH_URL, timeout=3)
            if resp.is_success:
                data = resp.json()
                providers = data.get("providers", [])
                if providers:
                    print(f"  + Notification providers active: {[p['name'] for p in providers]}")
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
                print(f"  + {name}")
            else:
                print(f"  - {name} ({resp.status_code})")
                ok = False
        except httpx.RequestError:
            print(f"  - {name} (unreachable)")
            ok = False
    return ok


def main() -> None:
    parser = argparse.ArgumentParser(description="RootPilot incident simulation")
    parser.add_argument("--direct", action="store_true", help="Bypass event bus and call investigation REST endpoint directly")
    args = parser.parse_args()

    noise_old = sum(1 for ev in NOISE_EVENTS if _ts_to_offset(ev["timestamp"]) > 300)
    noise_recent = len(NOISE_EVENTS) - noise_old

    print("-- Checking services ------------------------------------")
    if not check_services():
        print("\nSome services are unavailable. Starting ingestion only...")
    print()

    print("-- Scenario: Large-Scale DB Cascade (noise reduction test) -")
    print(f"    Noise:  {len(NOISE_EVENTS)} events ({noise_old} pruned by 300s window, {noise_recent} recent singletons)")
    print(f"    Signal: {len(SIGNAL_EVENTS)} events forming a 3-tier cascade")
    print(f"    Expected: signal grouped into 1-3 correlation groups, noise filtered out\n")
    print("    Expected notification:")
    print("      Title:    Correlated incident detected across 3 service(s)")
    print("      Severity: critical")
    print("      Body:     * postgres-primary (0.xx): database CPU spike causing cascading ...")
    print("                * api-gateway (0.xx): API errors due to upstream database ...")
    print("                * gateway (0.xx): upstream errors (502) from degraded API ...\n")

    with httpx.Client() as client:
        print("Sending telemetry batch to ingestion...")
        event_ids = send_telemetry(client)
        print(f"\n  + {len(event_ids)} events accepted\n")

        if args.direct:
            print("Direct mode - building incident context and calling investigation REST endpoint...")
            context = build_incident_context(event_ids)
            result = run_direct(client, context)
            print(f"\n-- Investigation Result -----------------------------")
            print_result(result)
        else:
            print("Event-driven mode - telemetry flows through the automated pipeline:")
            print("    ingestion -> correlation -> investigation -> notification")
            print(f"\n  Waiting for the pipeline to process ({'checking notification service'})...")
            if wait_for_notification(timeout_seconds=60):
                print("\n  + Pipeline completed. Notifications dispatched (check Slack/Discord).")
            else:
                print("\n  ! Notification service still waiting for events.")
                print("    Ensure RabbitMQ and all services are running with `docker compose up`.")
                print("    Fallback: run with `--direct` to test investigation without RabbitMQ.")

    print("\nDone.")

def _ts_to_offset(ts_str: str) -> int:
    """Helper to estimate offset in seconds from a timestamp string."""
    from datetime import datetime
    try:
        parsed = datetime.fromisoformat(ts_str)
        return int((datetime.now(UTC) - parsed).total_seconds())
    except Exception:
        return 0


if __name__ == "__main__":
    main()
