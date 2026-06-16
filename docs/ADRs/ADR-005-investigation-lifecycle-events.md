# ADR-005: Investigation Lifecycle Events

## Status

Accepted

---

## Context

AI-powered root cause analysis in RootPilot spans multiple services and takes significant time (LLM inference can take 5–30+ seconds per investigation).

The correlation-service detects incidents and needs to trigger investigations asynchronously. The ai-investigation-service runs the analysis and must make results available to downstream consumers without blocking the correlation pipeline.

Key requirements:

* investigation trigger must be non-blocking
* investigation depth must be configurable per request
* results must be structured enough for automated consumption
* downstream consumers (notification-service, gateway-service) must receive completion signals

---

## Decision

Investigation workflows are modeled as two distinct events in the `EventBus` contract:

### InvestigationRequestedEvent

| Field | Type | Description |
|---|---|---|
| `investigation_id` | `str` | Unique investigation identifier |
| `incident_id` | `str` | Incident the investigation relates to |
| `context` | `dict[str, Any]` | Supporting data (logs, traces, metrics) |
| `depth` | `"quick" \| "standard" \| "deep"` | Analysis depth hint |
| `requested_at` | `datetime` | When the request was created |

### InvestigationCompletedEvent

| Field | Type | Description |
|---|---|---|
| `investigation_id` | `str` | Matches the original request |
| `incident_id` | `str` | Incident identifier |
| `summary` | `dict[str, Any]` | Complete RCA as structured dict |
| `completed_at` | `datetime` | When analysis finished |

### Investigation Pipeline Output Model

The internal domain model is `InvestigationResult`, which wraps:

* `RCASummary` — incident_id, title, root causes (confidence-rated), progression narrative, remediation steps, overall confidence
* `raw_output` — optional raw LLM response for debugging
* `duration_ms` — pipeline execution time

### Flow

```
Correlation Service
  └─ publishes INVESTIGATION_REQUESTED

AI Investigation Service
  └─ subscribes INVESTIGATION_REQUESTED
  └─ runs InvestigationPipeline (LLM-based)
  └─ publishes INVESTIGATION_COMPLETED

Notification Service
  └─ subscribes INVESTIGATION_COMPLETED
  └─ routes notification to Slack/Discord

Gateway Service
  └─ reads investigation data from Elasticsearch via InvestigationStore
```

---

## Consequences

### Advantages

* Long-running LLM calls do not block correlation or notification
* Investigation depth is caller-configurable (quick → standard → deep)
* Results are available in a structured, typed format
* Downstream consumers can receive results via events or query persisted data

### Tradeoffs

* The `context` field is an unstructured dict — no schema validation at the event boundary
* No retry or timeout semantics are defined for investigations that never complete
* No mechanism to cancel an in-flight investigation

---

## Future Considerations

* Add `investigation.failed` event for pipeline errors
* Add cancellation topic for long-running investigations
* Introduce schema validation for `context` payload via Pydantic
