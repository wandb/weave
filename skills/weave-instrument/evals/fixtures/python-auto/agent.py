"""A research agent built on the OpenAI Agents SDK."""

from __future__ import annotations

import asyncio

from agents import Agent, Runner, function_tool


@function_tool
def get_weather(city: str) -> str:
    """Get the current weather for a city."""
    return f"The weather in {city} is 72F and sunny."


@function_tool
def search_wiki(query: str) -> str:
    """Search an encyclopedia for a topic."""
    return f"A short summary about {query}."


research_agent = Agent(
    name="research-assistant",
    instructions=(
        "You are a helpful research assistant. Use the tools to look things "
        "up before answering. Keep answers short."
    ),
    tools=[get_weather, search_wiki],
)


async def main() -> None:
    questions = [
        "What's the weather in Tokyo, and one fact about the city?",
        "What's the weather in Paris?",
    ]
    for question in questions:
        print(f"USER:  {question}")
        result = await Runner.run(research_agent, question)
        print(f"AGENT: {result.final_output}\n")


if __name__ == "__main__":
    asyncio.run(main())
