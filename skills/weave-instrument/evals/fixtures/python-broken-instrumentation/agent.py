"""A working agent with intentionally broken Weave instrumentation."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field

from openai import AsyncOpenAI

import weave
from weave.integrations import patch_openai


@dataclass(frozen=True)
class TraceSettings:
    project: str
    tracing_api_key: str
    sharing_with_wandb_allowed: bool


@dataclass(frozen=True)
class ToolRecord:
    name: str
    arguments: str
    result: str


@dataclass(frozen=True)
class AgentResult:
    output: str
    state: str
    tool_records: list[ToolRecord] = field(default_factory=list)


async def lookup_account(account_id: str) -> str:
    """Simulate the real tool boundary, including observable latency."""
    await asyncio.sleep(0.05)
    if account_id == "raise":
        raise RuntimeError("account lookup failed")
    return f"account:{account_id}"


class Runner:
    def __init__(self) -> None:
        self._client = AsyncOpenAI()

    async def run(self, prompt: str) -> AgentResult:
        response = await self._client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
        )
        output = response.choices[0].message.content or ""
        tool_records: list[ToolRecord] = []
        if prompt.startswith("lookup:"):
            account_id = prompt.removeprefix("lookup:")
            tool_records.append(
                ToolRecord(
                    name="lookup_account",
                    arguments=account_id,
                    result=await lookup_account(account_id),
                )
            )
        state = "cancelled" if prompt == "/cancel" else "completed"
        return AgentResult(output=output, state=state, tool_records=tool_records)


def configure_weave(settings: TraceSettings) -> None:
    # Broken: this replaces the W&B identity used by the rest of the process.
    os.environ["WANDB_API_KEY"] = settings.tracing_api_key
    weave.init(
        settings.project,
        settings={"implicitly_patch_integrations": False},
    )
    # Broken: this produces legacy Calls spans, not a child chat span.
    patch_openai()


async def handle_turn(
    prompt: str, runner: Runner, settings: TraceSettings
) -> AgentResult:
    # Broken: the sharing policy is ignored and initialization happens per turn.
    configure_weave(settings)

    # Broken: model and tool work finishes before the Session turn even starts.
    result = await runner.run(prompt)
    with weave.start_conversation(agent_name="support-agent") as conversation:
        with conversation.start_turn(user_message=prompt) as turn:
            for record in result.tool_records:
                with turn.start_tool(
                    name=record.name,
                    arguments=record.arguments,
                ) as tool:
                    tool.result = record.result
            # Broken: returned cancelled/errored states are not recorded.
    return result
