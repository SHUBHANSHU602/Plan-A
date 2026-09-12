from fastapi import APIRouter

from app.api.routes.alerts import router as alerts_router
from app.api.routes.exposure import router as exposure_router
from app.api.routes.health import router as health_router
from app.api.routes.notifications import router as notifications_router
from app.api.routes.predictions import router as predictions_router
from app.api.routes.websocket import router as websocket_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(alerts_router, prefix="/api/v1")
api_router.include_router(exposure_router, prefix="/api/v1")
api_router.include_router(notifications_router, prefix="/api/v1")
api_router.include_router(predictions_router, prefix="/api/v1")
api_router.include_router(websocket_router)
