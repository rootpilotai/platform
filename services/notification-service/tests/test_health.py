from httpx import AsyncClient


class TestHealthEndpoint:
    async def test_health_returns_healthy_when_connected(self, client: AsyncClient) -> None:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "notification-service"
        assert data["event_bus_connected"] is True

    async def test_health_returns_degraded_when_event_bus_disconnected(self, client: AsyncClient, app) -> None:
        from unittest.mock import AsyncMock

        app.state.event_bus.health = AsyncMock(return_value=False)
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["event_bus_connected"] is False

    async def test_health_includes_provider_status(self, client: AsyncClient) -> None:
        response = await client.get("/health")
        data = response.json()
        assert "providers" in data
        assert len(data["providers"]) > 0
        assert data["providers"][0]["name"] == "SlackNotificationProvider"
        assert data["providers"][0]["connected"] is True

    async def test_health_returns_valid_json_structure(self, client: AsyncClient) -> None:
        response = await client.get("/health")
        assert list(response.json().keys()) == [
            "status",
            "service",
            "environment",
            "event_bus_connected",
            "providers",
        ]
