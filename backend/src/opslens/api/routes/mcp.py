from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import Settings, get_settings
from ...db import get_db
from ...mcp_client import LocalMcpClient
from ...repositories import SettingsRepository
from ...schemas import McpStatusResponse, McpToolView

router = APIRouter(prefix="/mcp", tags=["mcp"])


@router.get("/status", response_model=McpStatusResponse)
async def mcp_status(
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> McpStatusResponse:
    profile = await SettingsRepository(session).get_aws_profile()
    selected_profile = profile.profile_name if profile else settings.default_aws_profile
    try:
        info = await LocalMcpClient(settings).inspect(selected_profile)
    except Exception as error:
        return McpStatusResponse(
            connected=False,
            message=f"MCP subprocess failed: {type(error).__name__}",
        )
    return McpStatusResponse(
        connected=True,
        server_name=info.server_name,
        protocol_version=info.protocol_version,
        tools=[
            McpToolView(
                name=tool.name,
                title=tool.title,
                description=tool.description,
                input_schema=tool.input_schema,
            )
            for tool in info.tools
        ],
        message=f"Discovered {len(info.tools)} read-only tools over local stdio.",
    )
