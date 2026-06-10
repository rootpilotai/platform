# RootPilot

> Autonomous Incident Investigation Platform

RootPilot is an AI-powered incident investigation platform designed for cloud-native and distributed systems.

The platform leverages observability pipelines, telemetry correlation, distributed tracing, and AI investigation workflows to analyze production incidents, identify probable root causes, and generate actionable remediation insights.

---

# Vision

Modern distributed systems generate massive amounts of:

* logs
* traces
* metrics
* deployment events
* infrastructure telemetry

During incidents, engineers spend significant time manually:

* correlating failures
* reconstructing timelines
* tracing dependencies
* validating hypotheses
* identifying root causes

RootPilot aims to automate and accelerate this investigation process using AI-assisted operational intelligence.

---

# Core Objectives

* AI-powered root cause analysis
* Distributed telemetry correlation
* Incident timeline reconstruction
* Event-driven investigation workflows
* Cloud-native observability integration
* Provider-agnostic architecture
* Production-grade engineering patterns

---

# Architecture Principles

RootPilot is intentionally designed around:

## Modular Architecture

Infrastructure providers are abstracted through interfaces to enable future extensibility.

Examples:

* RabbitMQ → Kafka
* OpenAI → Anthropic/Ollama
* Elasticsearch → alternative telemetry stores

---

## Event-Driven Communication

Internal services communicate asynchronously through messaging infrastructure.

Initial provider:

* RabbitMQ

Future support:

* Kafka
* NATS

---

## Observability-First Design

RootPilot itself is designed to be observable using:

* logs
* traces
* metrics
* health checks

OpenTelemetry integration is planned from early development stages.

---

# Planned Services

## Ingestion Service

Responsible for telemetry collection and normalization.

## Correlation Service

Responsible for contextual correlation and timeline reconstruction.

## AI Investigation Service

Responsible for root cause analysis and remediation generation.

## Incident Service

Responsible for incident orchestration and lifecycle management.

## Gateway Service

Responsible for API aggregation and external access.

---

# Initial Tech Stack

## Backend

* Python
* FastAPI
* AsyncIO

## Messaging

* RabbitMQ

## Observability

* OpenTelemetry
* Elasticsearch

## Storage

* PostgreSQL
* Elasticsearch

## AI

* LangGraph
* OpenAI APIs

## Infrastructure

* Docker
* Kubernetes

---

# Repository Structure

```text
services/
shared/
infrastructure/
docs/
scripts/
```

---

# Development Setup

RootPilot targets Python 3.13.

The expected local version is defined in:

```text
.python-version
```

Project dependencies, development dependencies, and pytest discovery are defined
in:

```text
pyproject.toml
```

Create a local virtual environment from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Run tests:

```powershell
python -m pytest
```

Run only the shared configuration tests:

```powershell
python -m pytest shared\config\tests
```

---

# Documentation

## Core Documents

* `docs/vision.md`
* `docs/architecture.md`
* `docs/configuration.md`
* `docs/roadmap.md`
* `docs/project-context.md`

---

## Architecture Decision Records (ADRs)

RootPilot maintains ADRs to document important architectural decisions and tradeoffs.

Examples:

* monorepo strategy
* messaging system selection
* infrastructure abstraction patterns
* observability standards

ADRs are located in:

```text
docs/ADRs/
```

---

# Current Status

RootPilot is currently in the foundational architecture phase.

Initial development priorities:

* repository structure
* infrastructure abstractions
* event-driven communication
* telemetry ingestion
* AI investigation workflows

---

# Long-Term Vision

Potential future capabilities:

* autonomous remediation
* Kubernetes diagnostics
* deployment impact analysis
* distributed tracing intelligence
* anomaly prediction
* multi-cluster observability
* AI-native operational intelligence

---

# Engineering Philosophy

RootPilot is intentionally:

* backend-heavy
* infrastructure-oriented
* AI-assisted
* production-minded

The goal is to build a realistic engineering platform rather than a simple AI demo or chatbot wrapper.

---

# License

Apache 2.0
