from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import Settings, get_settings
from ...db import get_db
from ...infrastructure.keychain import secret_store
from ...repositories import AuditRepository, SettingsRepository
from ...schemas import (
    AwsProfileUpdate,
    AwsProfileView,
    ModelProviderUpdate,
    ModelProviderView,
    ModelSecretUpdate,
    SettingsView,
    ValidationResponse,
)

router = APIRouter(prefix="/settings", tags=["settings"])


def _provider_view(record) -> ModelProviderView:
    reference = record.api_key_reference if record else None
    return ModelProviderView(
        provider=record.provider if record else "anthropic",
        model=record.model if record else "claude-sonnet-5-5",
        base_url=record.base_url if record else None,
        api_key_reference=reference,
        api_key_configured=(
            secret_store.is_configured(reference)
            or bool(secret_store.environment_secret(record.provider if record else "anthropic"))
        ),
        enabled=record.enabled if record else True,
        options=record.options_json if record else {},
    )


def _aws_view(record, settings: Settings) -> AwsProfileView | None:
    if record:
        return AwsProfileView(
            profile_name=record.profile_name,
            expected_account_id=record.expected_account_id,
            regions=record.regions_json,
            enabled=record.enabled,
        )
    if not settings.default_aws_profile:
        return None
    return AwsProfileView(
        profile_name=settings.default_aws_profile,
        regions=settings.default_aws_regions,
        enabled=True,
    )


@router.get("", response_model=SettingsView)
async def get_application_settings(
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> SettingsView:
    repository = SettingsRepository(session)
    return SettingsView(
        model_provider=_provider_view(await repository.get_model_provider()),
        aws_profile=_aws_view(await repository.get_aws_profile(), settings),
    )


@router.put("/model", response_model=ModelProviderView)
async def update_model_provider(
    update: ModelProviderUpdate,
    session: AsyncSession = Depends(get_db),
) -> ModelProviderView:
    repository = SettingsRepository(session)
    record = await repository.upsert_model_provider(
        provider=update.provider,
        model=update.model,
        base_url=update.base_url,
        enabled=update.enabled,
        options=update.options,
    )
    await AuditRepository(session).record(
        "settings.model.updated",
        f"Model provider changed to {update.provider}",
        {"provider": update.provider, "model": update.model},
    )
    await session.commit()
    return _provider_view(record)


@router.put("/aws", response_model=AwsProfileView)
async def update_aws_profile(
    update: AwsProfileUpdate,
    session: AsyncSession = Depends(get_db),
) -> AwsProfileView:
    repository = SettingsRepository(session)
    record = await repository.upsert_aws_profile(
        profile_name=update.profile_name,
        expected_account_id=update.expected_account_id,
        regions=update.regions,
        enabled=update.enabled,
    )
    await AuditRepository(session).record(
        "settings.aws.updated",
        f"AWS profile changed to {update.profile_name}",
        {"profile": update.profile_name, "regions": update.regions},
    )
    await session.commit()
    return AwsProfileView(
        profile_name=record.profile_name,
        expected_account_id=record.expected_account_id,
        regions=record.regions_json,
        enabled=record.enabled,
    )


@router.post("/model/secret", response_model=ValidationResponse)
async def store_model_secret(
    update: ModelSecretUpdate,
    session: AsyncSession = Depends(get_db),
) -> ValidationResponse:
    repository = SettingsRepository(session)
    record = await repository.get_model_provider()
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Save the model provider before storing its API key.",
        )
    reference = f"model/{record.provider}/default"
    try:
        secret_store.set(reference, update.api_key)
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"The operating-system keychain could not store the secret: {type(error).__name__}"
            ),
        ) from error
    record.api_key_reference = reference
    await AuditRepository(session).record(
        "settings.model.secret_updated",
        f"API key stored in the operating-system keychain for {record.provider}",
    )
    await session.commit()
    return ValidationResponse(ok=True, message="API key stored in the operating-system keychain.")


@router.post("/model/test", response_model=ValidationResponse)
async def test_model_configuration(
    session: AsyncSession = Depends(get_db),
) -> ValidationResponse:
    record = await SettingsRepository(session).get_model_provider()
    if record is None:
        return ValidationResponse(ok=False, message="Model provider has not been configured.")
    if (
        record.provider != "local"
        and not secret_store.is_configured(record.api_key_reference)
        and not secret_store.environment_secret(record.provider)
    ):
        return ValidationResponse(ok=False, message="No API key is stored for this provider.")
    return ValidationResponse(
        ok=True,
        message="Provider configuration is complete and ready for conversations.",
    )


@router.post("/mysql/test", response_model=ValidationResponse)
async def test_mysql(session: AsyncSession = Depends(get_db)) -> ValidationResponse:
    try:
        await session.execute(text("SELECT 1"))
    except Exception as error:
        return ValidationResponse(
            ok=False,
            message=f"MySQL connection failed: {type(error).__name__}",
        )
    return ValidationResponse(ok=True, message="MySQL connection is healthy.")
