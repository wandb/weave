# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "google-adk>=1.0",
#     "opentelemetry-sdk",
#     "opentelemetry-exporter-otlp-proto-grpc",
#     "opentelemetry-exporter-otlp-proto-http",
#     "Pillow",
#     "weave @ file:///Users/ben/repos/core/services/weave-python/weave-public",
# ]
# ///
"""Google ADK with subagents, delegation, multimodal tools — all OTel traced.

Creates a multi-agent system with LLM-driven delegation:
  - Coordinator: routes to specialists via sub_agents
  - WeatherAgent: looks up weather via a tool
  - CreativeAgent: generates images and describes them
  - MathAgent: performs arithmetic via a calculator tool

Demonstrates media capture via weave.otel.log_content() and manual system
prompt attribution via SystemPromptInjector.

NOTE: System prompts / agent instructions are manually injected because
Google ADK's native OTel tracing does not emit gen_ai.system_instructions.
The OTel GenAI spec defines this attribute (semantic-conventions PR #2179)
but neither ADK nor any other instrumentor implements it yet:
  - https://github.com/open-telemetry/semantic-conventions/pull/2179
  - https://github.com/google/adk-python/pull/2575

Usage:
    uv run --python 3.12 google_adk_example.py
    uv run --python 3.12 google_adk_example.py --genai-endpoint http://localhost:6345/otel/v1/genai/traces
"""

import argparse
import asyncio
import tempfile

from weave.otel import SystemPromptInjector, log_content, setup_tracing

# ---------------------------------------------------------------------------
# Agent instructions (defined before OTel setup for the injector)
# ---------------------------------------------------------------------------

COORDINATOR_INSTRUCTIONS = (
    "You are a helpful coordinator. Based on the user's request, "
    "delegate to the appropriate specialist:\n"
    "  - WeatherAgent for weather questions\n"
    "  - MathAgent for calculations and math\n"
    "  - CreativeAgent for image generation and visual content\n\n"
    "Always delegate — do not answer directly."
)

WEATHER_INSTRUCTIONS = (
    "You are a weather specialist. Use the get_weather tool to look "
    "up weather for cities. Give a short, friendly answer."
)

MATH_INSTRUCTIONS = (
    "You are a math specialist. Use the calculator tool to evaluate "
    "arithmetic expressions. Show your work briefly."
)

CREATIVE_INSTRUCTIONS = (
    "You are a creative image specialist. Use the generate_image tool "
    "to create images from descriptions. After generating, briefly "
    "describe what was created."
)

AGENT_INSTRUCTIONS = {
    "Coordinator": COORDINATOR_INSTRUCTIONS,
    "WeatherAgent": WEATHER_INSTRUCTIONS,
    "MathAgent": MATH_INSTRUCTIONS,
    "CreativeAgent": CREATIVE_INSTRUCTIONS,
}


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
            key = f"generated_image_{image_count}" if image_count > 0 else "generated_image"

            log_content(image_bytes, key=key, media_type=mime, role="output")

            tmp = tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False)
            tmp.write(image_bytes)
            tmp.close()
            print(f"  [generate_image] Saved {len(image_bytes):,} bytes -> {tmp.name}")
            description_parts.append(f"Image generated ({len(image_bytes):,} bytes, {mime})")
            image_count += 1
        elif part.text:
            description_parts.append(part.text)

    if not description_parts:
        return "Image generation returned no results."

    return " ".join(description_parts)


# ---------------------------------------------------------------------------
# Agent construction
# ---------------------------------------------------------------------------

def build_agents():
    """Build the multi-agent hierarchy. Call after OTel is configured."""
    from google.adk.agents import LlmAgent

    weather_agent = LlmAgent(
        name="WeatherAgent",
        model="gemini-2.0-flash",
        description="Specialist for weather forecasts and conditions in any city.",
        instruction=WEATHER_INSTRUCTIONS,
        tools=[get_weather],
    )

    math_agent = LlmAgent(
        name="MathAgent",
        model="gemini-2.0-flash",
        description="Specialist for arithmetic calculations and math questions.",
        instruction=MATH_INSTRUCTIONS,
        tools=[calculator],
    )

    creative_agent = LlmAgent(
        name="CreativeAgent",
        model="gemini-2.0-flash",
        description="Specialist for generating images from text descriptions.",
        instruction=CREATIVE_INSTRUCTIONS,
        tools=[generate_image],
    )

    coordinator = LlmAgent(
        name="Coordinator",
        model="gemini-2.0-flash",
        description="Routes requests to the appropriate specialist agent.",
        instruction=COORDINATOR_INSTRUCTIONS,
        sub_agents=[weather_agent, math_agent, creative_agent],
    )

    return coordinator


async def run_agents(coordinator) -> None:
    """Run queries including multimodal image generation."""
    from google.adk.runners import InMemoryRunner
    from google.genai import types

    runner = InMemoryRunner(agent=coordinator, app_name="multi_agent_app")

    queries = [
        "What's the weather in Tokyo and Paris?",
        "What is (42 * 17) + (256 / 8)?",
        "Generate an image of a futuristic city at sunset with flying cars.",
    ]

    for q in queries:
        print(f"\n{'='*60}")
        print(f"User: {q}")
        print(f"{'='*60}")

        session = await runner.session_service.create_session(
            app_name="multi_agent_app",
            user_id="user1",
        )

        user_message = types.Content(
            role="user",
            parts=[types.Part(text=q)],
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
        processors=[SystemPromptInjector(AGENT_INSTRUCTIONS)],
    )

    coordinator = build_agents()
    asyncio.run(run_agents(coordinator))

    provider.force_flush()
    provider.shutdown()


if __name__ == "__main__":
    main()
