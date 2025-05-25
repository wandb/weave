# %% [markdown]
# # 🐝 Weave Workshop: Build, Track, and Evaluate LLM Applications
#
# <img src="http://wandb.me/logo-im-png" width="400" alt="Weights & Biases" />
#
# Welcome to the Weave workshop! In this hands-on session, you'll learn how to use Weave to develop, debug, and evaluate AI-powered applications.
#
# **What you'll learn:**
# - 🔍 **Trace & Debug**: Track every LLM call, see inputs/outputs, and debug issues
# - 📊 **Evaluate**: Build rigorous evaluations with multiple scoring functions
# - 🏃 **Compare**: Run A/B tests and compare different approaches
# - 📈 **Monitor**: Track costs, latency, and performance metrics
# - 🎯 **Iterate**: Use data-driven insights to improve your application

# %% [markdown]
# ## 🔑 Prerequisites
#
# Before we begin, let's set up your environment.

# %%
# Install dependencies
# %pip install wandb weave openai pydantic nest_asyncio opentelemetry-exporter-otlp 'weave[video_support]' -qqq

import os
from getpass import getpass
from typing import Any

from openai import OpenAI
from pydantic import BaseModel, Field

import weave

# 🔑 Setup your API keys
print("📝 Setting up API keys...")

# Weights & Biases will automatically prompt if needed
# It checks: 1) WANDB_API_KEY env var, 2) ~/.netrc, 3) prompts user
print("✅ W&B authentication will be handled automatically by Weave")
print("   (Optional: You can set WANDB_API_KEY env variable if you prefer)")

# OpenAI requires manual setup
print("\n🤖 OpenAI Setup:")
if not os.environ.get("OPENAI_API_KEY"):
    print(
        "You can generate your OpenAI API key here: https://platform.openai.com/api-keys"
    )
    os.environ["OPENAI_API_KEY"] = getpass("Enter your OpenAI API key: ")
else:
    print("✅ OpenAI API key found in environment")

print("\n---")

# 🏠 Initialize your W&B project
print("🐝 Initializing Weave...")
weave_client = weave.init("weave-workshop")  # 🐝 Your W&B project name

# %% [markdown]
# ## 🔍 Part 1: Tracing & Debugging with Weave
#
# Let's start by building a simple LLM application and see how Weave automatically tracks everything.
#
# Note: We're using `gpt-4o-mini` which supports structured outputs while being cost-effective.


# %%
# Define our data structure
class CustomerEmail(BaseModel):
    customer_name: str
    product: str
    issue: str
    sentiment: str = Field(description="positive, neutral, or negative")


# 🐝 Track functions with @weave.op
@weave.op
def analyze_customer_email(email: str) -> CustomerEmail:
    """Analyze a customer support email and extract key information."""
    client = OpenAI()

    # 🎯 Note: OpenAI calls are automatically traced by Weave!
    # Weave automatically integrates with dozens of popular libraries including:
    # OpenAI, Anthropic, LangChain, LlamaIndex, HuggingFace, and more
    # See full list: https://weave-docs.wandb.ai/guides/integrations/
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


# Let's test it!
test_email = """
Hi Support,

I'm really frustrated! My new ProWidget 3000 stopped working after just 2 days.
The screen went completely black and won't turn on no matter what I try.

Please help!
Sarah Johnson
"""

# 🎯 Run the function - Weave will automatically track this call
result = analyze_customer_email(test_email)
print("✅ Analysis complete!")
print(f"Customer: {result.customer_name}")
print(f"Sentiment: {result.sentiment}")
print("\n🔍 Check the Weave UI to see the trace!")


# %% [markdown]
# ### 🐛 Part 1.1: Debugging with Call Traces
#
# Weave tracks nested function calls, making debugging easy. Let's build a more complex example.


# %%
@weave.op
def preprocess_email(email: str) -> str:
    """Clean and standardize email text."""
    # Remove extra whitespace
    cleaned = " ".join(email.split())
    # Add some metadata for debugging
    print(f"📧 Original length: {len(email)}, Cleaned length: {len(cleaned)}")
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

    # Check for urgent keywords
    email_lower = email.lower()
    has_urgent_keywords = any(keyword in email_lower for keyword in urgent_keywords)

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

    # Step 2: Analyze the email
    analysis = analyze_customer_email(cleaned_email)

    # Step 3: Determine urgency
    urgency = classify_urgency(cleaned_email, analysis.sentiment)

    # Return complete ticket info
    return {
        "customer_name": analysis.customer_name,
        "product": analysis.product,
        "issue": analysis.issue,
        "sentiment": analysis.sentiment,
        "urgency": urgency,
        "needs_immediate_attention": urgency == "high",
    }


# 🎯 Run the pipeline - see the nested traces in Weave!
ticket = process_support_ticket(test_email)
print("\n🎫 Ticket processed!")
print(f"Urgency: {ticket['urgency']}")
print(f"Needs immediate attention: {ticket['needs_immediate_attention']}")


