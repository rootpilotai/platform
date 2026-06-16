import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_ok(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["incident_store"] is True
    assert data["investigation_store"] is True
    assert data["api_key_store"] is True


@pytest.mark.asyncio
async def test_health_degraded(
    client: AsyncClient,
    mock_incident_store: object,
) -> None:
    from unittest.mock import AsyncMock

    mock_incident_store.health = AsyncMock(return_value=False)  # type: ignore[attr-defined]
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["incident_store"] is False


@pytest.mark.asyncio
async def test_metrics(client: AsyncClient) -> None:
    response = await client.get("/metrics")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "gateway-service"
