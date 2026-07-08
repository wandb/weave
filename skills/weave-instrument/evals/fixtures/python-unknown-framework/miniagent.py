"""A tiny in-house agent framework. Weave has never heard of it — not a registered integration."""

from __future__ import annotations

import json
from collections.abc import Callable

from openai import OpenAI

_client = OpenAI()


class Agent:
    """Runs a tool-using loop against the OpenAI chat API."""

    def __init__(
        self,
        name: str,
        model: str,
        tools: dict[str, Callable[..., object]],
        schemas: list[dict],
    ) -> None:
        self.name = name
        self.model = model
        self.tools = tools
        self.schemas = schemas

    def run(self, question: str, max_steps: int = 6) -> str:
        messages: list[dict] = [{"role": "user", "content": question}]
        for _ in range(max_steps):
            response = _client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self.schemas,
            )
            message = response.choices[0].message
            messages.append(message.model_dump(exclude_none=True))

            if not message.tool_calls:
                return message.content or ""

            for call in message.tool_calls:
                args = json.loads(call.function.arguments)
                result = self.tools[call.function.name](**args)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": json.dumps(result),
                    }
                )

        return "Sorry, I ran out of steps."
