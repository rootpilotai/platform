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
- **The "Reachable Services" section lists services that are confirmed alive (they sent health-check telemetry) but had no failure signals. A reachable service CANNOT be a root cause. It is functioning normally.** The "Terminal Root Cause Candidates" section below has already excluded reachable services from its analysis.
- **Silent dependencies** (services with zero events) are critical root cause candidates ONLY IF they are NOT listed in Reachable Services. The section "Terminal Root Cause Candidates" below provides pre-computed analysis. Use it when ranking root causes — it identifies which silent deps sit at the end of the error chain vs which are intermediaries or broadly shared dependencies.
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
            reachable_set = set(context.reachable_services)
            lines.append("### Impact Analysis")
            for impact in context.impacts:
                lines.append(f"  Service: {impact.service}")
                if impact.upstream_causes:
                    lines.append(f"    Upstream Causes: {', '.join(impact.upstream_causes)}")
                if impact.downstream_impact:
                    lines.append(f"    Downstream Impact: {', '.join(impact.downstream_impact)}")
                if impact.silent_dependencies:
                    silent_lines = []
                    for sd in impact.silent_dependencies:
                        if sd in reachable_set:
                            silent_lines.append(f"{sd} (zero events but CONFIRMED REACHABLE — not a root cause)")
                        else:
                            silent_lines.append(f"{sd} (zero events — may be down)")
                    lines.append(f"    Silent Dependencies: {', '.join(silent_lines)}")
                if impact.propagation_paths:
                    paths = [" -> ".join(p) for p in impact.propagation_paths]
                    lines.append(f"    Propagation Paths: {' | '.join(paths)}")
            lines.append("")

        if context.reachable_services:
            lines.append("### Reachable Services")
            lines.append(
                "The following services are confirmed reachable (they sent health-check telemetry) but have no failure signals. These services are operating normally and are ELIMINATED as root cause candidates — they are alive and responding:"
            )
            lines.append(f"  {', '.join(context.reachable_services)}")
            lines.append("")

        # Pre-compute terminal root cause candidates from silent deps + propagation paths
        terminal_candidates = cls._compute_terminal_candidates(context, set(context.reachable_services))
        if terminal_candidates:
            lines.append("### Terminal Root Cause Candidates (pre-computed)")
            lines.append("These candidates scored highest by automated analysis of silent deps and propagation paths:")
            for label, silent_dep, services_detail in terminal_candidates:
                lines.append(f"  - {silent_dep} ({label}): {services_detail}")
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

    @classmethod
    def _compute_terminal_candidates(
        cls, context: IncidentContext, reachable: set[str] | None = None
    ) -> list[tuple[str, str, str]]:
        if not context.impacts:
            return []

        silents: dict[str, list[str]] = {}
        for impact in context.impacts:
            for sd in impact.silent_dependencies:
                if sd not in silents:
                    silents[sd] = []
                silents[sd].append(impact.service)

        # Exclude services confirmed reachable — they are NOT root cause candidates
        if reachable:
            for sd in list(silents):
                if sd in reachable:
                    del silents[sd]

        path_services: set[str] = set()
        path_ends: set[str] = set()
        for impact in context.impacts:
            for path in impact.propagation_paths:
                path_services.update(path)
                if path:
                    path_ends.add(path[-1])

        trace_services: set[str] = set()
        for tg in context.trace_groups or []:
            trace_services.update(tg.service_names or [])

        end_services_with_silent_deps: set[str] = set()
        for impact in context.impacts:
            if impact.service in path_ends and impact.silent_dependencies:
                end_services_with_silent_deps.add(impact.service)

        candidates: list[tuple[str, str, str]] = []

        for sd, parents in silents.items():
            if sd in path_services:
                candidates.append(
                    ("intermediary", sd, f"silent dep of {', '.join(parents)} but in paths — NOT root cause")
                )
                continue

            terminal_score = 0
            trails = []
            trace_parents = [p for p in parents if p in trace_services]

            for impact in context.impacts:
                if impact.service not in parents:
                    continue
                for path in impact.propagation_paths:
                    if len(path) > 1 and path[-1] == sd:
                        terminal_score += 3
                        trails.append(" -> ".join(path))
                if impact.service in end_services_with_silent_deps and sd in impact.silent_dependencies:
                    terminal_score += 2
                    if not trails:
                        trails.append(f"via {impact.service} (at path end)")

            if trace_parents:
                terminal_score += 2 * len(trace_parents)
                if not trails:
                    trails.append(f"silent dep of trace services: {', '.join(trace_parents)}")

            label = "broad" if len(parents) >= 3 else "direct"
            if terminal_score >= 3:
                label = "TERMINAL"

            if label == "TERMINAL":
                candidates.append(
                    (
                        "TERMINAL",
                        sd,
                        f"at end of error chain from {', '.join(parents)} (trace: {', '.join(trace_parents) or 'none'}; paths: {'; '.join(trails[:2])})",
                    )
                )
            elif label == "broad":
                candidates.append(
                    (
                        "broad",
                        sd,
                        f"silent dep of {len(parents)} services ({', '.join(parents)}) — not in error trace, weak signal",
                    )
                )
            else:
                candidates.append(("direct", sd, f"direct silent dep of {', '.join(parents)}"))

        label_order = {"TERMINAL": 0, "direct": 1, "broad": 2, "intermediary": 3}
        candidates.sort(key=lambda x: (label_order.get(x[0], 99), x[1]))
        return candidates
