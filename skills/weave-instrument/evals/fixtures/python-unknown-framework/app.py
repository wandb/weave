"""A user app built on our in-house `miniagent` framework."""

from __future__ import annotations

from miniagent import Agent

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather for a city.",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        },
    },
]


def get_weather(city: str) -> dict:
    return {"city": city, "tempF": 72, "conditions": "sunny"}


agent = Agent(
    name="weather-bot",
    model="gpt-4o-mini",
    tools={"get_weather": get_weather},
    schemas=TOOL_SCHEMAS,
)


def main() -> None:
    for question in ["What's the weather in Tokyo?", "And in Paris?"]:
        print(f"USER:  {question}")
        print(f"AGENT: {agent.run(question)}\n")


if __name__ == "__main__":
    main()
