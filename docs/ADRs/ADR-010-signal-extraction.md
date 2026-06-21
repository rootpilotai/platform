# ADR-010: Signal Extraction Layer for Telemetry Filtering

## Status

Accepted

---

## Context

The telemetry ingestion pipeline forwards every OTLP event (trace spans, logs, metrics) from the OpenTelemetry demo into RabbitMQ. During normal operation this produces healthy traffic — 200s, INFO logs, routine CPU/memory metrics — that the correlation service must process, buffer, and discard.

In practice this meant:

* Hundreds of thousands of low-signal events accumulated in the `telemetry.ingested` queue
* The correlation service was CPU-bound classifying and discarding healthy telemetry
* The AI investigation service was receiving noisy incident context from healthy traffic
* The ingestion bottleneck made it impossible to distinguish "no incidents" from "system is overwhelmed"

The core question was: should every telemetry event reach the business logic, or should filtering happen as early as possible?

---

## Decision

Introduce a **SignalExtraction layer** inside the `otel-adapter-service` that classifies each normalized telemetry event into one of four categories:

| Category | Meaning | Action |
|---|---|---|
| `HEALTH_CHECK` | Normal operation (2xx, INFO logs, routine metrics) | **Drop** — not published to queue |
| `FAILURE` | Error condition (5xx, ERROR/CRITICAL logs, error metrics) | **Promote** — published to queue |
| `DEPENDENCY_FAILURE` | Downstream dependency error | **Promote** — published to queue |
| `METRIC_ANOMALY` | Latency violation or anomalous value | **Promote** — published to queue |

The layer sits between the `OtelNormalizer` and the RabbitMQ publisher, operating on already-normalized `TelemetryEvent` objects. It uses the `__otel_category__` attribute set by the normalizer during trace/log/metric parsing.

Additionally, self-monitoring telemetry from the `otelcol-contrib` collector is dropped entirely — it contributes no signal about the target system.

The `SignalExtractor` is instantiated in `create_app()` and injected into the OTLP router. Per-event counters (`received`, `dropped`, `promoted`) are tracked to assess reduction ratios.

---

## Consequences

### Advantages

* Dramatic queue reduction — healthy demo traffic is filtered before reaching RabbitMQ
* Correlation service only sees real anomalies, reducing CPU and memory pressure
* AI investigations are scoped to actual failure signals
* Preserves the ability to detect "zero failures" vs. "overwhelmed pipeline"
* Extraction rules live in one place and are testable independently
* Counters provide operational visibility into filtering effectiveness

### Tradeoffs

* Adds latency to the OTLP ingestion path (classification is already done by the normalizer, so the overhead is a single attribute lookup)
* If extraction rules are too aggressive, real failure signals could be dropped
* If extraction rules are too permissive, queue pressure returns
* The category heuristic (`__otel_category__`) is based on span status codes, log severity, and metric name patterns — not semantic understanding

---

## Future Considerations

* Extraction rules could be made configurable per-deployment (e.g., environment-specific filter thresholds)
* A separate signal extraction service could be extracted if the rules grow complex enough to warrant independent scaling
* ML-based classification could replace heuristic categories once enough labeled telemetry data exists
