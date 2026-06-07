# RootPilot Roadmap

## Phase 1 — Foundation

### Goals

* Repository setup
* Core architecture
* Infrastructure abstractions
* Local development environment

### Tasks

* Monorepo structure
* Docker Compose setup
* RabbitMQ integration
* Base FastAPI services
* Shared event schemas
* OpenTelemetry setup
* Initial documentation

---

## Phase 2 — Telemetry Ingestion

### Goals

* Collect logs/events
* Normalize telemetry

### Tasks

* Ingestion service
* OpenTelemetry ingestion
* Log normalization
* Event pipeline
* ElasticSearch integration

---

## Phase 3 — Correlation Engine

### Goals

* Contextual incident grouping
* Timeline reconstruction

### Tasks

* Correlation engine
* Service dependency mapping
* Failure propagation analysis
* Temporal correlation logic

---

## Phase 4 — AI Investigation Engine

### Goals

* AI-powered RCA workflows

### Tasks

* LangGraph workflows
* Context assembly pipeline
* Root cause analysis prompts
* Incident summarization
* Remediation suggestions
* Confidence scoring

---

## Phase 5 — Incident Orchestration

### Goals

* Manage investigations

### Tasks

* Incident lifecycle
* RCA report generation
* Investigation history
* Streaming investigation updates

---

## Phase 6 — Kubernetes & Cloud-Native Integrations

### Goals

* Production-grade observability integration

### Tasks

* Kubernetes event ingestion
* Pod failure analysis
* Deployment correlation
* Namespace-level investigations

---

## Phase 7 — Platform Hardening

### Goals

* Production-grade architecture

### Tasks

* Authentication
* RBAC
* Rate limiting
* Retry strategies
* Circuit breakers
* Backpressure handling

---

## Future Exploration

* Autonomous remediation
* AI-assisted deployment analysis
* Multi-cloud support
* Vector memory systems
* Anomaly prediction
* SRE copilots
* Slack/Discord integrations
