from __future__ import annotations

from typing import Any

import pytest
from opslens.mcp_client import McpConnectionInfo, McpToolDescription
from opslens.orchestration.agent import AgentLoop
from opslens.providers.base import ProviderResponse, ToolCall


class FakeProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, **_kwargs: Any) -> ProviderResponse:
        self.calls += 1
        if self.calls == 1:
            return ProviderResponse(
                content=[
                    {
                        "type": "tool_use",
                        "id": "call-1",
                        "name": "list_cloudwatch_alarms",
                        "input": {"region": "ap-south-1"},
                    }
                ],
                text="",
                tool_calls=[
                    ToolCall(
                        id="call-1",
                        name="list_cloudwatch_alarms",
                        arguments={"region": "ap-south-1"},
                    )
                ],
                usage={"input_tokens": 10, "output_tokens": 4},
            )
        return ProviderResponse(
            content=[{"type": "text", "text": "No alarms are active."}],
            text="No alarms are active.",
            usage={"input_tokens": 20, "output_tokens": 5},
        )


class FakeMcp:
    async def inspect(self, _aws_profile: str = "") -> McpConnectionInfo:
        return McpConnectionInfo(
            server_name="test-mcp",
            protocol_version="test",
            tools=[
                McpToolDescription(
                    name="list_cloudwatch_alarms",
                    title=None,
                    description="List alarms",
                    input_schema={
                        "type": "object",
                        "properties": {"region": {"type": "string"}},
                    },
                )
            ],
        )

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        _aws_profile: str = "",
    ) -> dict[str, Any]:
        assert name == "list_cloudwatch_alarms"
        assert arguments == {"region": "ap-south-1"}
        return {"status": "ok", "facts": {"resources": []}}


@pytest.mark.asyncio
async def test_agent_executes_tool_and_returns_evidence_based_answer() -> None:
    loop = AgentLoop(
        provider=FakeProvider(),
        mcp=FakeMcp(),
        aws_profile="test-profile",
        regions=["ap-south-1"],
        model="test-model",
        max_iterations=3,
        max_tokens=512,
        max_tool_result_chars=10_000,
    )
    events = [event async for event in loop.run([{"role": "user", "content": "Any alarms?"}])]

    assert [event["type"] for event in events] == [
        "status",
        "tool_started",
        "tool_completed",
        "message",
        "done",
    ]
    assert events[2]["status"] == "succeeded"
    assert events[3]["content"] == "No alarms are active."
    assert events[4]["usage"] == {"input_tokens": 30, "output_tokens": 9}
