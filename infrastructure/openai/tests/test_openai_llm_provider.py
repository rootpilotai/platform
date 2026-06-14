"""Tests for the OpenAI LLM provider adapter."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel, Field

from infrastructure.openai.openai_llm_provider import OpenAILLMProvider, OpenAIProviderConfig
from shared.contracts.interfaces.llm_provider import LLMMessage


class _FakeSchema(BaseModel):
    result: str = Field(description="Test field")


@pytest.fixture
def config() -> OpenAIProviderConfig:
    return OpenAIProviderConfig(api_key="test-key")


@pytest.fixture
def provider(config: OpenAIProviderConfig) -> OpenAILLMProvider:
    return OpenAILLMProvider(config)


class TestOpenAIProviderConfig:
    def test_defaults(self) -> None:
        cfg = OpenAIProviderConfig()
        assert cfg.default_model == "gpt-4o"
        assert cfg.default_temperature == 0.1
        assert cfg.default_max_tokens == 4096
        assert cfg.timeout_seconds == 60

    def test_env_prefix(self) -> None:
        assert OpenAIProviderConfig.model_config.get("env_prefix") == "OPENAI_"


class TestOpenAILLMProvider:
    async def test_start_creates_client(self, provider: OpenAILLMProvider) -> None:
        assert provider._client is None
        with patch("openai.AsyncOpenAI") as mock:
            await provider.start()
        mock.assert_called_once_with(api_key="test-key", timeout=60)
        assert provider._client is not None

    async def test_close_clears_client(self, provider: OpenAILLMProvider) -> None:
        provider._client = MagicMock()
        await provider.close()
        assert provider._client is None

    async def test_generate_returns_response(self, provider: OpenAILLMProvider) -> None:
        provider._client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "Hello"
        mock_choice.finish_reason = "stop"
        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 10
        mock_usage.completion_tokens = 5
        mock_usage.total_tokens = 15
        provider._client.chat.completions.create = AsyncMock(
            return_value=MagicMock(choices=[mock_choice], usage=mock_usage)
        )

        messages = [LLMMessage(role="user", content="hi")]
        response = await provider.generate(messages)

        assert response.content == "Hello"
        assert response.finish_reason == "stop"
        assert response.usage == {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}

    async def test_generate_structured_returns_parsed_schema(self, provider: OpenAILLMProvider) -> None:
        provider._client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = '{"result": "ok"}'
        mock_choice.finish_reason = "stop"
        provider._client.chat.completions.create = AsyncMock(return_value=MagicMock(choices=[mock_choice], usage=None))

        messages = [LLMMessage(role="user", content="test")]
        result = await provider.generate_structured(messages, _FakeSchema)

        assert isinstance(result, _FakeSchema)
        assert result.result == "ok"

    async def test_embed_returns_float_list(self, provider: OpenAILLMProvider) -> None:
        provider._client = MagicMock()
        mock_embedding = MagicMock()
        mock_embedding.embedding = [0.1, 0.2, 0.3]
        provider._client.embeddings.create = AsyncMock(return_value=MagicMock(data=[mock_embedding]))

        result = await provider.embed("test text")
        assert result == [0.1, 0.2, 0.3]

    async def test_generate_raises_if_not_started(self, provider: OpenAILLMProvider) -> None:
        with pytest.raises(AttributeError):
            await provider.generate([LLMMessage(role="user", content="hi")])
