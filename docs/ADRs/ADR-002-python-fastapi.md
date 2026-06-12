# ADR-002: Python and FastAPI as Primary Backend Stack

## Status

Accepted

---

## Context

RootPilot is an AI-powered observability and incident investigation platform focused on:

* distributed systems
* telemetry correlation
* asynchronous processing
* AI investigation workflows
* cloud-native infrastructure

A backend technology stack decision was required for:

* microservices
* event-driven processing
* AI integration
* observability tooling
* infrastructure extensibility

---

## Decision

RootPilot will use:

* Python as the primary programming language
* FastAPI as the primary backend framework

for all initial services.

---

## Rationale

### AI Ecosystem Alignment

The modern AI ecosystem is heavily centered around Python.

Key frameworks and tooling used by RootPilot are Python-native:

* LangGraph
* OpenTelemetry tooling
* AI SDKs
* vector database tooling
* embedding libraries
* evaluation frameworks

Using Python reduces ecosystem friction and integration complexity.

---

### FastAPI Advantages

FastAPI was selected because it provides:

* async-first architecture
* strong typing support
* high developer velocity
* OpenAPI integration
* lightweight microservice design
* excellent developer experience

FastAPI aligns well with:

* event-driven services
* telemetry ingestion
* internal APIs
* asynchronous workflows

---

### Async Processing Requirements

RootPilot requires:

* asynchronous messaging
* concurrent telemetry processing
* distributed event handling
* streaming workflows

Python AsyncIO and FastAPI provide a strong foundation for these requirements.

---

### Engineering Velocity

The project prioritizes:

* rapid iteration
* experimentation
* modular service development
* AI workflow integration

Python enables faster implementation velocity during the early platform phases.

---

## Alternatives Considered

### Node.js

Advantages:

* strong backend performance
* existing team familiarity
* mature ecosystem

Reasons not selected:

* weaker AI ecosystem integration
* less alignment with AI tooling
* reduced compatibility with emerging AI frameworks

---

### .NET

Advantages:

* strong performance
* excellent tooling
* enterprise maturity

Reasons not selected:

* AI ecosystem less mature compared to Python
* slower iteration speed for AI-heavy workflows
* reduced community momentum in AI infrastructure tooling

---

## Consequences

### Positive

* Excellent AI ecosystem compatibility
* Faster experimentation
* Strong async support
* Easier AI integration
* Improved observability tooling support

### Tradeoffs

* Lower raw throughput compared to some alternatives
* Increased care required for async correctness
* Potential CPU-bound scaling limitations

---

## Future Considerations

Future components may introduce:

* polyglot services
* Go-based infrastructure tooling
* Rust performance-critical pipelines

However, Python remains the primary platform language for initial RootPilot development.
