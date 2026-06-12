from httpx import AsyncClient


class TestHealthEndpoint:
    async def test_health_returns_healthy(self, client: AsyncClient) -> None:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "correlation-service"
        assert data["environment"] == "test"

    async def test_health_returns_valid_json_structure(self, client: AsyncClient) -> None:
        response = await client.get("/health")
        assert response.status_code == 200
        assert list(response.json().keys()) == [
            "status",
            "service",
            "environment",
        ]