# %% [markdown]
# ### 🐞 Part 1.2: Exception Tracking
#
# Weave automatically tracks exceptions in nested function calls, making debugging easy.
# Let's see how exceptions flow through parent and child operations.


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
            # Catch and log the exception
            results["failed"].append({"index": i, "data": data, "error": str(e)})
            print(f"❌ Failed to process item {i}: {e}")

    return results


# Test with mixed data - some will succeed, some will fail
test_data = [
    "Valid data here",  # ✅ Will succeed
    "err",  # ❌ Too short
    "This contains error word",  # ❌ Contains 'error'
    "Another good input",  # ✅ Will succeed
    "bad",  # ❌ Too short
]

print("🐞 Testing exception tracking in nested operations...")
result = safe_processor(test_data)

print("\n📊 Results:")
print(f"✅ Successful: {len(result['successful'])}")
print(f"❌ Failed: {len(result['failed'])}")




# %% [markdown]
# ### 🎬 Part 1.3: Media Support & Multimodal Tracing
#
# Weave can automatically trace and log various media types including images, videos, audio, and PDFs.
# This is especially useful for multimodal AI applications.

# %%
# Let's demonstrate media support with different types
import requests
from PIL import Image
import wave
import base64

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

# 🖼️ Multimodal Analysis - Combining image and text
@weave.op
def analyze_image_with_gpt4_vision(image: Image.Image, question: str) -> str:
    """Analyze an image using GPT-4 Vision."""
    client = OpenAI()
    
    # Convert PIL image to base64 for API
    import io
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",  # Supports vision
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": question},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_base64}"
                        }
                    }
                ]
            }
        ],
        max_tokens=300
    )
    
    return response.choices[0].message.content


# Test image generation and analysis
print("\n📸 Generating image...")
sample_image = generate_sample_image()
print(f"✅ Generated image: {sample_image.size}")

print("\n🔍 Analyzing image with GPT-4 Vision...")
analysis = analyze_image_with_gpt4_vision(
    sample_image, 
    "What do you see in this image? Describe it in one sentence."
)
print(f"🤖 Analysis: {analysis}")

# Test audio generation
print("\n🎵 Generating audio...")
sample_audio = generate_sample_audio("Welcome to the Weave workshop! This audio will be automatically logged.")
print("✅ Generated audio file")

# Test video creation (if moviepy is available)
print("\n🎬 Creating video...")
sample_video = create_sample_video()
if isinstance(sample_video, str):
    print(f"⚠️ {sample_video}")
else:
    print("✅ Generated video clip")

print("\n💡 Check the Weave UI to see:")
print("  - 📸 Images displayed with thumbnails and full-size view")
print("  - 🎵 Audio files with built-in audio player and waveform")
print("  - 🎬 Video clips with video player (if moviepy available)")
print("  - 🔗 All media automatically linked to their function calls")
print("  - 📊 Media metadata (dimensions, duration, file size, etc.)")

print("\n🎯 Key Benefits:")
print("  - No manual upload needed - Weave handles everything automatically")
print("  - Media is preserved with full context of the function call")
print("  - Easy to debug multimodal AI applications")
print("  - Share results with team members through Weave UI")


# %% [markdown]
# ### 🔒 Part 1.4: Custom Serialization
#
# Control what gets logged and how with Weave's serialization features.
# Use `postprocess_inputs` and `postprocess_output` to customize what data gets stored.
# Perfect for PII redaction, large object handling, sensitive data filtering, and more.

# %%
import re
from typing import Any, Dict

