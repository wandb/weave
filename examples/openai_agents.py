# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "weave",
#     "openai",
#     "openai-agents>=0.14.7",
# ]
#
# # Resolve `weave` against this checkout (../) instead of PyPI, so local
# # edits to the SDK are picked up without a release/install cycle.
# [tool.uv.sources]
# weave = { path = "..", editable = true }
# ///
"""
Example: OpenAI Agents Integration with Weave (Python)

    uv run examples/openai_agents.py

Required env:

    WANDB_API_KEY            — your wandb API key
    OPENAI_API_KEY           — your openai API key
    WANDB_PROJECT            — optional; defaults to ``example``
"""

import asyncio
import os
import re
from typing import Literal

from agents import Agent, Runner, function_tool, gen_trace_id, trace

import weave

WANDB_PROJECT = os.environ.get("WANDB_PROJECT", "example-python-agent")


# --- Tools ---


@function_tool
def get_weather(city: str, unit: Literal["celsius", "fahrenheit"]) -> str:
    """Get the current weather for a given city.

    Args:
        city: The name of the city.
        unit: Temperature unit, either ``celsius`` or ``fahrenheit``.
    """
    weather = {
        "San Francisco": {"temp": 18, "condition": "Foggy"},
        "New York": {"temp": 22, "condition": "Sunny"},
        "London": {"temp": 12, "condition": "Cloudy"},
        "Tokyo": {"temp": 28, "condition": "Humid"},
    }

    data = weather.get(city, {"temp": 20, "condition": "Clear"})
    temp = round(data["temp"] * 9 / 5 + 32) if unit == "fahrenheit" else data["temp"]
    unit_label = "°F" if unit == "fahrenheit" else "°C"

    return f"{city}: {data['condition']}, {temp}{unit_label}"


@function_tool
def calculate(expression: str) -> str:
    """Evaluate a basic arithmetic expression.

    Args:
        expression: A math expression, e.g. ``"3 * (4 + 2)"``.
    """
    # NOTE: ``eval`` is unsafe in production. In a real application, use a
    # proper math library (e.g. ``sympy``) instead.
    if not re.match(r"^[\d\s+\-*/().]+$", expression):
        return "Error: invalid expression"
    try:
        result = eval(expression, {"__builtins__": {}}, {})  # noqa: S307
    except Exception:
        return "Error: could not evaluate expression"
    return f"{expression} = {result}"


# --- Agent ---


async def main() -> None:
    weave.init(WANDB_PROJECT)

    agent = Agent(
        name="Assistant",
        instructions=(
            "You are a helpful assistant. Use the available tools when "
            "appropriate to answer questions accurately."
        ),
        tools=[get_weather, calculate],
    )

    queries = [
        "What's the temperature difference between Tokyo and San Francisco in "
        "celsius? Use the calculator to subtract.",
        "If the temperature in London tripled, what would it be? Get the "
        "weather first, then use the calculator.",
    ]

    # Group all runs under a single conversation trace so they share a
    # ``group_id`` in Weave — equivalent to passing ``groupId`` to the TS
    # ``Runner`` constructor.
    with trace("Conversation", group_id=gen_trace_id()):
        history: list = []
        for query in queries:
            print(f"\nQuery: {query}")
            result = await Runner.run(agent, query)
            history = result.to_input_list()
            print(f"Answer: {result.final_output}")

    # ``history`` is collected for parity with the TS example; it is not used
    # in subsequent queries there either.
    _ = history


if __name__ == "__main__":
    asyncio.run(main())
