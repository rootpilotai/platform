# RootPilot

> **Autonomous Incident Investigation Platform**

RootPilot is an event-driven platform that transforms distributed telemetry into AI-assisted incident investigations.

Instead of helping engineers collect more telemetry, RootPilot focuses on the next problem: understanding **why an incident happened**.

It integrates with existing observability ecosystems, correlates operational signals across services, reconstructs failure timelines, and generates structured root cause investigations with confidence scoring and remediation suggestions.

---

# Why RootPilot?

Modern cloud-native systems already produce enormous amounts of telemetry through platforms such as OpenTelemetry, Elasticsearch, Grafana, Prometheus, and cloud-native observability stacks.

The challenge is no longer collecting data.

The challenge is investigating incidents.

When an outage occurs, engineers must manually:

* correlate logs, traces, and metrics
* reconstruct request flows
* identify affected services
* validate hypotheses
* determine the most probable root cause

RootPilot automates this investigation workflow using an event-driven architecture and AI-assisted operational intelligence.

---

# Current Architecture

```text
Applications / Services
        │
        ▼
OpenTelemetry Collector
        │
        ▼
OTEL Adapter Service
(Normalization + Signal Extraction)
        │
        ▼
RabbitMQ (telemetry.ingested)
        │
        ▼
Correlation Service
        │
RabbitMQ (investigation.requested)
        │
        ▼
AI Investigation Service
        │
        ├──────────────► Elasticsearch
        │               (Incidents & Investigations)
        │
        ▼
RabbitMQ (investigation.completed)
        │
        ▼
Notification Service
(Slack / Discord)

Gateway Service
        │
        ▼
Search & Investigation APIs
```

---

# Core Features

* OpenTelemetry ingestion
* Event-driven microservices
* Distributed telemetry correlation
* Timeline reconstruction
* AI-powered root cause analysis
* Elasticsearch-backed investigation history
* Gateway APIs secured with API keys
* Slack and Discord notifications
* Provider abstractions for AI, messaging, storage, and notifications
* Docker-based local development environment

---

# Design Principles

## Event-Driven First

All platform components communicate asynchronously through RabbitMQ.

This enables independent scaling of ingestion, correlation, AI investigation, persistence, and notification services.

---

## Provider Agnostic

Infrastructure providers are abstracted behind interfaces.

Examples:

* RabbitMQ → Kafka
* OpenAI → Anthropic / local models
* Elasticsearch → alternative storage providers
* Slack → Teams / Email / PagerDuty

This keeps the platform independent of vendor-specific implementations.

---

## AI Investigates Incidents — Not Raw Telemetry

One of the key architectural learnings from validating against the OpenTelemetry Demo environment was that AI should not process every telemetry event.

Instead:

```text
Raw Telemetry
      │
      ▼
Signal Extraction
      │
      ▼
Correlation
      │
      ▼
Incident Context
      │
      ▼
AI Investigation
```

The signal extraction layer reduces operational noise before correlation, allowing the investigation pipeline to focus only on meaningful operational signals.

---

# Repository Structure

```text
services/
├── ai-investigation-service
├── correlation-service
├── gateway-service
├── ingestion-service
├── notification-service
└── otel-adapter-service

shared/
infrastructure/
docs/
scripts/
```

---

# Technology Stack

## Backend

* Python
* FastAPI
* AsyncIO

## Messaging

* RabbitMQ

## Observability

* OpenTelemetry
* Elasticsearch

## Infrastructure

* Docker
* Docker Compose

## AI

* OpenAI-compatible provider abstraction

---

# Development

RootPilot targets Python 3.13.

Create a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Run tests:

```bash
pytest
```

Or start the local development environment:

```bash
docker compose up
```

---

# Documentation

Project documentation is located under:

```text
docs/
```

including:

* Vision
* Architecture
* Configuration
* Roadmap
* Architecture Decision Records (ADRs)

The ADR collection documents important architectural decisions, trade-offs, and lessons learned throughout the project's evolution.

---

# Current Status

Current capabilities include:

* ✅ OpenTelemetry integration
* ✅ Event-driven investigation workflow
* ✅ Distributed telemetry correlation
* ✅ AI-powered incident investigation
* ✅ Elasticsearch persistence
* ✅ Gateway APIs
* ✅ Slack & Discord notifications

Active areas of development:

* 🚧 Signal extraction refinement
* 🚧 Correlation quality improvements
* 🚧 Production observability connectors
* 🚧 Topology-aware investigations

---

# License

Apache 2.0
