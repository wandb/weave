"""Demo script for the Claude Agent SDK Weave integration.

Runs several real Claude Agent SDK queries with Weave tracing enabled,
so you can see what the integration produces in the Weave UI.

Requirements:
  - Claude Code CLI installed and on PATH
  - `pip install claude-agent-sdk`
  - Weave credentials configured (WANDB_API_KEY or `wandb login`)
"""

import asyncio
import os

import claude_agent_sdk
from claude_agent_sdk import ClaudeAgentOptions, ResultMessage

import weave
from weave.integrations.claude_agent_sdk.claude_agent_sdk import (
    get_claude_agent_sdk_patcher,
)


async def run_query(prompt: str, options: ClaudeAgentOptions) -> None:
    """Run a single query and print streamed messages."""
    print(f"\n{'=' * 60}")
    print(f"Prompt: {prompt[:80]}{'...' if len(prompt) > 80 else ''}")
    print("=" * 60)
    async for message in claude_agent_sdk.query(prompt=prompt, options=options):
        name = type(message).__name__
        if isinstance(message, ResultMessage):
            print(f"  [{name}] turns={message.num_turns} cost=${message.total_cost_usd} duration={message.duration_ms}ms")
            if message.result:
                print(f"  Result: {message.result[:120]}{'...' if len(message.result or '') > 120 else ''}")
        else:
            print(f"  [{name}]")


async def main() -> None:
    # 1. Simple factual question — no tools needed
    await run_query(
        prompt="What is 2 + 2? Answer with just the number.",
        options=ClaudeAgentOptions(
            max_turns=1,
            permission_mode="default",
        ),
    )

    # 2. Task that uses Bash tool
    await run_query(
        prompt="Use the Bash tool to run `echo hello world` and tell me what it outputs.",
        options=ClaudeAgentOptions(
            allowed_tools=["Bash"],
            max_turns=3,
            permission_mode="bypassPermissions",
        ),
    )

    # 3. Task that reads a file
    await run_query(
        prompt="Read the file pyproject.toml and tell me the project name.",
        options=ClaudeAgentOptions(
            allowed_tools=["Read"],
            max_turns=3,
            permission_mode="bypassPermissions",
        ),
    )

    # 4. Multi-step task with several tool calls
    await run_query(
        prompt="List the Python files in the current directory using Bash (ls *.py), then count how many there are. If there are none, just say so.",
        options=ClaudeAgentOptions(
            allowed_tools=["Bash"],
            max_turns=5,
            permission_mode="bypassPermissions",
        ),
    )

    # 5. Task with a system prompt
    await run_query(
        prompt="Write a haiku about programming.",
        options=ClaudeAgentOptions(
            system_prompt="You are a poet who only writes haikus. Respond with just the haiku, nothing else.",
            max_turns=1,
            permission_mode="default",
        ),
    )

    # 6. Task with a constrained max_turns that may hit the limit
    await run_query(
        prompt="Use Bash to run `date` and `whoami` and `uname -a`, then summarize the results.",
        options=ClaudeAgentOptions(
            allowed_tools=["Bash"],
            max_turns=2,
            permission_mode="bypassPermissions",
        ),
    )


if __name__ == "__main__":
    weave.init("wandb/weave-claude-agent-sdk1")

    # Ensure the integration is patched
    patcher = get_claude_agent_sdk_patcher()
    patcher.attempt_patch()

    asyncio.run(main())

    print("\nDone! View traces at the Weave UI.")
