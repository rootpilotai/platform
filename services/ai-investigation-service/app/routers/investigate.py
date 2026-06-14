from fastapi import APIRouter, Depends, HTTPException, Request

from app.pipeline import InvestigationPipeline
from shared.domain.incident.context.models import IncidentContext
from shared.domain.investigation.models import InvestigationResult

router = APIRouter(prefix="/investigate", tags=["investigate"])


def _get_pipeline(request: Request) -> InvestigationPipeline:
    pipeline: InvestigationPipeline | None = getattr(request.app.state, "pipeline", None)
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Investigation pipeline not available")
    return pipeline


@router.post("/run", response_model=InvestigationResult)
async def run_investigation(
    context: IncidentContext,
    pipeline: InvestigationPipeline = Depends(_get_pipeline),
) -> InvestigationResult:
    return await pipeline.run(context)
