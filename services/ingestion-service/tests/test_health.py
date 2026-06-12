from fastapi import FastAPI
from httpx import AsyncClient


class TestHealthEndpoint:
    async def test_health_returns_healthy_when_event_bus_connected(
        self, client: AsyncClient
    ) -> None:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "ingestion-service"
        assert data["environment"] == "test"
        assert data["event_bus_connected"] is True

    async def test_health_returns_degraded_when_event_bus_disconnected(
        self, client: AsyncClient, app: FastAPI
    ) -> None:
        from unittest.mock import AsyncMock

        app.state.event_bus.health = AsyncMock(return_value=False)
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["event_bus_connected"] is False

    async def test_health_returns_valid_json_structure(self, client: AsyncClient) -> None:
        response = await client.get("/health")
        assert response.status_code == 200
        assert list(response.json().keys()) == [
            "status",
            "service",
            "environment",
            "event_bus_connected",
        ]
