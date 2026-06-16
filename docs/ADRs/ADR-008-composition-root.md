# ADR-008: Composition Root and Dependency Inversion

## Status

Accepted

---

## Context

RootPilot follows a layered architecture where business services depend on interfaces, not concrete providers. However, at startup, every service must wire concrete implementations (RabbitMQ, Elasticsearch, OpenAI) into the application.

The architectural question is: where and how does this wiring happen?

Choices considered:

* service locator / global registry
* dependency injection framework
* manual composition at the application entry point

Additionally, services vary in their wiring needs:

* some services need an event bus (correlation, investigation, notification)
* some need persistence stores (gateway)
* some need both LLM providers and event buses (investigation)

---

## Decision

RootPilot uses a **composition root** pattern: a thin `run.py` entry point that manually wires concrete infrastructure into a `create_app()` factory. No DI framework is used.

### Pattern

```python
# run.py — composition root
async def _create_rabbitmq_bus(url: str) -> EventBus:
    config = RabbitMQConfig(url=url)
    bus = RabbitMQEventBus(config=config)
    await bus.start()
    return bus

app = create_app(event_bus_factory=_create_rabbitmq_bus)
```

```python
# app/main.py — service factory
def create_app(event_bus_factory: EventBusFactory | None = None) -> FastAPI:
    app = FastAPI(...)
    app.state._event_bus_factory = event_bus_factory
    # ... routers, middleware ...
    return app
```

```python
# lifespan
async def lifespan(app):
    settings = load_settings(Settings)
    factory = getattr(app.state, "_event_bus_factory", None)
    if factory:
        event_bus = await factory(settings.event_bus_url)
        app.state.event_bus = event_bus
    yield
    if event_bus:
        await event_bus.close()
```

### Variations

| Service | `run.py` | Wired Dependencies |
|---|---|---|
| ingestion-service | None (direct in main.py) | `RabbitMQEventBus` |
| correlation-service | Yes | `RabbitMQEventBus` |
| ai-investigation-service | Yes | `RabbitMQEventBus`, `OpenAILLMProvider` |
| notification-service | Yes | `RabbitMQEventBus`, `SlackNotificationProvider`, `DiscordNotificationProvider` |
| gateway-service | None | `ElasticsearchIncidentStore`, `ElasticsearchInvestigationStore`, `EnvironmentApiKeyStore` |

### Principles

1. **The `create_app()` factory never imports concrete infrastructure.** It receives factories or already-initialized objects.
2. **`run.py` is the only file that imports both business code and infrastructure.** It is the explicit dependency inversion boundary.
3. **No global state.** Wired dependencies live on `app.state` and are accessed via FastAPI `Depends()`.
4. **No DI framework.** Manual composition keeps the wiring explicit, debuggable, and framework-independent.

---

## Consequences

### Advantages

* Business code never imports RabbitMQ, Elasticsearch, or OpenAI directly
* Testing is straightforward — create the app with mocks instead of real factories
* No DI framework lock-in or magic
* Wiring is visible in a single small file per service
* Each service only pays for the dependencies it needs

### Tradeoffs

* Manual wiring requires boilerplate — each new dependency needs a factory or direct initialization
* No automatic lifecycle management — `start()` and `close()` must be called explicitly in `lifespan`
* Inconsistency across services (ingestion-service and gateway-service wire directly in main.py instead of using run.py)
* The LLM provider in ai-investigation-service is instantiated directly in lifespan rather than via a factory, breaking the pure composition root pattern

---

## Guidance

* New services should follow the `run.py` + `create_app(factory)` pattern established by correlation-service
* Direct instantiation in `main.py` (as ingestion-service does) is acceptable for simple services but should be avoided when possible
* Factories should be async callables so connection setup can happen during `lifespan`
