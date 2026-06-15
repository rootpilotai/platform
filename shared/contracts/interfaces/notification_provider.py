"""Notification provider abstraction for provider-agnostic message delivery."""

from abc import ABC, abstractmethod

from shared.contracts.schemas.notification import NotificationMessage


class NotificationProvider(ABC):
    @abstractmethod
    async def send(self, message: NotificationMessage) -> None: ...

    @abstractmethod
    async def health(self) -> bool: ...

    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def close(self) -> None: ...
