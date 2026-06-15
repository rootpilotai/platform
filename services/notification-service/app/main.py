"""Notification service — consumes investigation lifecycle events and routes notifications."""

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import NotificationServiceSettings
from app.routers import health
from app.services.provider_router import NotificationRouter
from infrastructure.monitoring.otel import setup_tracing
from shared.config import load_settings
from shared.contracts import Event, EventBus
from shared.contracts.events import EventTopic, InvestigationCompletedEvent
from shared.contracts.schemas.notification import NotificationMessage

logger = logging.getLogger(__name__)

DEAD_LETTER_TOPIC = EventTopic.NOTIFICATION_DEAD_LETTER

EventBusFactory = Callable[[str], Awaitable[EventBus]]


def _build_notification(event: Event) -> NotificationMessage | None:
    try:
        payload = InvestigationCompletedEvent(**event.payload)
    except Exception:
        logger.exception("Failed to parse investigation.completed payload")
        return None

    summary = payload.summary or {}
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


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: NotificationServiceSettings = load_settings(NotificationServiceSettings)
    app.state.settings = settings

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(levelname)s\t%(name)s\t%(message)s",
    )

    setup_tracing(app, settings)

    factory: EventBusFactory | None = getattr(app.state, "_event_bus_factory", None)
    if factory is not None:
        event_bus = await factory(settings.event_bus_url)
        app.state.event_bus = event_bus
    else:
        logger.warning("No event bus factory configured")
        yield
        return

    router = NotificationRouter(settings)
    await router.start_all()
    app.state.router = router

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

    await router.stop_all()
    await event_bus.close()
    logger.info("Service stopped", extra={"service": settings.service_name})


def create_app(event_bus_factory: EventBusFactory | None = None) -> FastAPI:
    app = FastAPI(
        title="notification-service",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state._event_bus_factory = event_bus_factory
    app.include_router(health.router)
    return app


app = create_app()
