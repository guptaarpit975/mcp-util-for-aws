from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Any

from mcp import Client, StdioServerParameters

from .config import Settings


@dataclass(slots=True)
class McpToolDescription:
    name: str
    title: str | None
    description: str | None
    input_schema: dict


@dataclass(slots=True)
class McpConnectionInfo:
    server_name: str | None
    protocol_version: str | None
    tools: list[McpToolDescription]


class LocalMcpClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _parameters(self, aws_profile: str) -> StdioServerParameters:
        environment = {
            "OPSLENS_AWS_PROFILE": aws_profile,
            "OPSLENS_INVENTORY_PAGE_LIMIT": str(self.settings.inventory_page_limit),
        }
        for variable in ("AWS_CONFIG_FILE", "AWS_SHARED_CREDENTIALS_FILE"):
            if value := os.getenv(variable):
                environment[variable] = value
        return StdioServerParameters(
            command=sys.executable,
            args=["-m", "aws_ops_mcp.server"],
            env=environment,
            cwd=self.settings.project_root,
        )

    async def inspect(self, aws_profile: str = "") -> McpConnectionInfo:
        async with Client(
            self._parameters(aws_profile),
            read_timeout_seconds=self.settings.mcp_tool_timeout_seconds,
        ) as client:
            result = await client.list_tools()
            server_info = client.server_info
            return McpConnectionInfo(
                server_name=server_info.name if server_info else None,
                protocol_version=str(client.protocol_version) if client.protocol_version else None,
                tools=[
                    McpToolDescription(
                        name=tool.name,
                        title=tool.title,
                        description=tool.description,
                        input_schema=tool.input_schema,
                    )
                    for tool in result.tools
                ],
            )

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        aws_profile: str = "",
    ) -> Any:
        async with Client(
            self._parameters(aws_profile),
            read_timeout_seconds=self.settings.mcp_tool_timeout_seconds,
        ) as client:
            result = await client.call_tool(name, arguments)
            if result.structured_content is not None:
                return result.structured_content
            return [
                item.model_dump(mode="json") if hasattr(item, "model_dump") else str(item)
                for item in result.content
            ]
