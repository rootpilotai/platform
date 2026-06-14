"""InvestigationPipeline — deterministic RCA orchestration.

Assembles incident context into prompts, calls the LLM for structured output,
and returns an InvestigationResult.
"""

import time

from app.prompts.rca import RCAPrompts
from shared.contracts.interfaces.llm_provider import LLMProvider
from shared.domain.incident.context.models import IncidentContext
from shared.domain.investigation.models import InvestigationResult, RCASummary


class InvestigationPipeline:
    """Deterministic investigation pipeline.

    Usage:
        pipeline = InvestigationPipeline(llm_provider)
        result = await pipeline.run(incident_context)
    """

    def __init__(self, llm_provider: LLMProvider) -> None:
        self._llm = llm_provider

    async def run(self, context: IncidentContext) -> InvestigationResult:
        """Run the full investigation pipeline for a given incident context."""
        start = time.perf_counter()

        messages = RCAPrompts.build_rca_messages(context)

        summary: RCASummary = await self._llm.generate_structured(messages, RCASummary)

        duration = (time.perf_counter() - start) * 1000

        return InvestigationResult(
            summary=summary,
            raw_output=None,
            duration_ms=round(duration, 2),
        )
