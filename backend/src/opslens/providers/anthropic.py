from __future__ import annotations

from typing import Any

from anthropic import AsyncAnthropic

from .base import ProviderResponse, ToolCall, ToolDefinition


class AnthropicProvider:
    def __init__(self, api_key: str, base_url: str | None = None) -> None:
        arguments: dict[str, Any] = {"api_key": api_key}
        if base_url:
            arguments["base_url"] = base_url
        self.client = AsyncAnthropic(**arguments)

    async def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[ToolDefinition],
        model: str,
        max_tokens: int,
    ) -> ProviderResponse:
        response = await self.client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,  # type: ignore[arg-type]
            tools=[
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.input_schema,
                }
                for tool in tools
            ],  # type: ignore[arg-type]
        )
        content: list[dict[str, Any]] = []
        calls: list[ToolCall] = []
        text_parts: list[str] = []
        for block in response.content:
            if block.type == "text":
                value = {"type": "text", "text": block.text}
                content.append(value)
                text_parts.append(block.text)
            elif block.type == "tool_use":
                arguments = block.input if isinstance(block.input, dict) else {}
                value = {
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": arguments,
                }
                content.append(value)
                calls.append(ToolCall(id=block.id, name=block.name, arguments=arguments))
        return ProviderResponse(
            content=content,
            text="\n".join(text_parts).strip(),
            tool_calls=calls,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
            stop_reason=response.stop_reason,
        )
