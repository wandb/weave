# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "google-adk>=1.0",
#     "opentelemetry-sdk",
#     "opentelemetry-exporter-otlp-proto-grpc",
#     "opentelemetry-exporter-otlp-proto-http",
#     "requests",
#     "Pillow",
# ]
# ///
"""Google ADK with subagents, delegation, multimodal tools — all OTel traced.

Creates a multi-agent system with LLM-driven delegation:
  - Coordinator: routes to specialists via sub_agents
  - WeatherAgent: looks up weather via a tool
  - CreativeAgent: generates images and describes them
  - MathAgent: performs arithmetic via a calculator tool

Demonstrates weave.otel.log_content() pattern for capturing generated
images and attaching content references to OTel spans.

Usage:
    uv run --python 3.12 google_adk_example.py
    uv run --python 3.12 google_adk_example.py --genai-endpoint http://localhost:6345/otel/v1/genai/traces
"""

import argparse
import asyncio
import base64
import hashlib
import io
import json
import os
import tempfile

import requests as http_requests
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
# Inline log_content (standalone version of weave.otel.log_content)
# ---------------------------------------------------------------------------

def _weave_digest(content: bytes) -> str:
    """Content-addressed digest matching weave.shared.digest.bytes_digest."""
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
    """Upload content and attach a ref to the active OTel span."""
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
        server_url = os.environ.get("WF_TRACE_SERVER_URL", "http://localhost:6345")
        api_key = os.environ.get("WANDB_API_KEY", "")
        headers = {}
        if api_key:
            creds = base64.b64encode(f"api:{api_key}".encode()).decode()
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
    """Configure OTel TracerProvider. Must be called BEFORE importing ADK."""
    entity = os.environ.get("WANDB_ENTITY", "ben-urmomsclothes")
    resource = Resource.create(
        {
            "service.name": "google-adk-otel-example",
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
        result = eval(expression)  # noqa: S307
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

    provider = setup_otel(args.otlp_endpoint, args.genai_endpoint)

    coordinator = build_agents()
    asyncio.run(run_agents(coordinator))

    provider.force_flush()
    provider.shutdown()


if __name__ == "__main__":
    main()
