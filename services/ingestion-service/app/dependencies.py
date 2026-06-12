from collections.abc import AsyncGenerator
from typing import Any

from fastapi import Request

from app.config import IngestionServiceSettings
from shared.contracts import EventBus


def get_settings(request: Request) -> IngestionServiceSettings:
    return request.app.state.settings


async def get_event_bus(request: Request) -> AsyncGenerator[EventBus, Any]:
    yield request.app.state.event_bus
