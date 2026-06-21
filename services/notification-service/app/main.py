"""Notification service — consumes investigation lifecycle events and routes notifications."""

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import NotificationServiceSettings
from app.routers import health
from app.services.provider_router import NotificationRouter
from shared.config import BaseAppSettings, load_settings
from shared.contracts import Event, EventBus, ObservabilityProvider
from shared.contracts.events import EventTopic, InvestigationCompletedEvent
from shared.contracts.schemas.notification import NotificationMessage

logger = logging.getLogger(__name__)

DEAD_LETTER_TOPIC = EventTopic.NOTIFICATION_DEAD_LETTER
_MIN_CONFIDENCE_FOR_NOTIFICATION = 0.1

EventBusFactory = Callable[[str], Awaitable[EventBus]]
NotificationRouterFactory = Callable[[], NotificationRouter]
ObservabilityFactory = Callable[[BaseAppSettings], ObservabilityProvider]


def _build_notification(event: Event) -> NotificationMessage | None:
    try:
        payload = InvestigationCompletedEvent(**event.payload)
    except Exception:
        logger.exception("Failed to parse investigation.completed payload")
        return None

    summary = payload.summary or {}
    overall_confidence = summary.get("overall_confidence", 0.0)

    if overall_confidence < _MIN_CONFIDENCE_FOR_NOTIFICATION:
        logger.debug(
            "Suppressing notification — overall_confidence %.2f below threshold %.1f (incident=%s)",
            overall_confidence,
            _MIN_CONFIDENCE_FOR_NOTIFICATION,
            payload.incident_id,
        )
        return None

    title = summary.get("title", "Investigation Completed")
    incident_id = payload.incident_id

    fields = {
        "Incident ID": incident_id,
        "Investigation ID": payload.investigation_id,
        "Confidence": f"{summary.get('overall_confidence', 'N/A')}",
    }

    root_causes = summary.get("root_causes", [])
    if root_causes:
        causes = [
            f"• {rc.get('service', '?')} ({rc.get('confidence', 0)}): {rc.get('explanation', '')[:120]}"
            for rc in root_causes[:3]
        ]
        body = "\n".join(causes)
    else:
        body = "No root causes identified."

    return NotificationMessage(
        topic=event.topic,
        title=title,
        body=body,
        fields=fields,
        severity=(summary.get("overall_confidence", 0.5) > 0.7 and "critical") or "warning",
        source=event.source,
    )


def _noop_observability(_settings: BaseAppSettings) -> ObservabilityProvider:
    from shared.contracts.interfaces.observability import ObservabilityProvider

    class _NoopProvider(ObservabilityProvider):
        def setup(self, app: FastAPI) -> None:
            logger.info("No observability provider configured — tracing disabled")

    return _NoopProvider()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: NotificationServiceSettings = load_settings(NotificationServiceSettings)
    app.state.settings = settings

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(levelname)s\t%(name)s\t%(message)s",
    )

    obs_factory = getattr(app.state, "_observability_factory", None)
    provider = obs_factory(settings) if obs_factory else _noop_observability(settings)
    provider.setup(app)

    factory: EventBusFactory | None = getattr(app.state, "_event_bus_factory", None)
    if factory is not None:
        event_bus = await factory(settings.event_bus_url)
        app.state.event_bus = event_bus
    else:
        logger.warning("No event bus factory configured")
        yield
        return

    router_factory = getattr(app.state, "_notification_router_factory", None)
    if router_factory is None:
        logger.warning("No notification router factory configured")
        yield
        return

    router = router_factory()
    app.state.router = router
    await router.start_all()

    async def handle_investigation_completed(event: Event) -> None:
        message = _build_notification(event)
        if message is None:
            return

        try:
            await router.route(message)
        except Exception:
            logger.exception("Notification routing failed, publishing to dead-letter")
            try:
                dead_letter = Event(
                    source=settings.service_name,
                    topic=DEAD_LETTER_TOPIC,
                    payload={
                        "original_event_id": event.id,
                        "original_topic": event.topic,
                        "error": "routing failed",
                    },
                )
                await event_bus.publish(dead_letter)
            except Exception:
                logger.exception("Failed to publish dead-letter event")

    await event_bus.subscribe(EventTopic.INVESTIGATION_COMPLETED, handle_investigation_completed)
    logger.info("Subscribed to investigation.completed")

    logger.info("Service started", extra={"service": settings.service_name})
    yield

    router = getattr(app.state, "router", None)
    if router is not None:
        await router.stop_all()
    await event_bus.close()
    logger.info("Service stopped", extra={"service": settings.service_name})


def create_app(
    event_bus_factory: EventBusFactory | None = None,
    notification_router_factory: NotificationRouterFactory | None = None,
    observability_factory: ObservabilityFactory | None = None,
) -> FastAPI:
    app = FastAPI(
        title="notification-service",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state._event_bus_factory = event_bus_factory
    app.state._notification_router_factory = notification_router_factory
    app.state._observability_factory = observability_factory
    app.include_router(health.router)
    return app


app = create_app()
