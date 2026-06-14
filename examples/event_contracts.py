"""Serialization and usage examples for RootPilot event contracts."""

import json
from datetime import UTC, datetime

from shared.contracts import (
    Event,
    IncidentDetectedEvent,
    InvestigationRequestedEvent,
    Severity,
    TelemetryEvent,
)

# ---------------------------------------------------------------------------
# TelemetryEvent – serialize / deserialize
# ---------------------------------------------------------------------------

telemetry = TelemetryEvent(
    metric="cpu.usage",
    value=87.5,
    unit="%",
    tags={"host": "node-1", "region": "us-east"},
    source="ingestion-service",
)

telemetry_json = telemetry.model_dump_json(indent=2)
telemetry_restored = TelemetryEvent.model_validate_json(telemetry_json)

assert telemetry_restored == telemetry
print(f"Telemetry round-trip OK  ({telemetry.metric}={telemetry.value}{telemetry.unit})")


# ---------------------------------------------------------------------------
# Telemetry wrapped in Event envelope (for EventBus)
# ---------------------------------------------------------------------------

envelope = Event(
    source="ingestion-service",
    topic="telemetry.ingested",
    payload=telemetry.model_dump(),
)

print(f"Envelope: {envelope.id} -> {envelope.topic}")


# ---------------------------------------------------------------------------
# IncidentDetectedEvent
# ---------------------------------------------------------------------------

incident = IncidentDetectedEvent(
    incident_id="INC-001",
    severity=Severity.CRITICAL,
    service="api-gateway",
    title="Gateway timeout spike above threshold",
    description="p99 latency exceeded 5s for 3 consecutive minutes.",
    source_event_ids=[envelope.id],
    detected_at=datetime.now(UTC),
)

incident_json = incident.model_dump_json()
incident_restored = IncidentDetectedEvent.model_validate_json(incident_json)
assert incident_restored == incident
print(f"Incident round-trip OK  ({incident.incident_id} / {incident.severity})")

incident_envelope = Event(
    source="correlation-service",
    topic="incident.detected",
    payload=incident.model_dump(),
)

print(f"  -> {incident_envelope.topic}  id={incident_envelope.id}")


# ---------------------------------------------------------------------------
# InvestigationRequestedEvent
# ---------------------------------------------------------------------------

investigation = InvestigationRequestedEvent(
    investigation_id="INV-001",
    incident_id=incident.incident_id,
    context={"logs": ["log-1", "log-2"], "traces": ["trace-abc"]},
    depth="deep",
)

inv_json = investigation.model_dump_json()
inv_restored = InvestigationRequestedEvent.model_validate_json(inv_json)
assert inv_restored == investigation
print(f"Investigation round-trip OK  ({investigation.investigation_id})")

inv_envelope = Event(
    source="incident-service",
    topic="investigation.requested",
    payload=investigation.model_dump(),
)

print(f"  -> {inv_envelope.topic}  depth={investigation.depth}")


# ---------------------------------------------------------------------------
# Bulk serialization example
# ---------------------------------------------------------------------------

all_events = [
    {
        "type": "telemetry",
        "version": telemetry.model_version,
        "data": json.loads(telemetry_json),
    },
    {
        "type": "incident",
        "version": incident.model_version,
        "data": json.loads(incident_json),
    },
    {
        "type": "investigation",
        "version": investigation.model_version,
        "data": json.loads(inv_json),
    },
]

with open("examples/_sample_events.json", "w") as f:
    json.dump(all_events, f, indent=2, default=str)

print("Bulk export written to examples/_sample_events.json")
