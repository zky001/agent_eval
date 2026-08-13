from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./data/agent_eval.db"
    # Upper bound on concurrently executing LLM calls across ALL runs.
    MAX_CONCURRENT_TASKS: int = 10
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    # LLM HTTP client behaviour
    LLM_TIMEOUT_SECONDS: float = 120.0
    LLM_MAX_RETRIES: int = 3

    # Sandboxed code execution (humaneval) timeout per item
    CODE_EXEC_TIMEOUT_SECONDS: float = 5.0

    model_config = {"env_prefix": "AGENT_EVAL_", "env_file": ".env"}


settings = Settings()
