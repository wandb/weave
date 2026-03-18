# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "openai-agents",
#     "openai",
#     "opentelemetry-instrumentation-openai-agents-v2",
#     "opentelemetry-sdk",
#     "opentelemetry-exporter-otlp-proto-grpc",
#     "opentelemetry-exporter-otlp-proto-http",
#     "requests",
# ]
# ///
"""OpenAI Agents with multimodal tools + weave.otel-style media capture.

Creates an agent with:
  - DALL-E image generation (via built-in ImageGenerationTool)
  - Text-to-speech (via custom function_tool wrapping the TTS API)

Demonstrates the weave.otel.log_content() pattern: upload media bytes to
the Weave file store and attach content-addressed references to the active
OTel span via ``weave.content_refs`` attributes.

Usage:
    uv run --python 3.12 openai_multimodal_example.py
    uv run --python 3.12 openai_multimodal_example.py --genai-endpoint http://localhost:6345/otel/v1/genai/traces
"""

import argparse
import asyncio
import hashlib
import io
import json
import os
import tempfile

import openai
import requests as http_requests
from agents import Agent, Runner, function_tool
from agents.tool import ImageGeneration, ImageGenerationTool
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter as OTLPHTTPSpanExporter,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)


# ---------------------------------------------------------------------------
# Inline weave.otel.log_content() for standalone scripts.
# When weave is installed as a package, use weave.otel.log_content() instead.
# ---------------------------------------------------------------------------

def _weave_digest(content: bytes) -> str:
    """Content-addressed digest matching weave.shared.digest.bytes_digest."""
    import base64

    hash_bytes = hashlib.sha256(content).digest()
    b64 = base64.urlsafe_b64encode(hash_bytes).decode("utf-8")
    return b64.replace("-", "X").replace("_", "Y").rstrip("=")


def log_content(
    data: bytes,
    *,
    key: str | None = None,
    media_type: str = "application/octet-stream",
    role: str = "output",
) -> str | None:
    """Upload content and attach a ref to the active OTel span.

    Standalone version of weave.otel.log_content() for use in example scripts.
    """
    span = trace.get_current_span()
    if not span or not span.is_recording():
        return None

    digest = _weave_digest(data)

    resource = getattr(span, "resource", None)
    if resource:
        entity = resource.attributes.get("wandb.entity", "")
        project = resource.attributes.get("wandb.project", "")
        project_id = f"{entity}/{project}" if entity and project else None
    else:
        project_id = None

    if project_id:
        import base64 as b64lib

        server_url = os.environ.get("WF_TRACE_SERVER_URL", "http://localhost:6345")
        api_key = os.environ.get("WANDB_API_KEY", "")
        headers = {}
        if api_key:
            creds = b64lib.b64encode(f"api:{api_key}".encode()).decode()
            headers["Authorization"] = f"Basic {creds}"
        try:
            http_requests.post(
                f"{server_url}/file/create",
                files={"file": ("content", io.BytesIO(data), media_type)},
                data={"project_id": project_id},
                headers=headers,
                timeout=30,
            )
        except Exception as e:
            print(f"  [log_content] Upload failed: {e}")

    ref_entry = {"digest": digest, "media_type": media_type, "role": role, "size_bytes": len(data)}
    if key:
        ref_entry["key"] = key

    existing_raw = span.attributes.get("weave.content_refs") if hasattr(span, "attributes") else None
    existing = json.loads(existing_raw) if existing_raw else []
    existing.append(ref_entry)
    span.set_attribute("weave.content_refs", json.dumps(existing))

    print(f"  [log_content] Stored {len(data):,} bytes as {key or media_type} (digest={digest[:12]}...)")
    return digest


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
    audio_bytes = open(tmp.name, "rb").read()

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
    import base64

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
# OTel setup
# ---------------------------------------------------------------------------

def _wandb_auth_headers() -> dict[str, str]:
    """Build auth headers from WANDB_API_KEY if present."""
    api_key = os.environ.get("WANDB_API_KEY", "")
    if api_key:
        return {"wandb-api-key": api_key}
    return {}


def setup_otel(
    otlp_endpoint: str | None = None,
    genai_endpoint: str | None = None,
) -> TracerProvider:
    """Configure OTel TracerProvider."""
    entity = os.environ.get("WANDB_ENTITY", "ben-urmomsclothes")
    resource = Resource.create(
        {
            "service.name": "openai-multimodal-otel-example",
            "service.version": "0.1.0",
            "wandb.entity": entity,
            "wandb.project": "genai-otel-test",
        }
    )
    provider = TracerProvider(resource=resource)

    if genai_endpoint:
        provider.add_span_processor(
            BatchSpanProcessor(
                OTLPHTTPSpanExporter(
                    endpoint=genai_endpoint,
                    headers=_wandb_auth_headers(),
                )
            )
        )
    elif otlp_endpoint:
        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint))
        )
    else:
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    return provider


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

    provider = setup_otel(args.otlp_endpoint, args.genai_endpoint)

    from opentelemetry.instrumentation.openai_agents import OpenAIAgentsInstrumentor

    OpenAIAgentsInstrumentor().instrument(tracer_provider=provider)

    asyncio.run(run_agents())
    provider.force_flush()
    provider.shutdown()


if __name__ == "__main__":
    main()
