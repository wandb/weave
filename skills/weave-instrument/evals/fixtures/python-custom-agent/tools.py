"""Tool implementations and their JSON schemas for the agent."""

from __future__ import annotations


def get_weather(city: str) -> dict:
    """Pretend to look up the weather."""
    return {"city": city, "temp_f": 72, "conditions": "sunny"}


def search_wiki(query: str) -> dict:
    """Pretend to search an encyclopedia."""
    return {"query": query, "summary": f"A short summary about {query}."}


TOOLS = {
    "get_weather": get_weather,
    "search_wiki": search_wiki,
}

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
    {
        "type": "function",
        "function": {
            "name": "search_wiki",
            "description": "Search an encyclopedia for a topic.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
]
