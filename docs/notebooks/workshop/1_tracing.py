# %% [markdown]
# # Part 1: Tracing & Debugging with Weave
#
# <img src="http://wandb.me/logo-im-png" width="400" alt="Weights & Biases" />
#
# Learn how to use Weave's automatic tracing capabilities to debug and monitor LLM applications.
#
# **In this section:**
# - 🔍 **Function Tracing**: Automatically track function calls with `@weave.op`
# - 🐛 **Nested Debugging**: Debug complex pipelines with call traces
# - ⚠️ **Exception Tracking**: Monitor and debug failures
# - 🖼️ **Media Support**: Trace multimodal applications with images and audio
# - 🔒 **Custom Serialization**: Control what data gets logged
# - 🔗 **OpenTelemetry**: Integrate with existing observability tools

# %% [markdown]
# ## Setup
#
# Install dependencies and configure API keys.

# %%
# Install dependencies
# %pip install wandb weave openai pydantic nest_asyncio opentelemetry-exporter-otlp 'weave[video_support]' -qqq

import os
from getpass import getpass
from typing import Any

from openai import OpenAI
from pydantic import BaseModel, Field

import weave

# Setup API keys
if not os.environ.get("OPENAI_API_KEY"):
    print("Get your OpenAI API key: https://platform.openai.com/api-keys")
    os.environ["OPENAI_API_KEY"] = getpass("Enter your OpenAI API key: ")

# Initialize Weave - this creates your project and starts tracing
weave_client = weave.init("weave-workshop")

# %% [markdown]
# ## 🔍 Part 1: Function Tracing
#
# Let's start by building a simple LLM application and see how Weave automatically tracks everything.


# %%
# Define our data structure
class CustomerEmail(BaseModel):
    customer_name: str
    product: str
    issue: str
    sentiment: str = Field(description="positive, neutral, or negative")


# 🎯 Track functions with @weave.op
@weave.op
def analyze_customer_email(email: str) -> CustomerEmail:
    """Analyze a customer support email and extract key information."""
    client = OpenAI()

    # 🔥 OpenAI calls are automatically traced by Weave!
    # Weave integrates with dozens of popular AI libraries out of the box
    response = client.beta.chat.completions.parse(
        model="gpt-4o-mini",  # Using mini model for cost efficiency
        messages=[
            {
                "role": "system",
                "content": "Extract customer name, product, issue, and sentiment.",
            },
            {
                "role": "user",
                "content": email,
            },
        ],
        response_format=CustomerEmail,
    )

    return response.choices[0].message.parsed


# Test the function
test_email = """
Hi Support,

I'm really frustrated! My new ProWidget 3000 stopped working after just 2 days.
The screen went black and won't turn on no matter what I try.

Please help!
Sarah Johnson
"""

# 🚀 Run the function - Weave automatically tracks this call
result = analyze_customer_email(test_email)
print(f"Customer: {result.customer_name}")
print(f"Sentiment: {result.sentiment}")
print("✅ Check the Weave UI to see the trace!")

# %% [markdown]
# ### 🐛 Part 1.1: Nested Debugging
#
# Weave tracks nested function calls, making debugging easy. Let's build a more complex pipeline.


# %%
@weave.op
def preprocess_email(email: str) -> str:
    """Clean and standardize email text."""
    # Remove extra whitespace and normalize formatting
    cleaned = " ".join(email.split())
    return cleaned


@weave.op
def classify_urgency(email: str, sentiment: str) -> str:
    """Determine urgency level based on content and sentiment."""
    urgent_keywords = [
        "urgent",
        "asap",
        "immediately",
        "frustrated",
        "broken",
        "stopped working",
    ]

    # Check for urgent keywords in the email
    email_lower = email.lower()
    has_urgent_keywords = any(keyword in email_lower for keyword in urgent_keywords)

    # Combine sentiment and keywords to determine urgency
    if sentiment == "negative" and has_urgent_keywords:
        return "high"
    elif sentiment == "negative" or has_urgent_keywords:
        return "medium"
    else:
        return "low"


