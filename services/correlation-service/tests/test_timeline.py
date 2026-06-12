from datetime import datetime, timezone

from httpx import AsyncClient

from shared.domain.timeline.enums import TimelineEventCategory, TimelineEventSource


class TestReconstructEndpoint:
    async def test_reconstruct_empty_events(self, client: AsyncClient) -> None:
        payload = {
            "incident_id": "inc-1",
            "service": "api-gateway",
            "events": [],
        }
        response = await client.post("/api/v1/timeline/reconstruct", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["incident_id"] == "inc-1"
        assert data["service"] == "api-gateway"
        assert data["event_count"] == 0
        assert data["window_count"] == 0

    async def test_reconstruct_single_event(self, client: AsyncClient) -> None:
        ts = "2026-06-12T10:00:00+00:00"
        payload = {
            "incident_id": "inc-2",
            "service": "api",
            "events": [
                {
                    "event_id": "e1",
                    "category": "failure",
                    "source": "telemetry",
                    "timestamp": ts,
                    "service_name": "api",
                    "title": "error rate spike",
                    "description": "",
                    "trace_id": None,
                    "request_id": None,
                    "severity": None,
                    "tags": {},
                }
            ],
        }
        response = await client.post("/api/v1/timeline/reconstruct", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["event_count"] == 1
        assert data["window_count"] == 1
        assert len(data["windows"]) == 1
        assert data["windows"][0]["events"][0]["event_id"] == "e1"

    async def test_reconstruct_multiple_events_in_windows(self, client: AsyncClient) -> None:
        base = "2026-06-12T10:00:00+00:00"
        later = "2026-06-12T10:06:00+00:00"
        payload = {
            "incident_id": "inc-3",
            "service": "api",
            "events": [
                {
                    "event_id": "e1",
                    "category": "failure",
                    "source": "telemetry",
                    "timestamp": base,
                    "service_name": "api",
                    "title": "error",
                    "description": "",
                    "trace_id": None,
                    "request_id": None,
                    "severity": None,
                    "tags": {},
                },
                {
                    "event_id": "e2",
                    "category": "retry",
                    "source": "telemetry",
                    "timestamp": later,
                    "service_name": "api",
                    "title": "retry",
                    "description": "",
                    "trace_id": None,
                    "request_id": None,
                    "severity": None,
                    "tags": {},
                },
            ],
        }
        response = await client.post("/api/v1/timeline/reconstruct", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["event_count"] == 2
        assert data["window_count"] == 2
        assert data["windows"][0]["events"][0]["event_id"] == "e1"
        assert data["windows"][1]["events"][0]["event_id"] == "e2"

    async def test_reconstruct_with_window_duration_override(self, client: AsyncClient) -> None:
        base = "2026-06-12T10:00:00+00:00"
        inline = "2026-06-12T10:05:00+00:00"
        payload = {
            "incident_id": "inc-4",
            "service": "api",
            "events": [
                {
                    "event_id": "e1",
                    "category": "failure",
                    "source": "telemetry",
                    "timestamp": base,
                    "service_name": "api",
                    "title": "error",
                    "description": "",
                    "trace_id": None,
                    "request_id": None,
                    "severity": None,
                    "tags": {},
                },
                {
                    "event_id": "e2",
                    "category": "retry",
                    "source": "telemetry",
                    "timestamp": inline,
                    "service_name": "api",
                    "title": "retry",
                    "description": "",
                    "trace_id": None,
                    "request_id": None,
                    "severity": None,
                    "tags": {},
                },
            ],
            "window_duration_seconds": 360,
        }
        response = await client.post("/api/v1/timeline/reconstruct", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["window_count"] == 1
        assert data["window_duration_seconds"] == 360

    async def test_reconstruct_invalid_payload(self, client: AsyncClient) -> None:
        response = await client.post("/api/v1/timeline/reconstruct", json={})
        assert response.status_code == 422

    async def test_reconstruct_maintains_event_order(self, client: AsyncClient) -> None:
        t1 = "2026-06-12T10:02:00+00:00"
        t2 = "2026-06-12T10:01:00+00:00"
        t3 = "2026-06-12T10:03:00+00:00"
        payload = {
            "incident_id": "inc-5",
            "service": "api",
            "events": [
                {
                    "event_id": "e2",
                    "category": "failure",
                    "source": "telemetry",
                    "timestamp": t1,
                    "service_name": "api",
                    "title": "second",
                    "description": "",
                    "trace_id": None,
                    "request_id": None,
                    "severity": None,
                    "tags": {},
                },
                {
                    "event_id": "e1",
                    "category": "failure",
                    "source": "telemetry",
                    "timestamp": t2,
                    "service_name": "api",
                    "title": "first",
                    "description": "",
                    "trace_id": None,
                    "request_id": None,
                    "severity": None,
                    "tags": {},
                },
                {
                    "event_id": "e3",
                    "category": "failure",
                    "source": "telemetry",
                    "timestamp": t3,
                    "service_name": "api",
                    "title": "third",
                    "description": "",
                    "trace_id": None,
                    "request_id": None,
                    "severity": None,
                    "tags": {},
                },
            ],
        }
        response = await client.post("/api/v1/timeline/reconstruct", json=payload)
        assert response.status_code == 200
        data = response.json()
        ids = [e["event_id"] for w in data["windows"] for e in w["events"]]
        assert ids == ["e1", "e2", "e3"]
