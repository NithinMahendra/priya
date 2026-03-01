from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BACKEND_DIR / ".env", PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    APP_NAME: str = "AI Code Reviewer"
    API_V1_STR: str = "/api/v1"

    DATABASE_URL: str = "sqlite:///./reviewer.db"
    CORS_ORIGINS: str = "*"

    JWT_SECRET_KEY: str = "change-this-secret"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120

    LLM_PROVIDER: str = "mock"
    LLM_MODEL: str = "gpt-4.1-mini"
    OPENAI_API_KEY: str | None = None
    LLM_MAX_RETRIES: int = 2
    LLM_RETRY_BASE_SECONDS: float = 0.75
    PROJECT_CONTEXT_MAX_CHARS: int = 4000

    RATE_LIMIT_REQUESTS: int = 120
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    JAVA_CHECKSTYLE_CMD: str | None = None
    JAVA_PMD_CMD: str | None = None

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")

    @property
    def effective_llm_provider(self) -> str:
        provider = self.LLM_PROVIDER.strip().lower()
        if provider == "openai" and not self.OPENAI_API_KEY:
            return "mock"
        if provider not in {"openai", "mock"}:
            return "mock"
        return provider

    @property
    def cors_origins_list(self) -> list[str]:
        if self.CORS_ORIGINS.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