@weave.op
def process_support_ticket(email: str) -> dict[str, Any]:
    """Complete support ticket processing pipeline."""
    # Step 1: Clean the email
    cleaned_email = preprocess_email(email)

    # Step 2: Analyze the email content
    analysis = analyze_customer_email(cleaned_email)

    # Step 3: Determine urgency level
    urgency = classify_urgency(cleaned_email, analysis.sentiment)

    # Return complete ticket information
    return {
        "customer_name": analysis.customer_name,
        "product": analysis.product,
        "issue": analysis.issue,
        "sentiment": analysis.sentiment,
        "urgency": urgency,
        "needs_immediate_attention": urgency == "high",
    }


# 🔗 Run the pipeline - see the nested traces in Weave!
ticket = process_support_ticket(test_email)
print(f"Urgency: {ticket['urgency']}")
print(f"Needs immediate attention: {ticket['needs_immediate_attention']}")

# %% [markdown]
# ### ⚠️ Part 1.2: Exception Tracking
#
# Weave automatically tracks exceptions in nested function calls, making debugging easy.


# %%
@weave.op
def risky_operation(data: str) -> str:
    """A child operation that might fail."""
    if "error" in data.lower():
        raise ValueError(f"Found 'error' in data: {data}")
    if len(data) < 5:
        raise ValueError("Data too short!")
    return f"Processed: {data}"


@weave.op
def safe_processor(inputs: list[str]) -> dict[str, Any]:
    """A parent operation that handles child failures gracefully."""
    results = {"successful": [], "failed": []}

    for i, data in enumerate(inputs):
        try:
            # Call the risky child operation
            processed = risky_operation(data)
            results["successful"].append(
                {"index": i, "data": data, "result": processed}
            )
        except Exception as e:
            # Catch and log the exception - Weave tracks this!
            results["failed"].append({"index": i, "data": data, "error": str(e)})

    return results


# Test with mixed data - some will succeed, some will fail
test_data = [
    "Valid data here",  # ✅ Will succeed
    "err",  # ❌ Too short
    "This contains error word",  # ❌ Contains 'error'
    "Another good input",  # ✅ Will succeed
    "bad",  # ❌ Too short
]

result = safe_processor(test_data)
print(f"✅ Successful: {len(result['successful'])}")
print(f"❌ Failed: {len(result['failed'])}")

# %% [markdown]
# ### 🖼️ Part 1.3: Media Support
#
# Weave automatically traces and logs various media types including images, videos, and audio.

# %%
import base64
import wave

import requests
from PIL import Image


# 📸 Image Support - Weave automatically logs PIL.Image objects
@weave.op
def generate_sample_image() -> Image.Image:
    """Generate a sample image using OpenAI DALL-E API."""
    client = OpenAI()

    response = client.images.generate(
        model="dall-e-3",
        prompt="A cute robot learning about data science, digital art style",
        size="1024x1024",
        quality="standard",
        n=1,
    )

    # Download and return as PIL Image - Weave will automatically log this!
    image_url = response.data[0].url
    image_response = requests.get(image_url, stream=True)
    image = Image.open(image_response.raw)

    return image


# 🎵 Audio Support - Weave automatically logs wave.Wave_read objects
@weave.op
def generate_sample_audio(text: str) -> wave.Wave_read:
    """Generate audio using OpenAI's text-to-speech API."""
    client = OpenAI()

    with client.audio.speech.with_streaming_response.create(
        model="tts-1",
        voice="alloy",
        input=text,
        response_format="wav",
    ) as response:
        response.stream_to_file("sample_audio.wav")

    # Return wave file - Weave will automatically log this with audio player!
    return wave.open("sample_audio.wav", "rb")


