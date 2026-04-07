# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "google-adk>=1.0",
#     "opentelemetry-sdk",
#     "opentelemetry-exporter-otlp-proto-grpc",
#     "opentelemetry-exporter-otlp-proto-http",
#     "Pillow",
#     "weave",
# ]
# ///
"""Google ADK — multi-turn conversation with subagent delegation, all OTel traced.

Demonstrates:
  - Multi-turn conversation via a persistent ADK session (context carries across turns)
  - LLM-driven delegation to specialist sub_agents
  - Tool calls within a conversation that builds on prior context
  - Media capture via weave.otel.log_content()
  - Automatic system prompt, tool definition, and conversation tracking

All of this is set up with a single ``instrument()`` call — agent metadata
(instructions, tools, sub_agents) is auto-discovered from the LlmAgent objects.

The conversation is designed so each turn builds on prior context:
  1. Ask about weather in Tokyo and Paris
  2. Follow up asking which is warmer + calculate temperature difference
  3. Ask for the temperature in Fahrenheit converted to Celsius
  4. Generate an image of the warmer city at sunset
  5. Summarize the conversation

Usage:
    uv run --python 3.12 google_adk_example.py
    uv run --python 3.12 google_adk_example.py --genai-endpoint http://localhost:6345/otel/v1/genai/traces
"""

import argparse
import asyncio
import tempfile

from weave.agents import log_content, setup_tracing
from weave.agents.instrumentors.google_adk import instrument

# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


def get_weather(city: str) -> str:
    """Get the current weather for a city.

    Args:
        city: Name of the city.

    Returns:
        Weather description string.
    """
    forecasts = {
        "san francisco": "Foggy, 58°F, wind 12 mph W",
        "tokyo": "Clear, 75°F, humidity 45%",
        "london": "Rainy, 52°F, wind 8 mph SW",
        "paris": "Overcast, 61°F, light drizzle",
        "barcelona": "Sunny, 82°F, UV index 7",
    }
    return forecasts.get(city.lower(), f"Partly cloudy, 68°F in {city}")


def calculator(expression: str) -> str:
    """Evaluate an arithmetic expression safely.

    Args:
        expression: A mathematical expression like '42 * 17' or '(3 + 4) * 2'.

    Returns:
        The result as a string.
    """
    allowed = set("0123456789+-*/.(). ")
    if not all(c in allowed for c in expression):
        return f"Error: invalid characters in expression: {expression}"
    try:
        result = eval(expression)
        return str(result)
    except Exception as e:
        return f"Error: {e}"


def generate_image(prompt: str) -> str:
    """Generate an image from a text description using Gemini.

    Args:
        prompt: Detailed description of the image to generate.

    Returns:
        Description of the generated image.
    """
    from google import genai
    from google.genai.types import GenerateContentConfig, Modality

    client = genai.Client()
    response = client.models.generate_content(
        model="gemini-2.5-flash-image",
        contents=f"Generate an image: {prompt}",
        config=GenerateContentConfig(
            response_modalities=[Modality.TEXT, Modality.IMAGE],
        ),
    )

    description_parts = []
    image_count = 0
    for part in response.candidates[0].content.parts:
        if part.inline_data:
            image_bytes = part.inline_data.data
            mime = part.inline_data.mime_type or "image/png"
            ext = "png" if "png" in mime else "jpeg"
            key = (
                f"generated_image_{image_count}"
                if image_count > 0
                else "generated_image"
            )

            log_content(image_bytes, key=key, media_type=mime, role="output")

            tmp = tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False)
            tmp.write(image_bytes)
            tmp.close()
            print(f"  [generate_image] Saved {len(image_bytes):,} bytes -> {tmp.name}")
            description_parts.append(
                f"Image generated ({len(image_bytes):,} bytes, {mime})"
            )
            image_count += 1
        elif part.text:
            description_parts.append(part.text)

    if not description_parts:
        return "Image generation returned no results."

    return " ".join(description_parts)


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------


