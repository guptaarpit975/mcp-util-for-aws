from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import Settings, get_settings
from ...db import get_db
from ...schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> HealthResponse:
    database_status = "connected"
    status = "ok"
    try:
        await session.execute(text("SELECT 1"))
    except Exception:  # The health endpoint deliberately converts driver errors to status.
        database_status = "unavailable"
        status = "degraded"
    return HealthResponse(
        status=status,
        application=settings.app_name,
        environment=settings.environment,
        database=database_status,
    )
