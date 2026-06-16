import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_incidents_empty(
    client: AsyncClient,
    mock_api_key_store: object,
) -> None:
    response = await client.get(
        "/incidents",
        headers={"Authorization": "Bearer test-key"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_get_incident_not_found(
    client: AsyncClient,
    mock_incident_store: object,
    mock_api_key_store: object,
) -> None:
    from unittest.mock import AsyncMock

    mock_incident_store.get = AsyncMock(return_value=None)  # type: ignore[attr-defined]

    response = await client.get(
        "/incidents/non-existent",
        headers={"Authorization": "Bearer test-key"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_incident_found(
    client: AsyncClient,
    mock_incident_store: object,
    mock_api_key_store: object,
    sample_incident_context: dict,
) -> None:
    from unittest.mock import AsyncMock

    from shared.domain.incident.context.models import IncidentContext

    context = IncidentContext(**sample_incident_context)
    mock_incident_store.get = AsyncMock(return_value=context)  # type: ignore[attr-defined]

    response = await client.get(
        "/incidents/inc-001",
        headers={"Authorization": "Bearer test-key"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["incident_id"] == "inc-001"
    assert data["primary_service"] == "api-gateway"
    assert data["severity"] == "CRITICAL"


@pytest.mark.asyncio
async def test_incidents_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/incidents")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_incidents_rejects_bad_key(
    client: AsyncClient,
    mock_api_key_store: object,
) -> None:
    from unittest.mock import AsyncMock

    mock_api_key_store.validate = AsyncMock(return_value=False)  # type: ignore[attr-defined]
    response = await client.get(
        "/incidents",
        headers={"Authorization": "Bearer bad-key"},
    )
    assert response.status_code == 401
