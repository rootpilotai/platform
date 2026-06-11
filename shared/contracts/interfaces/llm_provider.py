"""LLM provider abstraction for provider-agnostic async AI workflows."""

from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T", bound=BaseModel)


class LLMMessage(BaseModel):
    role: str = Field(description="Message role (e.g. system, user, assistant).")
    content: str = Field(description="Message text content.")


class LLMResponse(BaseModel):
    content: str = Field(description="Generated response text.")
    finish_reason: str | None = Field(default=None, description="Why generation stopped (e.g. stop, length).")
    usage: dict[str, int] | None = Field(default=None, description="Token usage breakdown.")


class LLMProvider(ABC):
    @abstractmethod
    async def generate(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse: ...

    @abstractmethod
    async def generate_structured(
        self,
        messages: list[LLMMessage],
        schema: type[T],
        model: str | None = None,
    ) -> T: ...

    @abstractmethod
    async def embed(self, text: str, model: str | None = None) -> list[float]: ...
