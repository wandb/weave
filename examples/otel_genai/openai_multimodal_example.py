# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "openai-agents",
#     "openai",
#     "opentelemetry-instrumentation-openai-agents-v2",
#     "opentelemetry-sdk",
#     "opentelemetry-exporter-otlp-proto-grpc",
#     "opentelemetry-exporter-otlp-proto-http",
#     "weave @ file:///Users/ben/repos/core/services/weave-python/weave-public",
# ]
# ///
"""OpenAI Agents with multimodal tools + weave.otel media capture.

Creates an agent with:
  - DALL-E image generation (via custom function_tool)
  - Text-to-speech (via custom function_tool wrapping the TTS API)

Demonstrates weave.otel.log_content(): upload media bytes to the Weave
file store and attach content-addressed references to the active OTel span.

Usage:
    uv run --python 3.12 openai_multimodal_example.py
    uv run --python 3.12 openai_multimodal_example.py --genai-endpoint http://localhost:6345/otel/v1/genai/traces
"""

import argparse
import asyncio
import base64
import os
import tempfile

import openai
import requests as http_requests
from agents import Agent, Runner, function_tool

from weave.otel import log_content, setup_tracing

# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@function_tool
def text_to_speech(text: str, voice: str = "alloy") -> str:
    """Generate speech audio from text using OpenAI TTS.

    Args:
        text: The text to convert to speech.
        voice: Voice to use (alloy, echo, fable, onyx, nova, shimmer).

    Returns:
        Description of the generated audio.
    """
    client = openai.OpenAI()
    response = client.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice=voice,
        input=text,
        instructions="Speak clearly and naturally.",
    )

    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    response.stream_to_file(tmp.name)
    with open(tmp.name, "rb") as f:
        audio_bytes = f.read()

    log_content(audio_bytes, key="tts_audio", media_type="audio/mpeg", role="output")

    return f"Audio generated successfully ({len(audio_bytes):,} bytes, voice={voice})."


@function_tool
def generate_image(prompt: str) -> str:
    """Generate an image from a text description using DALL-E.

    Args:
        prompt: Detailed description of the image to generate.

    Returns:
        Description of the generated image.
    """
    client = openai.OpenAI()
    result = client.images.generate(
        model="gpt-image-1",
        prompt=prompt,
        n=1,
        size="1024x1024",
        quality="low",
    )

    image_data = result.data[0]
    if image_data.b64_json:
        image_bytes = base64.b64decode(image_data.b64_json)
    elif image_data.url:
        image_bytes = http_requests.get(image_data.url, timeout=30).content
    else:
        return "Image generation returned no data."

    log_content(image_bytes, key="generated_image", media_type="image/png", role="output")

    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp.write(image_bytes)
    tmp.close()
    print(f"  [generate_image] Saved {len(image_bytes):,} bytes -> {tmp.name}")

    return f"Image generated successfully ({len(image_bytes):,} bytes). Saved to {tmp.name}"


# ---------------------------------------------------------------------------
# Agent + main
# ---------------------------------------------------------------------------

creative_agent = Agent(
    name="CreativeAgent",
    instructions=(
        "You are a creative multimedia agent. When asked to create something visual, "
        "use the generate_image tool. When asked to create audio or speech, "
        "use the text_to_speech tool. Be creative and descriptive. After generating "
        "media, describe what you created briefly."
    ),
    tools=[generate_image, text_to_speech],
    model="gpt-4o-mini",
)


async def run_agents() -> None:
    """Run multimodal queries to exercise both image and audio capture."""
    queries = [
        "Generate an image of a cute robot painting a sunset on a canvas.",
        "Say 'Hello! Welcome to the future of AI agents.' in a friendly voice.",
    ]

    for q in queries:
        print(f"\n{'='*60}")
        print(f"User: {q}")
        print(f"{'='*60}")
        result = await Runner.run(creative_agent, q)
        print(f"\nAgent: {result.final_output}\n")


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(description="OpenAI multimodal OTel example")
    parser.add_argument("--otlp-endpoint", type=str, default=None)
    parser.add_argument("--genai-endpoint", type=str, default=None)
    args = parser.parse_args()

    os.environ.setdefault(
        "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "span_and_event"
    )

    provider = setup_tracing(
        service_name="openai-multimodal-otel-example",
        project="genai-otel-test",
        genai_endpoint=args.genai_endpoint,
        otlp_endpoint=args.otlp_endpoint,
    )

    from opentelemetry.instrumentation.openai_agents import OpenAIAgentsInstrumentor

    OpenAIAgentsInstrumentor().instrument(tracer_provider=provider)

    asyncio.run(run_agents())
    provider.force_flush()
    provider.shutdown()


if __name__ == "__main__":
    main()
