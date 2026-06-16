# ADR-006: Notification Service Architecture

## Status

Accepted

---

## Context

RootPilot must deliver incident investigation results to operations teams. The platform needs to support multiple notification channels while keeping delivery logic decoupled from channel-specific formatting.

Key considerations:

* initial channels are Slack and Discord
* additional channels (PagerDuty, email, webhook) are expected over time
* notification formatting differs significantly per channel
* notification failures must not block investigation workflows
* channels may be enabled or disabled per deployment

---

## Decision

The notification-service will use a `NotificationProvider` abstraction with a `NotificationRouter` that fans out to all enabled providers.

### Interface

```python
class NotificationProvider(ABC):
    async def start(self) -> None
    async def send(self, message: NotificationMessage) -> None
    async def health(self) -> bool
    async def close(self) -> None
```

### Message Model

`NotificationMessage` carries a `topic`, `title`, `body`, `fields` (key-value pairs), `severity`, `source`, `metadata` (for provider-specific options), and `timestamp`.

### Routing

A `NotificationRouter` holds a list of active providers (configured via settings flags `slack_enabled`, `discord_enabled`). On `send()`, it iterates every enabled provider and calls `send()` on each. Failures are logged per-provider but do not cascade; a dead-letter event (`notification.dead-letter`) is published on routing failure.

### Provider Implementations

| Provider | Transport | Key Configuration |
|---|---|---|
| Slack | `slack_sdk.AsyncWebClient` | `bot_token`, `default_channel` |
| Discord | `httpx.AsyncClient` → webhook | `webhook_url`, `username` |

### Trigger

The notification-service subscribes to `INVESTIGATION_COMPLETED`. It transforms the `InvestigationCompletedEvent` into a `NotificationMessage`, extracting the top root causes (up to 3), confidence scores, and incident metadata for the notification body.

---

## Consequences

### Advantages

* Adding a new provider requires only implementing `NotificationProvider` and adding a config flag
* Channel-specific formatting is encapsulated per provider
* Failure in one provider does not affect others
* Channels can be enabled or disabled without code changes
* Dead-letter topic provides a hook for retry or monitoring

### Tradeoffs

* No provider-specific error classification — all failures are generic
* No retry logic at the router level (relies on dead-letter for external handling)
* Each provider manages its own connection lifecycle independently

---

## Future Considerations

* Add PagerDuty provider for critical-severity alerting
* Add email provider (SMTP or SendGrid)
* Add provider priority/ordering instead of parallel fan-out
* Add retry logic with exponential backoff per provider
