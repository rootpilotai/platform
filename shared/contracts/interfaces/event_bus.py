"""Event bus abstraction for provider-agnostic async messaging."""

from abc import ABC, abstractmethod
from collections.abc import Coroutine
from typing import Any, Callable

from shared.contracts.events.base import Event

EventHandler = Callable[[Event], Coroutine[Any, Any, None]]


class EventBus(ABC):
    @abstractmethod
    async def publish(self, event: Event, topic: str | None = None) -> None: ...

    @abstractmethod
    async def subscribe(self, topic: str, handler: EventHandler) -> None: ...

    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def close(self) -> None: ...
