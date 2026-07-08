"""A small hand-rolled tool-using agent. No framework — just a loop."""

from __future__ import annotations

import json

from openai import OpenAI
from tools import TOOL_SCHEMAS, TOOLS

MODEL = "gpt-4o-mini"
SYSTEM_PROMPT = (
    "You are a helpful research assistant. Use the available tools to look "
    "things up before answering. Keep answers short."
)

client = OpenAI()


def run_agent(user_question: str, max_steps: int = 6) -> str:
    """Run the agent until it produces a final answer (or hits max_steps)."""
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_question},
    ]

    for _ in range(max_steps):
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOL_SCHEMAS,
        )
        choice = response.choices[0].message
        messages.append(choice.model_dump(exclude_none=True))

        if not choice.tool_calls:
            return choice.content or ""

        for tool_call in choice.tool_calls:
            name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)
            result = TOOLS[name](**args)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result),
                }
            )

    return "Sorry, I couldn't finish that within the step limit."
