from fastapi import APIRouter

from app.api.routes.auth import router as auth_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.health import router as health_router
from app.api.routes.integrations import router as integrations_router
from app.api.routes.learning import router as learning_router
from app.api.routes.reviews import router as reviews_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(reviews_router)
api_router.include_router(dashboard_router)
api_router.include_router(integrations_router)
api_router.include_router(learning_router)
