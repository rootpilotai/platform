# ADR-003: Provider Abstraction Boundaries

## Status

Accepted

---

## Context

RootPilot is intended to remain provider-agnostic across messaging, AI providers, telemetry stores, databases, and infrastructure APIs.

Direct provider usage in business services would make future replacements expensive and would weaken service boundaries.

---

## Decision

Core business logic will depend on shared interfaces and typed contracts.

Concrete provider implementations belong under `infrastructure/`.

Examples of provider abstractions include:

* `EventBus`
* `LLMProvider`
* `LogStore`
* `VectorStore`
* `IncidentRepository`

---

## Consequences

### Advantages

* Provider replacement remains practical
* Business logic is easier to test
* Infrastructure concerns stay isolated
* Service contracts become explicit

### Tradeoffs

* Requires upfront interface design
* Can add ceremony if abstractions are introduced before real use cases

---

## Guidance

Add abstractions when there is a clear provider boundary or testability need. Avoid speculative abstractions that do not yet protect real business logic.
