from datetime import UTC, datetime

from pydantic import BaseModel, Field


class RootCause(BaseModel):
    """A probable root cause identified during investigation."""

    service: str = Field(description="Service identified as the root cause.")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in this root cause identification.")
    evidence: list[str] = Field(description="Evidence supporting this root cause.")
    explanation: str = Field(description="Natural language explanation of why this is the root cause.")


class IncidentProgression(BaseModel):
    """Chronological narrative of how the incident unfolded."""

    sequence: list[str] = Field(description="Chronological sequence of key events.")
    timeline_summary: str = Field(description="Narrative summary of how the incident unfolded over time.")
    key_transitions: list[str] = Field(description="Key state changes or escalation points.")


class RemediationStep(BaseModel):
    """A suggested remediation action."""

    action: str = Field(description="Action to take.")
    service: str = Field(description="Target service for this action.")
    priority: str = Field(description="Priority level: critical, high, medium, low.")
    expected_impact: str = Field(description="Expected result of this action.")


class RCASummary(BaseModel):
    """Complete root cause analysis summary for an incident."""

    incident_id: str = Field(description="Incident identifier.")
    title: str = Field(description="Short human-readable incident summary.")
    root_causes: list[RootCause] = Field(description="Identified probable root causes, ranked by confidence.")
    progression: IncidentProgression = Field(description="Incident progression narrative.")
    remediation: list[RemediationStep] = Field(
        default_factory=list, description="Suggested remediation steps, ordered by priority."
    )
    overall_confidence: float = Field(ge=0.0, le=1.0, description="Overall confidence in the analysis.")
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="When this summary was generated."
    )


class InvestigationResult(BaseModel):
    """The complete output of an investigation pipeline run."""

    summary: RCASummary = Field(description="The structured RCA summary.")
    raw_output: str | None = Field(default=None, description="Raw LLM response text for debugging.")
    duration_ms: float = Field(default=0.0, description="Pipeline execution time in milliseconds.")
