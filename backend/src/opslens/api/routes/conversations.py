from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import Settings, get_settings
from ...db import SessionFactory, get_db
from ...mcp_client import LocalMcpClient
from ...orchestration.agent import AgentLoop
from ...providers.factory import ProviderConfigurationError, create_provider
from ...repositories import ConversationRepository, SettingsRepository
from ...schemas import ChatRequest, ConversationCreate, ConversationView, MessageView

router = APIRouter(prefix="/conversations", tags=["conversations"])


def _sse(event: dict) -> str:
    return f"event: {event['type']}\ndata: {json.dumps(event, default=str)}\n\n"


@router.get("", response_model=list[ConversationView])
async def list_conversations(
    session: AsyncSession = Depends(get_db),
) -> list[ConversationView]:
    records = await ConversationRepository(session).list()
    return [ConversationView.model_validate(item) for item in records]


@router.post("", response_model=ConversationView, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    request: ConversationCreate,
    session: AsyncSession = Depends(get_db),
) -> ConversationView:
    record = await ConversationRepository(session).create(request.title)
    await session.commit()
    return ConversationView.model_validate(record)


@router.get("/{conversation_id}/messages", response_model=list[MessageView])
async def list_messages(
    conversation_id: str,
    session: AsyncSession = Depends(get_db),
) -> list[MessageView]:
    repository = ConversationRepository(session)
    if not await repository.get(conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return [MessageView.model_validate(item) for item in await repository.messages(conversation_id)]


@router.post("/{conversation_id}/messages/stream")
async def stream_message(
    conversation_id: str,
    request: ChatRequest,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    conversations = ConversationRepository(session)
    conversation = await conversations.get(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    configuration = await SettingsRepository(session).get_model_provider()
    if not configuration:
        raise HTTPException(status_code=409, detail="Configure a model provider in Settings.")
    try:
        provider = create_provider(configuration)
    except ProviderConfigurationError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    aws_config = await SettingsRepository(session).get_aws_profile()
    aws_profile = aws_config.profile_name if aws_config else settings.default_aws_profile
    regions = aws_config.regions_json if aws_config else settings.default_aws_regions
    if not aws_profile:
        raise HTTPException(status_code=409, detail="Configure an AWS profile in Settings.")

    await conversations.add_message(conversation_id, "user", request.content)
    conversation.provider = configuration.provider
    conversation.model = configuration.model
    run = await conversations.create_run(
        conversation_id,
        configuration.provider,
        configuration.model,
    )
    history_records = await conversations.messages(conversation_id)
    history = [{"role": item.role, "content": item.content} for item in history_records]
    await session.commit()
    run_id = run.id

    loop = AgentLoop(
        provider=provider,
        mcp=LocalMcpClient(settings),
        aws_profile=aws_profile,
        regions=regions,
        model=configuration.model,
        max_iterations=settings.max_agent_iterations,
        max_tokens=settings.model_max_tokens,
        max_tool_result_chars=settings.max_tool_result_chars,
    )

    async def events() -> AsyncIterator[str]:
        try:
            async for event in loop.run(history):
                if event["type"] == "tool_completed":
                    async with SessionFactory() as stream_session:
                        await ConversationRepository(stream_session).record_tool_execution(
                            run_id=run_id,
                            tool_name=event["tool"],
                            status=event["status"],
                            arguments=event["arguments"],
                            result=event["result"],
                            duration_ms=event["duration_ms"],
                        )
                        await stream_session.commit()
                elif event["type"] == "message":
                    async with SessionFactory() as stream_session:
                        await ConversationRepository(stream_session).add_message(
                            conversation_id,
                            "assistant",
                            event["content"],
                        )
                        await stream_session.commit()
                elif event["type"] == "done":
                    async with SessionFactory() as stream_session:
                        await ConversationRepository(stream_session).finish_run(
                            run_id,
                            status="completed",
                            usage=event["usage"],
                        )
                        await stream_session.commit()
                yield _sse(event)
        except Exception as error:
            async with SessionFactory() as stream_session:
                await ConversationRepository(stream_session).finish_run(
                    run_id,
                    status="failed",
                    error_code=type(error).__name__,
                )
                await stream_session.commit()
            yield _sse(
                {
                    "type": "error",
                    "message": f"Conversation failed: {type(error).__name__}: {error}",
                }
            )

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
