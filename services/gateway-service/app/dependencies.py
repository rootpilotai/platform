"""Gateway service dependencies — FastAPI Depends() for store access and auth."""

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import GatewayServiceSettings
from shared.contracts.interfaces.api_key_store import ApiKeyStore
from shared.contracts.interfaces.incident_store import IncidentStore
from shared.contracts.interfaces.investigation_store import InvestigationStore

_bearer_scheme = HTTPBearer(auto_error=False)


def get_settings(request: Request) -> GatewayServiceSettings:
    return request.app.state.settings


def get_incident_store(request: Request) -> IncidentStore:
    return request.app.state.incident_store


def get_investigation_store(request: Request) -> InvestigationStore:
    return request.app.state.investigation_store


def get_api_key_store(request: Request) -> ApiKeyStore:
    return request.app.state.api_key_store


async def require_api_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    api_key_store: ApiKeyStore = Depends(get_api_key_store),
) -> None:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )
    valid = await api_key_store.validate(credentials.credentials)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
