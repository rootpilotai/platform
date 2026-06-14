from pydantic_settings import BaseSettings


class InvestigationServiceConfig(BaseSettings):
    model_config = {"env_prefix": "INVESTIGATION_"}

    service_name: str = "ai-investigation-service"
    environment: str = "development"
    debug: bool = False
    log_level: str = "INFO"
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 4096
