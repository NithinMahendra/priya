import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.db.base import Base
from app.db.session import engine
from app.middleware.rate_limit import RateLimitMiddleware
from app.models import review_action, submission, user  # noqa: F401
from app.services.llm_provider import get_llm_provider, get_provider_diagnostics

logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Production-grade AI-powered code review API.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    RateLimitMiddleware,
    max_requests=settings.RATE_LIMIT_REQUESTS,
    window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS,
)
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    diagnostics = get_provider_diagnostics()
    logger.info(
        "llm_startup_config provider=%s effective_provider=%s model_mode=%s free_only=%s api_base_host=%s mock_fallback_allowed=%s",
        diagnostics["provider"],
        diagnostics["effective_provider"],
        diagnostics["model_mode"],
        diagnostics["free_only"],
        diagnostics["api_base_host"],
        diagnostics["mock_fallback_allowed"],
    )
    try:
        get_llm_provider()
    except Exception as exc:
        logger.error("llm_startup_validation_failed error=%s", exc)
    else:
        logger.info("llm_startup_validation_ok")


@app.get("/", tags=["root"])
def root() -> dict[str, str]:
    return {"message": "AI Code Reviewer API is running."}
