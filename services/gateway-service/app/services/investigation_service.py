"""Investigation service — maps domain models to response schemas."""

from app.schemas import (
    IncidentProgressionResponse,
    InvestigationResponse,
    RemediationStepResponse,
    RootCauseResponse,
)
from shared.domain.investigation.models import InvestigationResult


def map_investigation_to_response(
    investigation_id: str,
    result: InvestigationResult,
) -> InvestigationResponse:
    summary = result.summary
    return InvestigationResponse(
        investigation_id=investigation_id,
        incident_id=summary.incident_id,
        title=summary.title,
        root_causes=[RootCauseResponse(**rc.model_dump()) for rc in summary.root_causes],
        progression=IncidentProgressionResponse(**summary.progression.model_dump()),
        remediation=[RemediationStepResponse(**rs.model_dump()) for rs in summary.remediation],
        overall_confidence=summary.overall_confidence,
        generated_at=summary.generated_at,
        duration_ms=result.duration_ms,
    )
