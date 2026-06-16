"""Gateway service Pydantic response schemas."""

from datetime import datetime

from pydantic import BaseModel


class PaginatedResponse[T](BaseModel):
    items: list[T]
    total: int
    limit: int
    offset: int


class HealthResponse(BaseModel):
    status: str
    incident_store: bool
    investigation_store: bool
    api_key_store: bool


class RootCauseResponse(BaseModel):
    service: str
    confidence: float
    evidence: list[str]
    explanation: str


class IncidentProgressionResponse(BaseModel):
    sequence: list[str]
    timeline_summary: str
    key_transitions: list[str]


class RemediationStepResponse(BaseModel):
    action: str
    service: str
    priority: str
    expected_impact: str


class InvestigationResponse(BaseModel):
    investigation_id: str
    incident_id: str
    title: str
    root_causes: list[RootCauseResponse]
    progression: IncidentProgressionResponse
    remediation: list[RemediationStepResponse]
    overall_confidence: float
    generated_at: datetime
    duration_ms: float


class IncidentResponse(BaseModel):
    incident_id: str
    primary_service: str
    severity: str
    title: str
    detected_at: datetime
    aggregated_at: datetime
    event_count: int
    service_count: int
    trace_count: int
    max_correlation_score: float | None
    service_list: list[str]
