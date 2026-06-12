from httpx import AsyncClient


class TestCorrelateEndpoint:
    async def test_correlate_two_trace_linked_events(self, client: AsyncClient) -> None:
        ts = "2026-06-12T10:00:00+00:00"
        payload = {
            "events": [
                {
                    "event_id": "e1",
                    "category": "failure",
                    "source": "telemetry",
                    "timestamp": ts,
                    "service_name": "api",
                    "title": "error spike",
                    "trace_id": "trace-1",
                },
                {
                    "event_id": "e2",
                    "category": "failure",
                    "source": "telemetry",
                    "timestamp": ts,
                    "service_name": "api",
                    "title": "timeout spike",
                    "trace_id": "trace-1",
                },
            ],
        }
        response = await client.post("/api/v1/correlate", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["total_events"] == 2
        assert len(data["groups"]) == 1
        assert set(data["groups"][0]["event_ids"]) == {"e1", "e2"}

    async def test_correlate_ungrouped_events(self, client: AsyncClient) -> None:
        ts = "2026-06-12T10:00:00+00:00"
        payload = {
            "events": [
                {
                    "event_id": "e1",
                    "category": "metric_anomaly",
                    "source": "telemetry",
                    "timestamp": ts,
                    "service_name": "api",
                    "title": "cpu spike",
                },
                {
                    "event_id": "e2",
                    "category": "metric_anomaly",
                    "source": "telemetry",
                    "timestamp": "2026-06-12T10:10:00+00:00",
                    "service_name": "db",
                    "title": "mem spike",
                },
            ],
        }
        response = await client.post("/api/v1/correlate", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["total_events"] == 2
        assert len(data["groups"]) == 0
        assert set(data["ungrouped_event_ids"]) == {"e1", "e2"}

    async def test_correlate_min_score_filters_weak_groups(self, client: AsyncClient) -> None:
        ts = "2026-06-12T10:00:00+00:00"
        payload = {
            "events": [
                {
                    "event_id": "e1",
                    "category": "metric_anomaly",
                    "source": "telemetry",
                    "timestamp": ts,
                    "service_name": "api",
                    "title": "cpu spike",
                },
                {
                    "event_id": "e2",
                    "category": "metric_anomaly",
                    "source": "telemetry",
                    "timestamp": "2026-06-12T10:00:50+00:00",
                    "service_name": "api",
                    "title": "mem spike",
                },
            ],
            "min_score": 0.5,
        }
        response = await client.post("/api/v1/correlate", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert len(data["groups"]) == 0

    async def test_correlate_strategy_counts_reported(self, client: AsyncClient) -> None:
        ts = "2026-06-12T10:00:00+00:00"
        payload = {
            "events": [
                {
                    "event_id": "e1",
                    "category": "failure",
                    "source": "telemetry",
                    "timestamp": ts,
                    "service_name": "api",
                    "title": "error",
                    "trace_id": "trace-1",
                },
                {
                    "event_id": "e2",
                    "category": "failure",
                    "source": "telemetry",
                    "timestamp": ts,
                    "service_name": "api",
                    "title": "error",
                    "trace_id": "trace-1",
                },
            ],
        }
        response = await client.post("/api/v1/correlate", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "trace_id" in data["strategy_counts"]
        assert data["strategy_counts"]["trace_id"] > 0

    async def test_correlate_invalid_payload(self, client: AsyncClient) -> None:
        response = await client.post("/api/v1/correlate", json={})
        assert response.status_code == 422

    async def test_correlate_empty_events(self, client: AsyncClient) -> None:
        payload = {"events": []}
        response = await client.post("/api/v1/correlate", json=payload)
        assert response.status_code == 422
