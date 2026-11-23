from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_db
from ...health import HealthRepository
from ...repositories import AuditRepository
from ...schemas import FindingListResponse, FindingView, HealthSummaryResponse

router = APIRouter(tags=["health findings"])


@router.get("/health/summary", response_model=HealthSummaryResponse)
async def health_summary(session: AsyncSession = Depends(get_db)) -> HealthSummaryResponse:
    return await HealthRepository(session).summary()


@router.post("/health/evaluate", response_model=FindingListResponse)
async def evaluate_health(session: AsyncSession = Depends(get_db)) -> FindingListResponse:
    repository = HealthRepository(session)
    await repository.evaluate_stored_inventory()
    items, total = await repository.list_findings("open")
    await AuditRepository(session).record(
        "health.evaluated",
        f"Evaluated stored inventory and found {total} open findings",
    )
    await session.commit()
    return FindingListResponse(
        items=[FindingView.model_validate(item) for item in items],
        total=total,
    )


@router.get("/findings", response_model=FindingListResponse)
async def list_findings(
    finding_status: str = Query(default="open", alias="status"),
    session: AsyncSession = Depends(get_db),
) -> FindingListResponse:
    if finding_status not in {"open", "acknowledged", "resolved", "all"}:
        raise HTTPException(status_code=400, detail="Unsupported finding status.")
    items, total = await HealthRepository(session).list_findings(finding_status)
    return FindingListResponse(
        items=[FindingView.model_validate(item) for item in items],
        total=total,
    )


@router.post("/findings/{finding_id}/acknowledge", response_model=FindingView)
async def acknowledge_finding(
    finding_id: str,
    session: AsyncSession = Depends(get_db),
) -> FindingView:
    record = await HealthRepository(session).acknowledge(finding_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found.")
    await AuditRepository(session).record(
        "finding.acknowledged",
        f"Acknowledged finding {record.code} for {record.resource_name}",
        {"finding_id": finding_id},
    )
    await session.commit()
    return FindingView.model_validate(record)
