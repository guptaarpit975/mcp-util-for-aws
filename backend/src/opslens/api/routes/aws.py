from __future__ import annotations

import anyio
from aws_ops_mcp.aws import caller_identity, collect_inventory
from botocore.exceptions import BotoCoreError, ClientError, ProfileNotFound
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import Settings, get_settings
from ...db import get_db
from ...health import HealthRepository
from ...repositories import AuditRepository, InventoryRepository, SettingsRepository
from ...schemas import (
    AwsConnectionResponse,
    InventoryRefreshRequest,
    InventoryRefreshResponse,
    ResourceListResponse,
    ResourceView,
)

router = APIRouter(tags=["aws"])


async def _configured_profile(
    session: AsyncSession,
    settings: Settings,
):
    record = await SettingsRepository(session).get_aws_profile()
    if record:
        return record.profile_name, record.expected_account_id, record.regions_json
    return settings.default_aws_profile, None, settings.default_aws_regions


@router.get("/aws/status", response_model=AwsConnectionResponse)
async def aws_status(
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AwsConnectionResponse:
    profile, expected_account_id, _regions = await _configured_profile(session, settings)
    if not profile:
        return AwsConnectionResponse(
            connected=False,
            profile="",
            message="Configure an AWS profile in Settings.",
        )
    try:
        identity = await anyio.to_thread.run_sync(lambda: caller_identity(profile))
    except (BotoCoreError, ClientError, ProfileNotFound) as error:
        return AwsConnectionResponse(
            connected=False,
            profile=profile,
            message=f"AWS connection failed: {type(error).__name__}",
        )
    if expected_account_id and identity["account_id"] != expected_account_id:
        return AwsConnectionResponse(
            connected=False,
            profile=profile,
            account_id=identity["account_id"],
            arn=identity["arn"],
            user_id=identity["user_id"],
            message="The AWS profile resolved to an account outside the configured allowlist.",
        )
    return AwsConnectionResponse(
        connected=True,
        profile=profile,
        account_id=identity["account_id"],
        arn=identity["arn"],
        user_id=identity["user_id"],
        message="Temporary AWS credentials are valid.",
    )


@router.post("/resources/refresh", response_model=InventoryRefreshResponse)
async def refresh_resources(
    request: InventoryRefreshRequest,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> InventoryRefreshResponse:
    profile, expected_account_id, regions = await _configured_profile(session, settings)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Configure an AWS profile before refreshing inventory.",
        )
    try:
        result = await anyio.to_thread.run_sync(
            lambda: collect_inventory(
                profile,
                regions,
                services=request.services,
                page_limit=settings.inventory_page_limit,
            )
        )
    except (BotoCoreError, ClientError, ProfileNotFound) as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AWS inventory failed: {type(error).__name__}",
        ) from error
    if expected_account_id and result.account_id != expected_account_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The AWS profile resolved to an account outside the configured allowlist.",
        )
    await InventoryRepository(session).replace_inventory(result, request.services)
    # Evaluate the complete stored inventory. A service-scoped refresh must not
    # resolve findings that belong to services omitted from this collection.
    await HealthRepository(session).evaluate_stored_inventory()
    await AuditRepository(session).record(
        "aws.inventory.refreshed",
        f"Collected {len(result.resources)} AWS resources",
        {
            "account_id": result.account_id,
            "regions": regions,
            "services": request.services,
            "warning_count": len(result.warnings),
        },
        created_at=result.collected_at,
    )
    await session.commit()
    return InventoryRefreshResponse(
        account_id=result.account_id,
        resource_count=len(result.resources),
        warning_count=len(result.warnings),
        warnings=result.warnings,
        collected_at=result.collected_at,
    )


@router.get("/resources", response_model=ResourceListResponse)
async def list_resources(
    service: str | None = Query(default=None),
    region: str | None = Query(default=None),
    search: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=500, ge=1, le=1000),
    session: AsyncSession = Depends(get_db),
) -> ResourceListResponse:
    items, total = await InventoryRepository(session).list_resources(
        service=service,
        region=region,
        search=search,
        limit=limit,
    )
    return ResourceListResponse(
        items=[ResourceView.model_validate(item) for item in items],
        total=total,
    )
