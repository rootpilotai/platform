# RootPilot AI Engineering Guidelines

## Project Overview

RootPilot is an autonomous incident investigation platform designed for distributed systems and cloud-native infrastructure.

The platform focuses on:

* AI-powered root cause analysis
* telemetry correlation
* observability workflows
* event-driven architecture
* provider-agnostic infrastructure

This repository is intended to reflect production-grade backend and AI engineering practices.

---

# Core Engineering Principles

## 1. Provider-Agnostic Architecture

Infrastructure providers must remain replaceable.

Business logic must never directly depend on:

* RabbitMQ
* Elasticsearch
* OpenAI
* Kubernetes APIs
* vector database implementations

Use abstraction interfaces instead.

Examples:

* EventBus
* LLMProvider
* LogStore
* VectorStore

Infrastructure implementations belong inside:

```text id="r2p0vw"
infrastructure/
```

---

## 2. Dependency Inversion

Core business services must depend on interfaces, not concrete implementations.

Avoid:

```python id="0qdujy"
rabbitmq.publish(event)
```

Prefer:

```python id="dx5m0t"
event_bus.publish(event)
```

---

## 3. Event-Driven Communication

Internal services should communicate asynchronously where appropriate.

Initial messaging provider:

* RabbitMQ

Future support:

* Kafka
* NATS

Avoid tightly coupled synchronous service communication unless necessary.

---

## 4. Observability-First Development

RootPilot itself must be observable.

New services should expose:

* structured logs
* traces
* metrics
* health checks

OpenTelemetry integration is preferred.

---

## 5. Async-First Backend Design

Prefer asynchronous implementations whenever possible.

Examples:

* async FastAPI routes
* async database access
* async messaging consumers

Avoid blocking operations in request paths.

---

## 6. Strong Typing

Prefer explicit typing and typed schemas.

Use:

* Pydantic
* dataclasses
* typed interfaces

Avoid loosely structured payloads where possible.

---

## 7. Modular Service Boundaries

Services should remain focused and composable.

Avoid:

* monolithic shared logic
* cross-service coupling
* business logic leakage between services

---

## 8. AI Workflow Discipline

LLM calls should:

* minimize hallucinations
* use contextual retrieval
* avoid unnecessary token usage
* prefer structured outputs
* support future evaluation pipelines

Prompt logic should remain modular and testable.

---

# Repository Structure

```text id="ok7vcl"
services/
shared/
infrastructure/
docs/
scripts/
```

---

# Service Responsibilities

## ingestion-service

Telemetry ingestion and normalization.

## correlation-service

Contextual incident correlation and timeline reconstruction.

## ai-investigation-service

Root cause analysis and AI investigation workflows.

## incident-service

Incident orchestration and lifecycle management.

## gateway-service

API aggregation and external access.

---

# Initial Stack

## Backend

* Python
* FastAPI

## Messaging

* RabbitMQ

## Storage

* PostgreSQL
* Elasticsearch

## Observability

* OpenTelemetry

## AI

* LangGraph
* OpenAI APIs

## Infrastructure

* Docker
* Kubernetes

---

# Testing

Service tests must be run from each service's directory (not from the project root) due to sys.path isolation:

```text
cd services/ingestion-service && python -m pytest
cd services/correlation-service && python -m pytest
```

Shared and infrastructure tests can run from the project root:

```text
python -m pytest shared/ infrastructure/
```

---

# Development Guidelines

## Prefer:

* clean architecture
* interface-driven design
* modular services
* reusable abstractions
* explicit contracts
* configuration-driven providers

## Avoid:

* hardcoded provider logic
* premature optimization
* unnecessary framework complexity
* tightly coupled implementations

---

# Current Development Phase

Current focus:

* architecture foundation
* infrastructure abstractions
* messaging layer
* telemetry ingestion
* AI investigation workflows

Frontend/UI concerns are secondary.

---

# Long-Term Direction

Potential future capabilities:

* autonomous remediation
* deployment impact analysis
* Kubernetes diagnostics
* distributed tracing intelligence
* anomaly prediction
* multi-cloud observability
* AI-native operational tooling