# 🔍 Multimodal Analysis - Combining image and text
@weave.op
def analyze_image_with_gpt4_vision(image: Image.Image, question: str) -> str:
    """Analyze an image using GPT-4 Vision."""
    client = OpenAI()

    # Convert PIL image to base64 for API
    import io

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    image_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

    response = client.chat.completions.create(
        model="gpt-4o-mini",  # Supports vision
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": question},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_base64}"},
                    },
                ],
            }
        ],
        max_tokens=300,
    )

    return response.choices[0].message.content


# Generate and analyze media
sample_image = generate_sample_image()
print(f"📸 Generated image: {sample_image.size}")

analysis = analyze_image_with_gpt4_vision(
    sample_image, "What do you see in this image? Describe it in one sentence."
)
print(f"🤖 Analysis: {analysis}")

sample_audio = generate_sample_audio(
    "Welcome to the Weave workshop! This audio will be automatically logged."
)
print("🎵 Generated audio file")

# %% [markdown]
# ### 🔒 Part 1.4: Custom Serialization
#
# Control what gets logged with custom serialization functions.
# Perfect for PII redaction, large object handling, and sensitive data filtering.

# %%
import re
from typing import Any, Dict


# 🔐 Example 1: PII Redaction
def redact_pii_inputs(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Redact PII from inputs before logging."""
    processed = inputs.copy()

    if "email_content" in processed:
        text = processed["email_content"]
        # Redact email addresses
        text = re.sub(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "<EMAIL>", text
        )
        # Redact phone numbers
        text = re.sub(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b", "<PHONE>", text)
        # Redact SSN
        text = re.sub(r"\b\d{3}-\d{2}-\d{4}\b", "<SSN>", text)
        processed["email_content"] = text

    return processed


def redact_pii_output(output: Any) -> Any:
    """Redact PII from outputs before logging."""
    if hasattr(output, "customer_name"):
        # Create a copy and redact the name
        output_dict = output.dict() if hasattr(output, "dict") else output
        if isinstance(output_dict, dict) and "customer_name" in output_dict:
            output_dict["customer_name"] = "<CUSTOMER_NAME>"
        return output_dict
    return output


@weave.op(postprocess_inputs=redact_pii_inputs, postprocess_output=redact_pii_output)
def analyze_sensitive_email(email_content: str) -> CustomerEmail:
    """Analyze email while protecting PII in logs."""
    return analyze_customer_email(email_content)


# 📦 Example 2: Large Object Handling
def summarize_large_inputs(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Summarize large objects to avoid logging huge data."""
    processed = inputs.copy()

    for key, value in processed.items():
        if isinstance(value, (list, tuple)) and len(value) > 10:
            # Only log first/last few items for large lists
            processed[key] = {
                "type": f"{type(value).__name__}",
                "length": len(value),
                "sample_start": value[:3],
                "sample_end": value[-3:],
                "note": "Large object truncated for logging",
            }
        elif isinstance(value, str) and len(value) > 1000:
            # Truncate very long strings
            processed[key] = {
                "type": "string",
                "length": len(value),
                "preview": value[:200] + "...",
                "note": "Long string truncated for logging",
            }

    return processed


@weave.op(postprocess_inputs=summarize_large_inputs)
def process_large_dataset(data_list: list, metadata: str) -> dict:
    """Process large datasets while keeping logs manageable."""
    return {
        "processed_count": len(data_list),
        "metadata_length": len(metadata),
        "summary": f"Processed {len(data_list)} items",
    }


# 🔑 Example 3: Sensitive Configuration Filtering
def filter_sensitive_config(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Remove sensitive configuration from logs."""
    processed = inputs.copy()
    # List of sensitive keys to redact
    sensitive_keys = ["api_key", "password", "secret", "token", "private_key"]

    for key in list(processed.keys()):
        if any(sensitive in key.lower() for sensitive in sensitive_keys):
            processed[key] = "<REDACTED>"
        elif isinstance(processed[key], dict):
            # Recursively filter nested dictionaries
            processed[key] = filter_sensitive_config({"nested": processed[key]})[
                "nested"
            ]

    return processed


@weave.op(postprocess_inputs=filter_sensitive_config)
def configure_api_client(api_key: str, endpoint: str, secret_token: str) -> dict:
    """Configure API client while hiding sensitive data in logs."""
    return {"endpoint": endpoint, "configured": True, "auth_method": "token"}


# 🧪 Test serialization controls
sensitive_email = """
Hi Support,
My name is John Smith and my email is john.smith@company.com.
My phone number is 555-123-4567 and SSN is 123-45-6789.
Please help with my ProWidget issue!
"""

result1 = analyze_sensitive_email(sensitive_email)
print("✅ PII redacted in logs (check Weave UI)")

large_data = list(range(1000))  # Large list
long_text = "This is a very long string. " * 100  # Long string
result2 = process_large_dataset(large_data, long_text)
print("✅ Large objects summarized")

result3 = configure_api_client(
    api_key="secret_key_12345",
    endpoint="https://api.example.com",
    secret_token="super_secret_token",
)
print("✅ Sensitive config filtered")

# %% [markdown]
# ### 🔗 Part 1.5: OpenTelemetry Integration
#
# Weave supports OpenTelemetry traces, allowing integration with existing observability infrastructure.

# %%
import base64

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk import trace as trace_sdk
from opentelemetry.sdk.trace.export import SimpleSpanProcessor


# 🔧 Configure OTEL to send traces to Weave
def setup_otel_for_weave(project_name: str = "weave-workshop"):
    """Set up OpenTelemetry to send traces to Weave."""
    # Note: Replace ENTITY with your actual W&B entity
    ENTITY = "your-entity"  # Replace with your W&B entity
    PROJECT_ID = f"{ENTITY}/{project_name}"
    OTEL_ENDPOINT = "https://trace.wandb.ai/otel/v1/traces"

    # Authentication (get from environment in real usage)
    WANDB_API_KEY = os.environ.get("WANDB_API_KEY", "your-api-key")
    auth = base64.b64encode(f"api:{WANDB_API_KEY}".encode()).decode()

    headers = {
        "Authorization": f"Basic {auth}",
        "project_id": PROJECT_ID,
    }

    # Create tracer provider
    tracer_provider = trace_sdk.TracerProvider()

    # Configure OTLP exporter for Weave
    exporter = OTLPSpanExporter(endpoint=OTEL_ENDPOINT, headers=headers)
    tracer_provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(tracer_provider)

    return trace.get_tracer(__name__)


def otel_function(tracer, data: str) -> str:
    """A function traced by OpenTelemetry."""
    with tracer.start_as_current_span("otel_processing") as span:
        span.set_attribute("input.data", data)
        span.set_attribute("processing.type", "otel")
        result = f"OTEL processed: {data}"
        span.set_attribute("output.result", result)
        return result


# Example OTEL integration (commented out to avoid auth issues in demo)
# tracer = setup_otel_for_weave()
# otel_function(tracer, "Hello from OTEL")

print("🔗 OpenTelemetry integration example completed")

# %% [markdown]
# ## Summary
#
# You've learned how to use Weave's tracing capabilities:
#
# - ✅ **Function Tracing**: Use `@weave.op` to automatically track function calls
# - ✅ **Nested Debugging**: Debug complex pipelines with automatic call traces
# - ✅ **Exception Tracking**: Monitor failures with full context preservation
# - ✅ **Media Support**: Trace multimodal applications with automatic media logging
# - ✅ **Custom Serialization**: Control data logging with preprocessing functions
# - ✅ **OpenTelemetry**: Integrate with existing observability infrastructure
#
# **Next Steps:**
# - Continue to Part 2: Evaluations to learn systematic testing and model comparison
# - Check the Weave UI to explore your traces and debug your applications
# - Try tracing your own LLM applications with `@weave.op`
#
# **Key Takeaways:**
# - Tracing is automatic with `@weave.op` - no manual logging required
# - Weave integrates with 20+ popular AI libraries out of the box
# - Rich debugging context helps you understand exactly what happened
# - Production-ready features like PII redaction and custom serialization