# 🔒 Example 1: PII Redaction
def redact_pii_inputs(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Redact PII from inputs before logging."""
    processed = inputs.copy()
    
    if "email_content" in processed:
        text = processed["email_content"]
        # Redact email addresses
        text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '<EMAIL>', text)
        # Redact phone numbers
        text = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '<PHONE>', text)
        # Redact SSN
        text = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '<SSN>', text)
        processed["email_content"] = text
    
    return processed

def redact_pii_output(output: Any) -> Any:
    """Redact PII from outputs before logging."""
    if hasattr(output, 'customer_name'):
        # Create a copy and redact the name
        output_dict = output.dict() if hasattr(output, 'dict') else output
        if isinstance(output_dict, dict) and 'customer_name' in output_dict:
            output_dict['customer_name'] = '<CUSTOMER_NAME>'
        return output_dict
    return output

@weave.op(
    postprocess_inputs=redact_pii_inputs,
    postprocess_output=redact_pii_output
)
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
                "note": "Large object truncated for logging"
            }
        elif isinstance(value, str) and len(value) > 1000:
            # Truncate very long strings
            processed[key] = {
                "type": "string",
                "length": len(value),
                "preview": value[:200] + "...",
                "note": "Long string truncated for logging"
            }
    
    return processed

@weave.op(postprocess_inputs=summarize_large_inputs)
def process_large_dataset(data_list: list, metadata: str) -> dict:
    """Process large datasets while keeping logs manageable."""
    return {
        "processed_count": len(data_list),
        "metadata_length": len(metadata),
        "summary": f"Processed {len(data_list)} items"
    }

# 🎯 Example 3: Sensitive Configuration Filtering
def filter_sensitive_config(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Remove sensitive configuration from logs."""
    processed = inputs.copy()
    
    # List of sensitive keys to redact
    sensitive_keys = ['api_key', 'password', 'secret', 'token', 'private_key']
    
    for key in list(processed.keys()):
        if any(sensitive in key.lower() for sensitive in sensitive_keys):
            processed[key] = '<REDACTED>'
        elif isinstance(processed[key], dict):
            # Recursively filter nested dictionaries
            processed[key] = filter_sensitive_config({'nested': processed[key]})['nested']
    
    return processed

@weave.op(postprocess_inputs=filter_sensitive_config)
def configure_api_client(api_key: str, endpoint: str, secret_token: str) -> dict:
    """Configure API client while hiding sensitive data in logs."""
    return {
        "endpoint": endpoint,
        "configured": True,
        "auth_method": "token"
    }

# 🔄 Example 4: Data Transformation for Logging
def transform_for_logging(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Transform data to a more readable format for logs."""
    processed = inputs.copy()
    
    # Convert complex objects to readable summaries
    for key, value in processed.items():
        if hasattr(value, '__dict__'):
            # Convert objects to their string representation
            processed[key] = {
                "type": type(value).__name__,
                "summary": str(value)[:100],
                "attributes": list(vars(value).keys()) if hasattr(value, '__dict__') else []
            }
    
    return processed

def enhance_output_logging(output: Any) -> Any:
    """Add metadata to output for better logging."""
    if isinstance(output, dict):
        enhanced = output.copy()
        enhanced["_logged_at"] = "workshop_demo"
        enhanced["_output_type"] = "processed_result"
        return enhanced
    return output

@weave.op(
    postprocess_inputs=transform_for_logging,
    postprocess_output=enhance_output_logging
)
def complex_data_processor(user_object: Any, config: dict) -> dict:
    """Process complex data with enhanced logging."""
    return {
        "status": "completed",
        "config_keys": list(config.keys()) if isinstance(config, dict) else [],
        "user_data_processed": True
    }

# 🧪 Let's test all the serialization controls!
print("🔒 Testing custom serialization and privacy controls...")

# Test 1: PII Redaction
print("\n📧 Testing PII redaction...")
sensitive_email = """
Hi Support,
My name is John Smith and my email is john.smith@company.com.
My phone number is 555-123-4567 and SSN is 123-45-6789.
Please help with my ProWidget issue!
"""

result1 = analyze_sensitive_email(sensitive_email)
print("✅ PII redacted in logs (check Weave UI)")

# Test 2: Large Object Handling  
print("\n📦 Testing large object handling...")
large_data = list(range(1000))  # Large list
long_text = "This is a very long string. " * 100  # Long string

result2 = process_large_dataset(large_data, long_text)
print(f"✅ Large objects summarized: {result2}")

# Test 3: Sensitive Configuration
print("\n🔐 Testing sensitive config filtering...")
result3 = configure_api_client(
    api_key="secret_key_12345",
    endpoint="https://api.example.com",
    secret_token="super_secret_token"
)
print(f"✅ Sensitive config filtered: {result3}")

# Test 4: Data Transformation
print("\n🔄 Testing data transformation...")
class SampleObject:
    def __init__(self):
        self.name = "test"
        self.value = 42

sample_obj = SampleObject()
sample_config = {"debug": True, "timeout": 30}

result4 = complex_data_processor(sample_obj, sample_config)
print(f"✅ Data transformed for logging: {result4}")


# %% [markdown]
# ### 🔗 Part 1.5: OpenTelemetry Integration
#
# Weave supports OpenTelemetry (OTEL) traces, allowing you to integrate with existing observability infrastructure.
# Send OTLP-formatted traces directly to Weave alongside your native Weave traces.

# %%
import base64
from opentelemetry import trace
from opentelemetry.sdk import trace as trace_sdk
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

ENTITY = ...

# 🔗 Configure OTEL to send traces to Weave
def setup_otel_for_weave(project_name: str = "weave-workshop"):
    """Set up OpenTelemetry to send traces to Weave."""
    
    # Weave OTEL endpoint
    PROJECT_ID = f"{ENTITY}/{project_name}"  # Replace with your entity
    OTEL_ENDPOINT = "https://trace.wandb.ai/otel/v1/traces"
    
    # Authentication (in real usage, get from environment)
    WANDB_API_KEY = os.environ.get("WANDB_API_KEY", "your-api-key")
    auth = base64.b64encode(f"api:{WANDB_API_KEY}".encode()).decode()
    
    headers = {
        "Authorization": f"Basic {auth}",
        "project_id": PROJECT_ID,
    }
    
    # Create tracer provider
    tracer_provider = trace_sdk.TracerProvider()
    
    # Configure OTLP exporter for Weave
    exporter = OTLPSpanExporter(
        endpoint=OTEL_ENDPOINT,
        headers=headers,
    )
    
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

tracer = setup_otel_for_weave()
otel_function(tracer, "Hello from OTEL")
