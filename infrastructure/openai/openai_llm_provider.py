"""OpenAI LLM provider adapter implementing the LLMProvider contract."""

import json
from typing import Any, TypeVar

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

from shared.contracts.interfaces.llm_provider import LLMMessage, LLMProvider, LLMResponse

T = TypeVar("T", bound=BaseModel)


class OpenAIProviderConfig(BaseSettings):
    model_config = {"env_prefix": "OPENAI_", "env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    api_key: str = Field(default="", description="OpenAI API key.")
    base_url: str | None = Field(
        default=None, description="OpenAI API base URL (defaults to https://api.openai.com/v1)."
    )
    default_model: str = Field(default="gpt-4o", description="Default model identifier.")
    default_temperature: float = Field(default=0.1, ge=0.0, le=2.0, description="Default generation temperature.")
    default_max_tokens: int = Field(default=4096, ge=1, description="Default max tokens per response.")
    timeout_seconds: int = Field(default=60, ge=1, description="Request timeout in seconds.")


class OpenAILLMProvider(LLMProvider):
    """OpenAI-backed LLM provider.

    Lifecycle:
        Call ``start()`` before first use to initialise the client, and
        ``close()`` to release resources.
    """

    def __init__(self, config: OpenAIProviderConfig | None = None) -> None:
        self._config = config or OpenAIProviderConfig()
        self._client: Any = None

    async def start(self) -> None:
        from openai import AsyncOpenAI

        kwargs: dict[str, Any] = {"api_key": self._config.api_key, "timeout": self._config.timeout_seconds}
        if self._config.base_url is not None:
            kwargs["base_url"] = self._config.base_url
        self._client = AsyncOpenAI(**kwargs)

    async def close(self) -> None:
        self._client = None

    async def generate(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        kwargs = self._build_kwargs(messages, model, temperature, max_tokens)
        response = await self._client.chat.completions.create(**kwargs)
        return self._to_response(response)

    async def generate_structured(
        self,
        messages: list[LLMMessage],
        schema: type[T],
        model: str | None = None,
    ) -> T:
        kwargs = self._build_kwargs(messages, model)
        kwargs["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": schema.__name__, "strict": True, "schema": schema.model_json_schema()},
        }
        response = await self._client.chat.completions.create(**kwargs)
        raw = response.choices[0].message.content or ""
        try:
            cleaned = self._extract_json(raw)
            return schema.model_validate_json(cleaned)
        except (ValueError, Exception):
            pass

        # Fallback — model doesn't support response_format, retry with JSON instruction in system prompt
        schema_json = json.dumps(schema.model_json_schema(), indent=2)
        instruction = f"\n\nYou MUST respond with valid JSON matching this schema:\n```json\n{schema_json}\n```\nReturn ONLY the JSON object — no markdown, no explanations, no tags."
        fallback = [
            LLMMessage(role=m.role, content=m.content + instruction) if m.role == "system" else m for m in messages
        ]
        fbk = self._build_kwargs(fallback, model)
        response = await self._client.chat.completions.create(**fbk)
        cleaned = self._extract_json(response.choices[0].message.content or "")
        return schema.model_validate_json(cleaned)

    async def embed(self, text: str, model: str | None = None) -> list[float]:
        model = model or "text-embedding-3-small"
        response = await self._client.embeddings.create(input=text, model=model)
        return response.data[0].embedding

    def _build_kwargs(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        return {
            "model": model or self._config.default_model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature if temperature is not None else self._config.default_temperature,
            "max_tokens": max_tokens or self._config.default_max_tokens,
        }

    @staticmethod
    def _extract_json(content: str) -> str:
        """Strip non-JSON wrappers (think tags, markdown fences, leading text) from LLM output."""
        import re

        # Remove <think>...</think> blocks
        content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
        # Extract JSON from markdown code fence if present
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, flags=re.DOTALL)
        if m:
            return m.group(1).strip()
        # Fallback: find first { and last }
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            return content[start : end + 1]
        return content

    @staticmethod
    def _to_response(raw: Any) -> LLMResponse:
        choice = raw.choices[0]
        usage = raw.usage
        return LLMResponse(
            content=choice.message.content or "",
            finish_reason=choice.finish_reason,
            usage={
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens,
            }
            if usage
            else None,
        )
