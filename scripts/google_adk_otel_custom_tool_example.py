"""Trace a Google ADK agent with a custom tool to Weave.

This is plain ADK code with one addition: ``weave.init`` at the top.
The Weave integration auto-patches ADK on import and ships every span
ADK emits to the GenAI OTLP endpoint at ``/agents/otel/v1/traces``.

A ``StubLlm`` stands in for a real Gemini / Vertex model so the example
needs no API credentials. In production swap the model and nothing else
changes — the spans ADK emits are identical.

Run:

    uv venv --python 3.12 --clear
    source .venv/bin/activate
    uv pip install -e . 'google-adk>=1.17.0'
    export WANDB_API_KEY=...          # or run ``wandb login`` once
    python scripts/google_adk_otel_custom_tool_example.py

Override the project with ``WEAVE_ADK_EXAMPLE_PROJECT``; defaults to
``megatruong/adk-test``.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from google.adk.agents.llm_agent import LlmAgent
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.runners import InMemoryRunner
from google.adk.tools import FunctionTool
from google.genai import types

import weave

APP_NAME = "adk-otel-demo"
USER_ID = "megatruong"
SESSION_ID = f"conv-custom-tool-{uuid.uuid4().hex[:8]}"


def get_weather(city: str, units: str = "metric") -> dict[str, Any]:
    """Look up the current weather for a city.

    Args:
        city: The city to look up, e.g. "Paris".
        units: ``"metric"`` for Celsius (default) or ``"imperial"`` for
            Fahrenheit.
    """
    fake_db = {
        "Paris": {"c": 18, "conditions": "cloudy"},
        "Tokyo": {"c": 22, "conditions": "sunny"},
        "New York": {"c": 9, "conditions": "rainy"},
    }
    entry = fake_db.get(city, {"c": 15, "conditions": "unknown"})
    if units == "imperial":
        return {
            "city": city,
            "temperature": round(entry["c"] * 9 / 5 + 32, 1),
            "unit": "F",
            "conditions": entry["conditions"],
        }
    return {
        "city": city,
        "temperature": entry["c"],
        "unit": "C",
        "conditions": entry["conditions"],
    }


def convert_currency(
    amount: float, from_currency: str, to_currency: str
) -> dict[str, Any]:
    """Convert an amount between two ISO-4217 currency codes."""
    fake_rates = {("USD", "JPY"): 150.2, ("USD", "EUR"): 0.92, ("USD", "GBP"): 0.79}
    rate = fake_rates.get((from_currency, to_currency))
    if rate is None:
        raise ValueError(f"No rate for {from_currency} -> {to_currency}")
    return {
        "from_currency": from_currency,
        "to_currency": to_currency,
        "rate": rate,
        "amount": round(amount * rate, 2),
    }


class StubLlm(BaseLlm):
    """A scripted LLM that calls each tool in turn, then answers.

    Swap this for ``Gemini(model="gemini-2.0-flash")`` (or any other
    ``BaseLlm`` subclass) to drive a real model.
    """

    @classmethod
    def supported_models(cls) -> list[str]:
        return ["stub-llm"]

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        tool_names_seen = [
            part.function_response.name
            for content in llm_request.contents
            for part in (content.parts or [])
            if part.function_response is not None
        ]

        if not tool_names_seen:
            yield _function_call_response(
                "call-weather-1", "get_weather",
                {"city": "Paris", "units": "metric"},
            )
            return

        if tool_names_seen == ["get_weather"]:
            yield _function_call_response(
                "call-currency-1", "convert_currency",
                {"amount": 1000, "from_currency": "USD", "to_currency": "JPY"},
            )
            return

        yield _text_response(
            "Paris is 18C and cloudy. 1000 USD converts to 150,200 JPY at "
            "today's rate."
        )


def _function_call_response(call_id: str, name: str, args: dict[str, Any]) -> LlmResponse:
    return LlmResponse(
        content=types.Content(
            role="model",
            parts=[
                types.Part(
                    function_call=types.FunctionCall(id=call_id, name=name, args=args)
                )
            ],
        ),
        finish_reason=types.FinishReason.STOP,
    )


def _text_response(text: str) -> LlmResponse:
    return LlmResponse(
        content=types.Content(role="model", parts=[types.Part(text=text)]),
        finish_reason=types.FinishReason.STOP,
    )


async def _run() -> None:
    weave.init(os.environ.get("WEAVE_ADK_EXAMPLE_PROJECT", "megatruong/adk-test"))

    agent = LlmAgent(
        name="trip_planner",
        description="Plans multi-city itineraries with live weather + currency lookup.",
        model=StubLlm(model="stub-llm"),
        tools=[FunctionTool(get_weather), FunctionTool(convert_currency)],
    )

    runner = InMemoryRunner(agent=agent, app_name=APP_NAME)
    await runner.session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
    )

    new_message = types.Content(
        role="user",
        parts=[
            types.Part(
                text="What's the weather in Paris, and how much is 1000 USD in JPY?"
            )
        ],
    )

    final_text = ""
    async for event in runner.run_async(
        user_id=USER_ID, session_id=SESSION_ID, new_message=new_message
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    final_text = part.text

    print(f"\nFinal answer: {final_text}")
    print(f"Conversation id: {SESSION_ID}")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
