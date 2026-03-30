# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "claude-agent-sdk>=0.1.0",
#     "opentelemetry-sdk",
#     "opentelemetry-exporter-otlp-proto-http",
#     "weave",
# ]
# ///
"""Claude Agent SDK — multi-turn conversation with tool use, all OTel traced.

Demonstrates:
  - Multi-turn conversation that builds on prior context
  - Tool use tracing (Bash, Read) with arguments and results
  - System prompt and allowed-tools extraction into gen_ai.* attributes
  - Token usage tracking (input_tokens, output_tokens, cache tokens)
  - Conversation stitching across turns

The conversation is designed so each turn builds on prior context:
  1. Check what files are in the current directory (uses Bash)
  2. Read a specific file found in turn 1 (uses Read)
  3. Summarize what we've learned (no tools, tests context carryover)

Prerequisites:
  - Claude Code must be installed and authenticated (``claude auth login``)
  - The SDK uses OAuth auth, not ANTHROPIC_API_KEY

Usage:
    devall uv run --group otel-genai python examples/otel_genai/claude_agent_sdk_example.py
"""

import asyncio
import os

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

from weave.agents import setup_tracing
from weave.agents.instrumentors.claude import instrument


def print_messages(msg: object) -> None:
    """Print a streamed message in a readable format."""
    msg_type = type(msg).__name__
    if hasattr(msg, "content"):
        if isinstance(msg.content, str):
            print(f"  [{msg_type}] {msg.content[:300]}")
        elif isinstance(msg.content, list):
            for block in msg.content:
                block_type = type(block).__name__
                if hasattr(block, "text"):
                    print(f"  Agent: {block.text[:300]}")
                elif hasattr(block, "thinking"):
                    print(f"  [{block_type}] (thinking...)")
                elif hasattr(block, "name"):
                    input_preview = ""
                    if hasattr(block, "input") and isinstance(block.input, dict):
                        input_preview = str(block.input)[:100]
                    print(f"  [Tool: {block.name}] {input_preview}")
    elif hasattr(msg, "result"):
        usage = getattr(msg, "usage", {}) or {}
        in_t = usage.get("input_tokens", "?")
        out_t = usage.get("output_tokens", "?")
        print(
            f"  [{msg_type}] turns={getattr(msg, 'num_turns', '?')}, "
            f"tokens={in_t}/{out_t}"
        )


async def main() -> None:
    """Run a multi-turn conversation with tool use."""
    options = ClaudeAgentOptions(
        system_prompt=(
            "You are a concise assistant. When asked to look at files or run "
            "commands, use the tools available. Keep answers to 1-2 sentences."
        ),
        max_turns=3,
        allowed_tools=["Bash", "Read"],
    )

    queries = [
        "List the Python files in the current directory using bash. Just list them, nothing else.",
        "Read the first 5 lines of pyproject.toml and tell me the project name.",
        "Summarize what you've learned about this project in one sentence.",
    ]

    async with ClaudeSDKClient(options=options) as client:
        for i, q in enumerate(queries, 1):
            print(f"\n{'='*60}")
            print(f"Turn {i}/{len(queries)}")
            print(f"User: {q}")
            print(f"{'='*60}")

            await client.query(q)
            async for msg in client.receive_response():
                print_messages(msg)

    print(f"\n{'='*60}")
    print("Done! Check the Weave UI -> genai-otel-test -> claude-multi-turn")
    print(f"{'='*60}")


if __name__ == "__main__":
    trace_server = os.environ.get("WF_TRACE_SERVER_URL", "http://localhost:6345")
    entity = os.environ.get("WANDB_ENTITY", "")

    provider = setup_tracing(
        service_name="claude-agent-sdk-otel-example",
        project="genai-otel-test",
        entity=entity,
        genai_endpoint=f"{trace_server}/otel/v1/genai/traces",
    )

    instrument(provider, conversation="claude-multi-turn")

    asyncio.run(main())

    provider.force_flush()
    provider.shutdown()
