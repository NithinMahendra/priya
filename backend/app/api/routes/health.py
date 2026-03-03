from fastapi import APIRouter

from app.services.llm_provider import get_provider_diagnostics

router = APIRouter(tags=["health"])


@router.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/provider")
def health_provider() -> dict[str, str | bool]:
    return get_provider_diagnostics()
