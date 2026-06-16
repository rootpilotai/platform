# ADR-004: Event-Driven Service Communication

## Status

Accepted

---

## Context

RootPilot consists of multiple services that must collaborate to ingest telemetry, correlate incidents, run AI investigations, and deliver notifications.

The platform initially chose RabbitMQ as the concrete messaging provider, but the architectural question was broader: should services communicate synchronously through HTTP APIs, or asynchronously through events?

Key driving concerns:

* services should evolve independently
* telemetry ingestion must not block on downstream processing
* AI investigation workflows are inherently asynchronous (LLM calls take seconds)
* the platform must support future provider swapping without service rewrites

---

## Decision

RootPilot services will communicate primarily through asynchronous events published to an `EventBus` abstraction.

Synchronous HTTP communication is reserved for:

* external API access (gateway-service)
* health checks
* administrative operations

### Event Topology

All internal events flow through a single topic exchange (`rootpilot.events`) with topic-based routing. Each event carries a source, topic, typed payload, trace context, and unique identifier.

### Defined Event Topics

| Topic | Publisher | Consumer(s) | Purpose |
|---|---|---|---|
| `telemetry.ingested` | ingestion-service | correlation-service | Raw telemetry received |
| `incident.detected` | correlation-service | — | Incident identified |
| `investigation.requested` | correlation-service | ai-investigation-service | Trigger RCA pipeline |
| `investigation.completed` | ai-investigation-service | notification-service | RCA results ready |
| `notification.dead-letter` | notification-service | — | Notification delivery failure |

### Choreography, Not Orchestration

Services react to events and produce new events without a central coordinator. No service holds the complete workflow state.

---

## Consequences

### Advantages

* Services remain decoupled — failure in one does not block others
* AI investigation (high-latency) runs without blocking ingestion
* New consumers can subscribe without publisher changes
* Event topology is discoverable from a single contract file (`enums.py`)
* Trace context propagation enables end-to-end observability

### Tradeoffs

* Event-driven flows are harder to reason about than synchronous request/response
* No built-in workflow visibility — requires OpenTelemetry tracing to observe end-to-end flows
* Event ordering guarantees are at-most-once without additional infrastructure
* Dead-letter handling must be explicitly designed (only notification-service currently does this)

---

## Future Considerations

* Kafka or NATS may replace RabbitMQ by implementing the same `EventBus` interface
* Event sourcing or replay capabilities may be added for debugging and audit
* An incident-service could subscribe to `incident.detected` once implemented
