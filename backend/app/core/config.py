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
        extra="ignore",
    )

    APP_NAME: str = "AI Code Reviewer"
    API_V1_STR: str = "/api/v1"

    DATABASE_URL: str = "sqlite:///./reviewer.db"
    CORS_ORIGINS: str = "*"

    JWT_SECRET_KEY: str = "change-this-secret"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120

    LLM_PROVIDER: str = "openrouter"
    LLM_MODEL: str = "nvidia/nemotron-3-nano-30b-a3b:free"
    OPENROUTER_API_KEY: str | None = None
    OPENROUTER_API_BASE: str = "https://openrouter.ai/api/v1"
    OPENROUTER_SITE_URL: str | None = None
    OPENROUTER_APP_NAME: str = "AI Code Reviewer"
    OPENROUTER_FREE_ONLY: bool = True
    OPENROUTER_MODEL_CACHE_SECONDS: int = 300
    OPENROUTER_TIMEOUT_SECONDS: float = 30.0
    OPENROUTER_TOTAL_TIMEOUT_SECONDS: float = 32.0
    OPENROUTER_MAX_CANDIDATES: int = 1
    LLM_ALLOW_MOCK_FALLBACK: bool = False
    LLM_MAX_RETRIES: int = 2
    LLM_RETRY_BASE_SECONDS: float = 0.75
    LLM_TOTAL_TIMEOUT_SECONDS: float = 35.0
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
        if provider in {"", "auto"}:
            if (self.OPENROUTER_API_KEY or "").strip():
                return "openrouter"
            return "mock"
        if provider == "openrouter":
            return "openrouter" if (self.OPENROUTER_API_KEY or "").strip() else "mock"
        if provider == "mock":
            return "mock"
        return "mock"

    @property
    def cors_origins_list(self) -> list[str]:
        if self.CORS_ORIGINS.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
