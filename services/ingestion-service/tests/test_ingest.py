from httpx import AsyncClient


class TestIngestEndpoint:
    async def test_ingest_telemetry_returns_accepted(self, client: AsyncClient) -> None:
        payload = {
            "metric": "cpu.usage",
            "value": 75.5,
            "unit": "%",
            "tags": {"host": "web-01", "region": "us-east-1"},
            "source": "web-service",
        }
        response = await client.post("/api/v1/ingest", json=payload)
        assert response.status_code == 202
        data = response.json()
        assert data["accepted"] is True
        assert len(data["event_id"]) > 0

    async def test_ingest_publishes_event_to_bus(self, client: AsyncClient, mock_event_bus) -> None:
        payload = {
            "metric": "mem.usage",
            "value": 4096.0,
            "unit": "MB",
            "tags": {"host": "db-01"},
            "source": "db-service",
        }
        await client.post("/api/v1/ingest", json=payload)
        mock_event_bus.publish.assert_awaited_once()
        call_args = mock_event_bus.publish.await_args[0][0]
        assert call_args.topic == "telemetry.ingested"
        assert call_args.payload["metric"] == "mem.usage"
        assert call_args.payload["value"] == 4096.0

    async def test_ingest_with_minimal_payload(self, client: AsyncClient) -> None:
        payload = {"metric": "requests.count", "value": 100, "source": "api"}
        response = await client.post("/api/v1/ingest", json=payload)
        assert response.status_code == 202
        data = response.json()
        assert data["accepted"] is True

    async def test_ingest_rejects_missing_required_fields(self, client: AsyncClient) -> None:
        payload = {"metric": "cpu"}
        response = await client.post("/api/v1/ingest", json=payload)
        assert response.status_code == 422

    async def test_ingest_rejects_empty_body(self, client: AsyncClient) -> None:
        response = await client.post("/api/v1/ingest", json={})
        assert response.status_code == 422

    async def test_ingest_rejects_non_numeric_value(self, client: AsyncClient) -> None:
        payload = {"metric": "cpu", "value": "high", "source": "test"}
        response = await client.post("/api/v1/ingest", json=payload)
        assert response.status_code == 422

    async def test_ingest_includes_trace_context(self, client: AsyncClient, mock_event_bus) -> None:
        payload = {
            "metric": "error.rate",
            "value": 0.15,
            "source": "api",
            "trace_id": "abc123",
            "span_id": "def456",
            "parent_span_id": "parent789",
            "request_id": "req-001",
            "severity": "error",
        }
        response = await client.post("/api/v1/ingest", json=payload)
        assert response.status_code == 202
        call_args = mock_event_bus.publish.await_args[0][0]
        pl = call_args.payload
        assert pl["trace_id"] == "abc123"
        assert pl["span_id"] == "def456"
        assert pl["parent_span_id"] == "parent789"
        assert pl["request_id"] == "req-001"
        assert pl["severity"] == "error"

    async def test_ingest_trace_fields_default_to_none(self, client: AsyncClient, mock_event_bus) -> None:
        payload = {"metric": "cpu.usage", "value": 95.0, "source": "api"}
        response = await client.post("/api/v1/ingest", json=payload)
        assert response.status_code == 202
        call_args = mock_event_bus.publish.await_args[0][0]
        pl = call_args.payload
        assert pl["trace_id"] is None
        assert pl["span_id"] is None
        assert pl["parent_span_id"] is None
        assert pl["request_id"] is None
        assert pl["severity"] is None

    async def test_ingest_accepts_optional_timestamp(self, client: AsyncClient) -> None:
        payload = {
            "metric": "latency",
            "value": 150.0,
            "unit": "ms",
            "source": "api-gateway",
            "timestamp": "2026-06-12T10:00:00+00:00",
        }
        response = await client.post("/api/v1/ingest", json=payload)
        assert response.status_code == 202

    async def test_ingest_handles_concurrent_requests(self, client: AsyncClient) -> None:
        import asyncio

        payload = {"metric": "cpu", "value": 50.0, "source": "test"}
        responses = await asyncio.gather(*[client.post("/api/v1/ingest", json=payload) for _ in range(5)])
        for resp in responses:
            assert resp.status_code == 202
