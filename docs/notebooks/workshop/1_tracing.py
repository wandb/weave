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
# %pip install wandb weave openai pydantic nest_asyncio -qqq

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

print("\n💡 Check the Weave UI to see:")
print("  - Parent operation (safe_processor) shows all child calls")
print("  - Failed child operations (risky_operation) are highlighted in red")
print("  - Full exception details and stack traces")
print("  - How exceptions flow from child to parent operations")


# %% [markdown]
# ### 🎬 Part 1.3: Media Support & Multimodal Tracing
#
# Weave can automatically trace and log various media types including images, videos, audio, and PDFs.
# This is especially useful for multimodal AI applications.
# TODO: (NEW CELL still focused on basic tracing) I would like to add another cell on tracing here that showcases Media Classes
#   * Media Classes
#       * Image support
#           * OpenAI's base64 pattern
#           * Standard PIL images are supported
#       * Video Support (Using the new annotations pattern)
#       * Audio support
#       * PDFs


# %% [markdown]
# ### 🔒 Part 1.4: Custom Serialization & Privacy Controls
#
# Control what gets logged and how with Weave's serialization features.
# Perfect for handling large objects, PII redaction, and privacy controls.
# TODO: (NEW CELL still focused on basic tracing) I would like to add another cell on tracing here that showcases pre- and post- processing to control what gets serialized


# %% [markdown]
# ### 🌊 Part 1.5: Streaming & Generators
#
# Weave can trace iterators, generators, and streaming data patterns.
# Essential for real-time applications and memory-efficient processing.
# TODO: (NEW CELL still focused on basic tracing) We should show that different forms of generators / iterators can be traced as well.


# %% [markdown]
# ### 🔗 Part 1.6: OpenTelemetry Integration
#
# Learn how Weave integrates with OpenTelemetry for enterprise observability.
# Perfect for connecting Weave traces with your existing monitoring infrastructure.
# TODO: (New cell) Let's showcase OTEL support and how that works at the end here
