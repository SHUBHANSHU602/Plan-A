from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.api.routes.predictions import router as predictions_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(predictions_router, prefix="/api/v1")
