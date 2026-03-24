from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./data/agent_eval.db"
    MAX_CONCURRENT_TASKS: int = 10
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    model_config = {"env_prefix": "AGENT_EVAL_", "env_file": ".env"}


settings = Settings()
