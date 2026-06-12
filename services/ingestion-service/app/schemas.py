from pydantic import BaseModel


class IngestRequest(BaseModel):
    metric: str
    value: float
    unit: str | None = None
    tags: dict[str, str] = {}
    source: str
    timestamp: str | None = None


class IngestResponse(BaseModel):
    accepted: bool
    event_id: str
