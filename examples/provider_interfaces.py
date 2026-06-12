"""Usage examples for RootPilot provider abstraction interfaces."""

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime, timezone

from pydantic import BaseModel
from shared.contracts import Event, EventBus, LLMMessage, LLMProvider, LLMResponse, LogEntry, LogFilter, LogStore


# ---------------------------------------------------------------------------
# Example EventBus implementation
# ---------------------------------------------------------------------------

class PrintBus(EventBus):
    async def publish(self, event: Event, topic: str | None = None) -> None:
        print(f"[{topic or event.topic}] {event.source}: {event.payload}")

    async def subscribe(self, topic: str, handler) -> None:
        pass

    async def start(self) -> None:
        pass

    async def close(self) -> None:
        pass

    async def health(self) -> bool:
        return True


# ---------------------------------------------------------------------------
# Example LogStore implementation
# ---------------------------------------------------------------------------

class MemoryLogStore(LogStore):
    def __init__(self) -> None:
        self._logs: list[LogEntry] = []

    async def write(self, entry: LogEntry) -> None:
        self._logs.append(entry)

    async def query(self, filter: LogFilter) -> AsyncIterator[LogEntry]:
        for entry in self._logs:
            if filter.service and entry.service != filter.service:
                continue
            if filter.level and entry.level != filter.level:
                continue
            yield entry

    async def health(self) -> bool:
        return True


# ---------------------------------------------------------------------------
# Example LLMProvider implementation
# ---------------------------------------------------------------------------

class EchoProvider(LLMProvider):
    async def generate(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        return LLMResponse(content=messages[-1].content if messages else "")

    async def generate_structured(
        self,
        messages: list[LLMMessage],
        schema: type[BaseModel],
        model: str | None = None,
    ) -> BaseModel:
        return schema()

    async def embed(self, text: str, model: str | None = None) -> list[float]:
        return [0.0] * 384


# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------

async def main() -> None:
    bus = PrintBus()
    await bus.publish(Event(source="test", topic="ping", payload={"msg": "hello"}))

    store = MemoryLogStore()
    await store.write(LogEntry(timestamp=datetime.now(timezone.utc), service="svc", level="INFO", message="started"))
    async for entry in store.query(LogFilter(service="svc")):
        print(f"  Log: {entry.message}")

    llm = EchoProvider()
    resp = await llm.generate([LLMMessage(role="user", content="hi")])
    print(f"  LLM: {resp.content}")


asyncio.run(main())