def build_agents():
    """Build the multi-agent hierarchy."""
    from google.adk.agents import LlmAgent

    weather_agent = LlmAgent(
        name="WeatherAgent",
        model="gemini-2.0-flash",
        description="Specialist for weather forecasts and conditions in any city.",
        instruction=(
            "You are a weather specialist. Use the get_weather tool to look "
            "up weather for cities. Give a short, friendly answer."
        ),
        tools=[get_weather],
    )

    math_agent = LlmAgent(
        name="MathAgent",
        model="gemini-2.0-flash",
        description="Specialist for arithmetic calculations and math questions.",
        instruction=(
            "You are a math specialist. Use the calculator tool to evaluate "
            "arithmetic expressions. Show your work briefly."
        ),
        tools=[calculator],
    )

    creative_agent = LlmAgent(
        name="CreativeAgent",
        model="gemini-2.0-flash",
        description="Specialist for generating images from text descriptions.",
        instruction=(
            "You are a creative image specialist. Use the generate_image tool "
            "to create images from descriptions. After generating, briefly "
            "describe what was created."
        ),
        tools=[generate_image],
    )

    coordinator = LlmAgent(
        name="Coordinator",
        model="gemini-2.0-flash",
        description="Routes requests to the appropriate specialist agent.",
        instruction=(
            "You are a helpful coordinator. Based on the user's request, "
            "delegate to the appropriate specialist:\n"
            "  - WeatherAgent for weather questions\n"
            "  - MathAgent for calculations and math\n"
            "  - CreativeAgent for image generation and visual content\n\n"
            "Always delegate — do not answer directly."
        ),
        sub_agents=[weather_agent, math_agent, creative_agent],
    )

    return coordinator


# Multi-turn conversation: each turn builds on prior context
CONVERSATION = [
    "What's the weather in Tokyo and Paris?",
    "Which city is warmer? Use the calculator to convert both temperatures from Fahrenheit to Celsius.",
    "What is (42 * 17) + (256 / 8)?",
    "Generate an image of the warmer city at sunset with cherry blossoms.",
    "Summarize everything we've discussed so far in this conversation.",
]


async def run_conversation(coordinator) -> None:
    """Run a multi-turn conversation that reuses a single ADK session."""
    from google.adk.runners import InMemoryRunner
    from google.genai import types

    runner = InMemoryRunner(agent=coordinator, app_name="multi_agent_app")

    session = await runner.session_service.create_session(
        app_name="multi_agent_app",
        user_id="user1",
    )

    for i, query in enumerate(CONVERSATION, 1):
        print(f"\n{'=' * 60}")
        print(f"Turn {i}/{len(CONVERSATION)}")
        print(f"User: {query}")
        print(f"{'=' * 60}")

        user_message = types.Content(
            role="user",
            parts=[types.Part(text=query)],
        )

        async for event in runner.run_async(
            user_id="user1",
            session_id=session.id,
            new_message=user_message,
        ):
            if event.is_final_response() and event.content:
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        print(f"\nAgent: {part.text.strip()}\n")

    final_session = await runner.session_service.get_session(
        app_name="multi_agent_app",
        user_id="user1",
        session_id=session.id,
    )
    if final_session:
        print(f"\n{'=' * 60}")
        print(
            f"Session has {len(final_session.events)} events after {len(CONVERSATION)} turns"
        )
        print(f"{'=' * 60}")


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(description="Google ADK OTel example")
    parser.add_argument("--otlp-endpoint", type=str, default=None)
    parser.add_argument("--genai-endpoint", type=str, default=None)
    args = parser.parse_args()

    provider = setup_tracing(
        service_name="google-adk-otel-example",
        project="genai-otel-test",
        genai_endpoint=args.genai_endpoint,
        otlp_endpoint=args.otlp_endpoint,
    )

    coordinator = build_agents()

    # One call: auto-discovers instructions, tools, sub_agents from the
    # agent tree. Also patches Gemini media capture and sets up
    # conversation stitching.
    instrument(provider, agents=[coordinator], conversation="adk-multi-agent")

    asyncio.run(run_conversation(coordinator))

    provider.force_flush()
    provider.shutdown()


if __name__ == "__main__":
    main()
