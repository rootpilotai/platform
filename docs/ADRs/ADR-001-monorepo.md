# ADR-001: Monorepo Architecture

## Status

Accepted

---

## Context

RootPilot is designed as a modular microservice platform.

The project requires:

* shared contracts
* infrastructure consistency
* rapid iteration
* centralized documentation
* simplified onboarding

A repository strategy decision was required.

---

## Decision

RootPilot will use a monorepo architecture.

All services, shared libraries, infrastructure definitions, and documentation will initially reside in a single repository.

---

## Consequences

### Advantages

* Simplified development workflow
* Easier dependency management
* Centralized architecture visibility
* Unified CI/CD
* Easier local development
* Better onboarding experience

### Tradeoffs

* Larger repository size over time
* Shared release coordination
* Potential future scaling complexity

---

## Future Considerations

If repository scale becomes problematic, selected components may later be extracted into dedicated repositories.

Examples:

* SDKs
* Helm charts
* shared tooling
* public client libraries

Current priority is engineering velocity and architectural consistency.
