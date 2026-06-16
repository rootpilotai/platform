"""Environment-variable-based API key store implementation.

Validates API keys from a comma-separated environment variable
(e.g., ``ROOTPILOT_API_KEYS=key1,key2,key3``).

Designed as a lightweight MVP that can be replaced with a database-backed
implementation via the ``ApiKeyStore`` abstraction without changing
consumer code.
"""

from __future__ import annotations

import logging

from shared.contracts.interfaces.api_key_store import ApiKeyStore

logger = logging.getLogger(__name__)


class EnvironmentApiKeyStore(ApiKeyStore):
    """ApiKeyStore that validates against keys from an environment variable.

    Keys are loaded at initialization and kept in memory. Key rotation
    requires a service restart.

    .. note::

       This implementation does NOT hash the keys — the env var itself
       serves as the secret store. For production use, migrate to a
       database-backed store with hashed keys.
    """

    def __init__(self, api_keys_csv: str = "") -> None:
        self._valid_keys: set[str] = set()
        if api_keys_csv:
            self._valid_keys = {k.strip() for k in api_keys_csv.split(",") if k.strip()}
            logger.info("EnvironmentApiKeyStore initialized", extra={"key_count": len(self._valid_keys)})
        else:
            logger.warning("EnvironmentApiKeyStore initialized with no keys — all requests will be rejected")

    async def validate(self, api_key: str) -> bool:
        return api_key in self._valid_keys

    async def health(self) -> bool:
        return len(self._valid_keys) > 0
