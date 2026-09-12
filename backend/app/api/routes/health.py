from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str


class ReadinessResponse(BaseModel):
    status: Literal["ready"]
    database: Literal["available"]


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(status="ok", service="plan-a-api")


@router.get("/health/ready", response_model=ReadinessResponse)
async def readiness_check(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ReadinessResponse:
    await session.execute(text("SELECT 1"))
    return ReadinessResponse(status="ready", database="available")
