"""InvestigationPipeline — deterministic RCA orchestration.

Assembles incident context into prompts, calls the LLM for structured output,
and returns an InvestigationResult.
"""

import logging
import time

from app.prompts.rca import RCAPrompts
from shared.contracts.interfaces.llm_provider import LLMProvider
from shared.domain.incident.context.models import IncidentContext
from shared.domain.investigation.models import InvestigationResult, RCASummary

logger = logging.getLogger(__name__)


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
        run_start = time.perf_counter()

        logger.info(
            "Starting investigation",
            extra={
                "incident_id": context.incident_id,
                "primary_service": context.primary_service,
                "event_count": context.event_count,
                "service_count": context.service_count,
                "trace_count": context.trace_count,
                "impact_count": len(context.impacts),
                "correlation_groups": len(context.correlation_groups),
            },
        )

        t0 = time.perf_counter()
        messages = RCAPrompts.build_rca_messages(context)
        prompt_duration = (time.perf_counter() - t0) * 1000
        logger.info(
            "Context formatted in %.0fms (system=%d chars, user=%d chars)",
            prompt_duration,
            len(messages[0].content) if messages else 0,
            len(messages[1].content) if len(messages) > 1 else 0,
        )

        llm_start = time.perf_counter()
        summary: RCASummary = await self._llm.generate_structured(messages, RCASummary)
        llm_duration = (time.perf_counter() - llm_start) * 1000

        total_duration = (time.perf_counter() - run_start) * 1000

        top = summary.root_causes[0] if summary.root_causes else None
        logger.info(
            "Investigation complete — LLM took %.0fms (total %.0fms) | top_root_cause=%s confidence=%.2f overall=%.2f",
            llm_duration,
            total_duration,
            top.service if top else "none",
            top.confidence if top else 0.0,
            summary.overall_confidence,
        )

        return InvestigationResult(
            summary=summary,
            raw_output=None,
            duration_ms=round(total_duration, 2),
        )
