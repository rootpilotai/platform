"""Tests for telemetry and incident event contracts."""

import json

from shared.contracts.events import (
    Event,
    IncidentDetectedEvent,
    InvestigationRequestedEvent,
    Severity,
    TelemetryEvent,
)


class TestTelemetryEvent:
    def test_default_timestamp_is_utc(self) -> None:
        event = TelemetryEvent(metric="cpu", value=50.0, source="test")
        assert event.timestamp.tzinfo is not None

    def test_round_trip_json(self) -> None:
        original = TelemetryEvent(metric="mem.usage", value=1024.0, unit="MB", tags={"host": "a"}, source="svc")
        data = json.loads(original.model_dump_json())
        restored = TelemetryEvent.model_validate(data)
        assert restored == original

    def test_model_version_present(self) -> None:
        event = TelemetryEvent(metric="cpu", value=1.0, source="test")
        assert event.model_version == "1.0"


class TestIncidentDetectedEvent:
    def test_round_trip_json(self) -> None:
        original = IncidentDetectedEvent(
            incident_id="INC-001",
            severity=Severity.CRITICAL,
            service="api-gateway",
            title="timeout spike",
        )
        restored = IncidentDetectedEvent.model_validate_json(original.model_dump_json())
        assert restored == original

    def test_default_severity_is_optional(self) -> None:
        event = IncidentDetectedEvent(incident_id="INC-002", severity=Severity.INFO, service="svc", title="test")
        assert event.severity == Severity.INFO

    def test_source_event_ids_defaults_empty(self) -> None:
        event = IncidentDetectedEvent(incident_id="INC-003", severity=Severity.WARNING, service="svc", title="test")
        assert event.source_event_ids == []


class TestInvestigationRequestedEvent:
    def test_round_trip_json(self) -> None:
        original = InvestigationRequestedEvent(
            investigation_id="INV-001",
            incident_id="INC-001",
            depth="deep",
        )
        restored = InvestigationRequestedEvent.model_validate_json(original.model_dump_json())
        assert restored == original

    def test_default_depth_is_standard(self) -> None:
        event = InvestigationRequestedEvent(investigation_id="INV-002", incident_id="INC-002")
        assert event.depth == "standard"

    def test_context_defaults_empty(self) -> None:
        event = InvestigationRequestedEvent(investigation_id="INV-003", incident_id="INC-003")
        assert event.context == {}


class TestWrappedInEventEnvelope:
    def test_telemetry_in_envelope(self) -> None:
        telemetry = TelemetryEvent(metric="cpu", value=50.0, source="test")
        envelope = Event(source="test", topic="telemetry.ingested", payload=telemetry.model_dump())
        assert envelope.topic == "telemetry.ingested"
        assert envelope.payload["metric"] == "cpu"

    def test_incident_in_envelope(self) -> None:
        incident = IncidentDetectedEvent(incident_id="INC-001", severity=Severity.ERROR, service="svc", title="err")
        envelope = Event(source="svc", topic="incident.detected", payload=incident.model_dump())
        assert envelope.payload["incident_id"] == "INC-001"

    def test_investigation_in_envelope(self) -> None:
        inv = InvestigationRequestedEvent(investigation_id="INV-001", incident_id="INC-001")
        envelope = Event(source="svc", topic="investigation.requested", payload=inv.model_dump())
        assert envelope.payload["investigation_id"] == "INV-001"


class TestVersionAware:
    def test_all_events_have_model_version(self) -> None:
        telemetry = TelemetryEvent(metric="cpu", value=1.0, source="test")
        incident = IncidentDetectedEvent(incident_id="INC-001", severity=Severity.INFO, service="svc", title="t")
        inv = InvestigationRequestedEvent(investigation_id="INV-001", incident_id="INC-001")

        assert telemetry.model_version == "1.0"
        assert incident.model_version == "1.0"
        assert inv.model_version == "1.0"
