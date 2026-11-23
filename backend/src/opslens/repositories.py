from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from aws_ops_mcp.contracts import InventoryResult
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    AgentRun,
    AuditEvent,
    AwsProfileConfig,
    Conversation,
    Message,
    ModelProviderConfig,
    ResourceInventory,
    ToolExecution,
)


class SettingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_model_provider(self) -> ModelProviderConfig | None:
        return await self.session.scalar(
            select(ModelProviderConfig).order_by(ModelProviderConfig.created_at).limit(1)
        )

    async def upsert_model_provider(
        self,
        *,
        provider: str,
        model: str,
        base_url: str | None,
        enabled: bool,
        options: dict[str, Any],
    ) -> ModelProviderConfig:
        record = await self.get_model_provider()
        if record is None:
            record = ModelProviderConfig()
            self.session.add(record)
        record.provider = provider
        record.model = model
        record.base_url = base_url
        record.enabled = enabled
        record.options_json = options
        await self.session.flush()
        return record

    async def get_aws_profile(self) -> AwsProfileConfig | None:
        return await self.session.scalar(
            select(AwsProfileConfig)
            .where(AwsProfileConfig.enabled.is_(True))
            .order_by(AwsProfileConfig.created_at)
            .limit(1)
        )

    async def upsert_aws_profile(
        self,
        *,
        profile_name: str,
        expected_account_id: str | None,
        regions: list[str],
        enabled: bool,
    ) -> AwsProfileConfig:
        record = await self.session.scalar(
            select(AwsProfileConfig).where(AwsProfileConfig.profile_name == profile_name)
        )
        if record is None:
            record = AwsProfileConfig(profile_name=profile_name)
            self.session.add(record)
        record.expected_account_id = expected_account_id
        record.regions_json = regions
        record.enabled = enabled
        await self.session.flush()
        return record


class InventoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def replace_inventory(
        self,
        result: InventoryResult,
        services: list[str] | None = None,
    ) -> None:
        delete_statement = delete(ResourceInventory).where(
            ResourceInventory.account_id == result.account_id
        )
        if services:
            delete_statement = delete_statement.where(ResourceInventory.service.in_(services))
        await self.session.execute(delete_statement)
        for resource in result.resources:
            # boto3 commonly returns datetime values inside service metadata. Normalize the
            # complete nested payload through Pydantic before handing it to MySQL's JSON type.
            serialized_resource = resource.model_dump(mode="json")
            statement = insert(ResourceInventory).values(
                account_id=result.account_id,
                region=resource.region,
                service=resource.service,
                resource_type=resource.resource_type,
                resource_id=resource.resource_id,
                name=resource.name,
                arn=resource.arn,
                status=resource.status,
                metadata_json=serialized_resource["metadata"],
                collected_at=result.collected_at,
            )
            await self.session.execute(statement)

    async def list_resources(
        self,
        *,
        service: str | None = None,
        region: str | None = None,
        search: str | None = None,
        limit: int = 500,
    ) -> tuple[list[ResourceInventory], int]:
        filters = []
        if service:
            filters.append(ResourceInventory.service == service)
        if region:
            filters.append(ResourceInventory.region == region)
        if search:
            filters.append(ResourceInventory.name.like(f"%{search}%"))
        query = (
            select(ResourceInventory)
            .where(*filters)
            .order_by(
                ResourceInventory.service,
                ResourceInventory.name,
            )
        )
        count_query = select(func.count()).select_from(ResourceInventory).where(*filters)
        total = int((await self.session.scalar(count_query)) or 0)
        rows = list((await self.session.scalars(query.limit(limit))).all())
        return rows, total


class AuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record(
        self,
        event_type: str,
        summary: str,
        details: dict[str, Any] | None = None,
        *,
        created_at: datetime | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            event_type=event_type,
            summary=summary,
            details_json=details,
        )
        if created_at:
            event.created_at = created_at
        self.session.add(event)
        await self.session.flush()
        return event


class ConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, title: str = "New conversation") -> Conversation:
        record = Conversation(title=title)
        self.session.add(record)
        await self.session.flush()
        return record

    async def get(self, conversation_id: str) -> Conversation | None:
        return await self.session.get(Conversation, conversation_id)

    async def list(self) -> list[Conversation]:
        return list(
            (
                await self.session.scalars(
                    select(Conversation).order_by(Conversation.updated_at.desc()).limit(100)
                )
            ).all()
        )

    async def messages(self, conversation_id: str) -> list[Message]:
        return list(
            (
                await self.session.scalars(
                    select(Message)
                    .where(Message.conversation_id == conversation_id)
                    .order_by(Message.created_at, Message.id)
                )
            ).all()
        )

    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        content_json: dict[str, Any] | None = None,
    ) -> Message:
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            content_json=content_json,
        )
        self.session.add(message)
        conversation = await self.get(conversation_id)
        if conversation:
            conversation.updated_at = datetime.now(UTC)
            if role == "user" and conversation.title == "New conversation":
                conversation.title = content[:80]
        await self.session.flush()
        return message

    async def create_run(
        self,
        conversation_id: str,
        provider: str,
        model: str,
    ) -> AgentRun:
        run = AgentRun(
            conversation_id=conversation_id,
            provider=provider,
            model=model,
            status="running",
        )
        self.session.add(run)
        await self.session.flush()
        return run

    async def finish_run(
        self,
        run_id: str,
        *,
        status: str,
        usage: dict[str, int] | None = None,
        error_code: str | None = None,
    ) -> None:
        run = await self.session.get(AgentRun, run_id)
        if run:
            run.status = status
            run.usage_json = usage
            run.error_code = error_code
            run.completed_at = datetime.now(UTC)

    async def record_tool_execution(
        self,
        *,
        run_id: str,
        tool_name: str,
        status: str,
        arguments: dict[str, Any],
        result: Any,
        duration_ms: int,
    ) -> None:
        summary: dict[str, Any]
        if isinstance(result, dict):
            summary = result
        else:
            summary = {"result": result}
        self.session.add(
            ToolExecution(
                agent_run_id=run_id,
                tool_name=tool_name,
                status=status,
                arguments_json=arguments,
                result_summary_json=summary,
                duration_ms=duration_ms,
            )
        )
