"""API key store abstraction for provider-agnostic API key validation."""

from abc import ABC, abstractmethod


class ApiKeyStore(ABC):
    """Abstract store for validating API keys."""

    @abstractmethod
    async def validate(self, api_key: str) -> bool:
        """Validate an API key. Returns True if the key is valid."""

    @abstractmethod
    async def health(self) -> bool:
        """Return True if the store is reachable and operational."""
