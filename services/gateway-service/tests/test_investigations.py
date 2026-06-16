import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_investigations_empty(
    client: AsyncClient,
    mock_api_key_store: object,
) -> None:
    response = await client.get(
        "/investigations",
        headers={"Authorization": "Bearer test-key"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_get_investigation_by_incident_not_found(
    client: AsyncClient,
    mock_investigation_store: object,
    mock_api_key_store: object,
) -> None:
    from unittest.mock import AsyncMock

    mock_investigation_store.get_by_incident = AsyncMock(return_value=None)  # type: ignore[attr-defined]

    response = await client.get(
        "/investigations/non-existent",
        headers={"Authorization": "Bearer test-key"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_investigation_by_incident_found(
    client: AsyncClient,
    mock_investigation_store: object,
    mock_api_key_store: object,
    sample_investigation_result: object,
) -> None:
    from unittest.mock import AsyncMock

    mock_investigation_store.get_by_incident = AsyncMock(  # type: ignore[attr-defined]
        return_value=sample_investigation_result,
    )

    response = await client.get(
        "/investigations/inc-001",
        headers={"Authorization": "Bearer test-key"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["incident_id"] == "inc-001"
    assert data["title"] == "High CPU on api-gateway"
    assert len(data["root_causes"]) == 1
    assert data["root_causes"][0]["service"] == "api-gateway"
    assert data["overall_confidence"] == 0.92
    assert data["duration_ms"] == 1500.0


@pytest.mark.asyncio
async def test_get_latest_investigation_not_found(
    client: AsyncClient,
    mock_investigation_store: object,
    mock_api_key_store: object,
) -> None:
    from unittest.mock import AsyncMock

    mock_investigation_store.latest = AsyncMock(return_value=None)  # type: ignore[attr-defined]

    response = await client.get(
        "/investigations/latest",
        headers={"Authorization": "Bearer test-key"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_latest_investigation_found(
    client: AsyncClient,
    mock_investigation_store: object,
    mock_api_key_store: object,
    sample_investigation_result: object,
) -> None:
    from unittest.mock import AsyncMock

    mock_investigation_store.latest = AsyncMock(  # type: ignore[attr-defined]
        return_value=sample_investigation_result,
    )

    response = await client.get(
        "/investigations/latest",
        headers={"Authorization": "Bearer test-key"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["incident_id"] == "inc-001"


@pytest.mark.asyncio
async def test_investigations_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/investigations")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_investigations_rejects_bad_key(
    client: AsyncClient,
    mock_api_key_store: object,
) -> None:
    from unittest.mock import AsyncMock

    mock_api_key_store.validate = AsyncMock(return_value=False)  # type: ignore[attr-defined]
    response = await client.get(
        "/investigations",
        headers={"Authorization": "Bearer bad-key"},
    )
    assert response.status_code == 401
