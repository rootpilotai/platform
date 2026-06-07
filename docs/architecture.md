# RootPilot Architecture

## High-Level Architecture

RootPilot follows a modular microservice architecture with event-driven communication and provider-agnostic infrastructure abstractions.

The system is designed around:

* observability ingestion
* contextual correlation
* AI investigation workflows
* incident orchestration

---

## Core Components

### 1. Ingestion Service

Responsible for:

* collecting logs
* consuming traces
* ingesting metrics/events
* normalizing telemetry data

Supported sources (planned):

* OpenTelemetry
* Kubernetes events
* Docker logs
* Elasticsearch
* Loki
* external observability systems

---

### 2. Correlation Service

Responsible for:

* grouping related incidents
* correlating telemetry across services
* identifying cascading failures
* reconstructing timelines

This service acts as the contextual intelligence layer.

---

### 3. AI Investigation Service

Responsible for:

* root cause analysis
* contextual reasoning
* summarization
* remediation generation
* investigation workflows

This service interfaces with LLM providers through abstraction layers.

Planned providers:

* OpenAI
* Anthropic
* Ollama/local models

---

### 4. Incident Service

Responsible for:

* incident lifecycle management
* incident state tracking
* investigation orchestration
* report generation

---

### 5. Gateway Service

Responsible for:

* API aggregation
* external access
* authentication (future)
* routing
* streaming responses

---

## Architecture Principles

### Modular Infrastructure

All infrastructure providers must be abstracted behind interfaces.

Examples:

* Event Bus Interface
* Vector Store Interface
* LLM Provider Interface
* Log Storage Interface

This allows future provider replacement without rewriting business logic.

---

### Event-Driven Communication

Internal services communicate asynchronously through an event bus.

Initial provider:

* RabbitMQ

Future providers:

* Kafka
* NATS

---

### Provider-Agnostic Design

RootPilot should avoid direct coupling to:

* messaging systems
* vector databases
* AI providers
* telemetry stores

Business logic must remain infrastructure-independent.

---

## Initial Tech Stack

### Backend

* Python
* FastAPI
* AsyncIO

### Messaging

* RabbitMQ

### Observability

* OpenTelemetry

### Storage

* PostgreSQL
* ElasticSearch

### AI

* LangGraph
* OpenAI APIs

### Infrastructure

* Docker
* Kubernetes

---

## Planned Repository Structure

```text
services/
shared/
infrastructure/
docs/
scripts/
```

---

## Deployment Strategy

Initial deployment:

* Docker Compose

Future deployment:

* Kubernetes
* Helm charts
* cloud-native deployment models

---

## Observability Strategy

RootPilot itself must be observable.

The platform should expose:

* logs
* traces
* metrics
* health checks

OpenTelemetry will be integrated internally from early development stages.

---

## Long-Term Architectural Goals

* Agentic investigation workflows
* AI memory/context systems
* Multi-cluster observability
* Distributed tracing intelligence
* Autonomous remediation orchestration
