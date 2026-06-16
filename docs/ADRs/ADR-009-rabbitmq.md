# ADR-009: RabbitMQ as Initial Messaging Provider

## Status

Accepted

---

## Context

RootPilot requires asynchronous communication between services for telemetry ingestion, incident correlation, and AI investigation workflows.

The initial messaging provider should support local development, common event-driven patterns, and straightforward operational learning.

---

## Decision

RootPilot will use RabbitMQ as the initial messaging provider.

Business services must communicate through an event bus abstraction rather than depending directly on RabbitMQ clients.

---

## Consequences

### Advantages

* Mature local development story
* Management UI for debugging queues and exchanges
* Good fit for task and event workflows
* Lower operational complexity than Kafka for the initial phase

### Tradeoffs

* Not optimized for long-term event replay
* Lower throughput ceiling than Kafka for some workloads
* Provider-specific routing concepts must stay inside infrastructure implementations

---

## Future Considerations

Kafka or NATS may be added later by implementing the same event bus contracts.
