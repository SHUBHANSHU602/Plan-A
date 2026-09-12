from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import get_settings
from app.scheduler.runtime import create_scheduler


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    scheduler = create_scheduler(settings)
    application.state.scheduler = scheduler
    if settings.scheduler_enabled:
        scheduler.start()
    try:
        yield
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=False)


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        description="Landslide risk and early-warning platform API",
        version=settings.app_version,
        lifespan=lifespan,
    )
    application.include_router(api_router)
    return application


app = create_app()
