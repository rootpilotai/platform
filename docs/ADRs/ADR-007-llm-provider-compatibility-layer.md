# ADR-007: LLM Provider Compatibility Layer

## Status

Accepted

---

## Context

RootPilot's investigation pipeline depends on large language models for root cause analysis. The LLM provider must be swappable — OpenAI is the initial provider, but the platform must support alternatives (Anthropic, local models, future fine-tuned models) without rewriting the investigation pipeline.

Key requirements:

* structured output generation (typed Pydantic models, not free text)
* standard text generation (chat completions)
* text embeddings for future retrieval-augmented generation
* configuration-driven provider selection
* consistent error handling across providers

---

## Decision

LLM access is abstracted behind the `LLMProvider` interface in `shared/contracts/interfaces/`.

### Interface

```python
class LLMProvider(ABC):
    async def generate(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse: ...

    async def generate_structured(
        self,
        messages: list[LLMMessage],
        schema: type[T],
        model: str | None = None,
    ) -> T: ...

    async def embed(self, text: str, model: str | None = None) -> list[float]: ...
```

### Key Design Properties

**Structured Output First** — `generate_structured()` is the primary method used by the investigation pipeline. It accepts a Pydantic model class (`T`) and returns a validated instance. The OpenAI implementation uses `response_format={"type": "json_schema"}` with strict schema enforcement, falling back to prompt-instructed JSON extraction.

**Provider Configuration via `BaseSettings`** — Each provider defines its own config model with provider-specific env prefix (e.g., `OPENAI_API_KEY`, `OPENAI_DEFAULT_MODEL`). This keeps provider credentials namespaced and avoids a single monolithic config.

**Current Implementation** — Only `OpenAILLMProvider` exists, using the `openai` Python SDK with `AsyncOpenAI`. The default model is `gpt-4o`, default temperature `0.1`, default max tokens `4096`.

### Usage in Investigation Pipeline

```
ai-investigation-service
  └─ InvestigationPipeline
       └─ LLMProvider.generate_structured(messages, RCASummary)
            └─ returns validated RCASummary
```

---

## Consequences

### Advantages

* Investigation pipeline is fully provider-agnostic
* Structured output reduces hallucination risk and eliminates parsing fragility
* Adding a new provider requires only implementing the three-method interface
* Provider config stays isolated behind `BaseSettings` with its own env prefix
* Embedding support enables future RAG workflows without interface changes

### Tradeoffs

* The interface is OpenAI-shaped — some providers may not support all three methods (especially `embed`)
* No streaming support in the interface (all methods return complete responses)
- No middleware layer for observability (tracing, token counting) — each provider must implement its own
* Only one provider (OpenAI) is implemented, so the abstraction is untested with alternatives

---

## Future Considerations

* Add Anthropic (Claude) provider implementation
* Add Azure OpenAI provider (different auth, same models)
* Add local model provider (Ollama, vLLM) for air-gapped deployments
* Add middleware layer for token tracking, cost accounting, and distributed tracing
* Evaluate streaming support for real-time investigation progress
