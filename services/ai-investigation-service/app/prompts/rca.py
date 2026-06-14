"""RCA prompt templates — modular, testable, and version-controlled."""

from shared.contracts.interfaces.llm_provider import LLMMessage
from shared.domain.incident.context.models import IncidentContext


class RCAPrompts:
    """Factory for building RCA prompt messages from incident context."""

    SYSTEM_PROMPT = """You are a senior Site Reliability Engineer conducting a root cause analysis.

Your task is to analyse the provided incident context and produce a structured RCA summary.

Rules:
- Base your analysis strictly on the evidence provided. Do not speculate beyond the data.
- Rank root causes by confidence based on correlation scores, impact chains, and supporting evidence.
- If evidence is insufficient, reflect low confidence rather than guessing.
- Remediation steps must be concrete, actionable, and ordered by priority.
- Use technical precision — be specific about services, signals, and time windows."""

    @classmethod
    def build_rca_messages(cls, context: IncidentContext) -> list[LLMMessage]:
        """Build the message list for RCA generation."""
        return [
            LLMMessage(role="system", content=cls.SYSTEM_PROMPT),
            LLMMessage(role="user", content=cls._format_context(context)),
        ]

    @classmethod
    def _format_context(cls, context: IncidentContext) -> str:
        """Format the incident context as a structured text prompt."""
        lines: list[str] = [
            f"## Incident: {context.title or 'Untitled'}",
            f"ID: {context.incident_id}",
            f"Primary Service: {context.primary_service}",
            f"Severity: {context.severity}",
            f"Detected At: {context.detected_at.isoformat()}",
            "",
            f"Total Events: {context.event_count}",
            f"Services Involved: {context.service_count}",
            f"Unique Traces: {context.trace_count}",
            "",
        ]

        if context.timeline:
            timeline = context.timeline
            lines.append("### Timeline")
            lines.append(f"Duration: {timeline.duration_seconds or 'N/A'} seconds")
            lines.append(f"Windows: {timeline.window_count}")
            lines.append(f"Total Events: {timeline.total_events}")
            lines.append("")

        if context.correlation_groups:
            lines.append("### Correlation Groups")
            for i, group in enumerate(context.correlation_groups, 1):
                services = ", ".join(group.services) if group.services else "unknown"
                lines.append(
                    f"  {i}. Score: {group.composite_score} | Signals: {[s.value for s in group.signals]} | Services: [{services}]"
                )
                if group.trace_id:
                    lines.append(f"     Trace: {group.trace_id} ({group.span_count} spans)")
            lines.append("")

        if context.impacts:
            lines.append("### Impact Analysis")
            for impact in context.impacts:
                lines.append(f"  Service: {impact.service}")
                if impact.upstream_causes:
                    lines.append(f"    Upstream Causes: {', '.join(impact.upstream_causes)}")
                if impact.downstream_impact:
                    lines.append(f"    Downstream Impact: {', '.join(impact.downstream_impact)}")
                if impact.propagation_paths:
                    paths = [" -> ".join(p) for p in impact.propagation_paths]
                    lines.append(f"    Propagation Paths: {' | '.join(paths)}")
            lines.append("")

        if context.trace_groups:
            lines.append("### Trace Groups")
            for tg in context.trace_groups:
                services = ", ".join(tg.service_names) if tg.service_names else "N/A"
                lines.append(
                    f"  Trace: {tg.trace_id} | Services: [{services}] | Spans: {tg.span_count} | Events: {len(tg.event_ids)}"
                )
            lines.append("")

        if context.ungrouped_events:
            lines.append(f"### Ungrouped Events: {len(context.ungrouped_events)} events below correlation threshold")
            lines.append("")

        lines.append("Provide your analysis following the output schema exactly.")
        return "\n".join(lines)
