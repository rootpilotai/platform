"""Tests for investigation domain models."""

from shared.domain.investigation.models import (
    IncidentProgression,
    InvestigationResult,
    RCASummary,
    RemediationStep,
    RootCause,
)


class TestRootCause:
    def test_minimal(self) -> None:
        rc = RootCause(
            service="api-gateway",
            confidence=0.85,
            evidence=["error budget burned"],
            explanation="gateway timeout cascade",
        )
        assert rc.service == "api-gateway"
        assert rc.confidence == 0.85
        assert len(rc.evidence) == 1

    def test_confidence_rejects_out_of_range(self) -> None:
        import pytest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            RootCause(service="db", confidence=1.5, evidence=[], explanation="")


class TestRemediationStep:
    def test_minimal(self) -> None:
        step = RemediationStep(action="restart", service="api", priority="high", expected_impact="resume serving")
        assert step.priority == "high"


class TestIncidentProgression:
    def test_minimal(self) -> None:
        prog = IncidentProgression(
            sequence=["error spike", "degradation"], timeline_summary="escalated quickly", key_transitions=["paged"]
        )
        assert len(prog.sequence) == 2


class TestRCASummary:
    def test_minimal(self) -> None:
        rc = RootCause(service="auth", confidence=0.9, evidence=["5xx spike"], explanation="auth timeout")
        prog = IncidentProgression(
            sequence=["deploy", "errors"], timeline_summary="post-deploy regression", key_transitions=["rollback"]
        )
        summary = RCASummary(
            incident_id="inc-001",
            title="Auth degradation",
            root_causes=[rc],
            progression=prog,
            overall_confidence=0.9,
        )
        assert summary.incident_id == "inc-001"
        assert len(summary.root_causes) == 1
        assert summary.generated_at.tzinfo is not None

    def test_with_remediation(self) -> None:
        rc = RootCause(service="db", confidence=0.7, evidence=["slow queries"], explanation="index missing")
        prog = IncidentProgression(sequence=["latency"], timeline_summary="degraded", key_transitions=[])
        step = RemediationStep(
            action="add index", service="db", priority="critical", expected_impact="restore performance"
        )
        summary = RCASummary(
            incident_id="inc-002",
            title="DB slowdown",
            root_causes=[rc],
            progression=prog,
            remediation=[step],
            overall_confidence=0.7,
        )
        assert len(summary.remediation) == 1


class TestInvestigationResult:
    def test_minimal(self) -> None:
        rc = RootCause(service="srv", confidence=0.5, evidence=["err"], explanation="cause")
        prog = IncidentProgression(sequence=["a"], timeline_summary="b", key_transitions=["c"])
        summary = RCASummary(incident_id="i1", title="t", root_causes=[rc], progression=prog, overall_confidence=0.5)
        result = InvestigationResult(summary=summary)
        assert result.summary.incident_id == "i1"
        assert result.duration_ms == 0.0
        assert result.raw_output is None
