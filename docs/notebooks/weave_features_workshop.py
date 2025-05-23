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
# %pip install wandb weave openai pydantic -qqq

import asyncio
import os
from getpass import getpass
from typing import Any, Dict, List, Optional

from openai import OpenAI
from pydantic import BaseModel, Field

import weave
from weave import Dataset, Evaluation, Model

# 🔑 Setup your API keys
print("---")
print(
    "You can find your Weights and Biases API key here: https://wandb.ai/settings#api"
)
if not os.environ.get("WANDB_API_KEY"):
    os.environ["WANDB_API_KEY"] = getpass("Enter your Weights and Biases API key: ")
print("---")
print("You can generate your OpenAI API key here: https://platform.openai.com/api-keys")
if not os.environ.get("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = getpass("Enter your OpenAI API key: ")
print("---")

# 🏠 Initialize your W&B project
weave_client = weave.init("weave-workshop")  # 🐝 Your W&B project name

# %% [markdown]
# ## 🔍 Part 1: Tracing & Debugging with Weave
#
# Let's start by building a simple LLM application and see how Weave automatically tracks everything.


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

    response = client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "You are a customer support analyst. Extract key information from emails.",
            },
            {
                "role": "user",
                "content": f"Analyze this customer email and extract the customer name, product, issue, and sentiment:\n\n{email}",
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
# ## 🐛 Part 2: Debugging with Call Traces
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
def process_support_ticket(email: str) -> Dict[str, Any]:
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
# ## 📊 Part 3: Building Evaluations
#
# Now let's evaluate our email analyzer using Weave's evaluation framework.

# %%
# Create evaluation dataset
eval_examples = [
    {
        "email": "Hello, I'm John Smith. My DataProcessor Pro crashed and I lost all my work. This is unacceptable!",
        "expected_name": "John Smith",
        "expected_product": "DataProcessor Pro",
        "expected_sentiment": "negative",
    },
    {
        "email": "Hi there! Jane Doe here. Just wanted to say the CloudSync Plus is working perfectly. Great product!",
        "expected_name": "Jane Doe",
        "expected_product": "CloudSync Plus",
        "expected_sentiment": "positive",
    },
    {
        "email": "My SmartHub isn't connecting to WiFi. Can you help? Thanks, Bob Wilson",
        "expected_name": "Bob Wilson",
        "expected_product": "SmartHub",
        "expected_sentiment": "neutral",
    },
]

# Create a Weave Dataset
support_dataset = Dataset(name="support_emails", rows=eval_examples)


# 🎯 Define scoring functions
@weave.op
def name_accuracy(expected_name: str, output: CustomerEmail) -> Dict[str, Any]:
    """Check if the extracted name matches."""
    is_correct = expected_name.lower() == output.customer_name.lower()
    return {"correct": is_correct, "score": 1.0 if is_correct else 0.0}


@weave.op
def sentiment_accuracy(
    expected_sentiment: str, output: CustomerEmail
) -> Dict[str, Any]:
    """Check if the sentiment analysis is correct."""
    is_correct = expected_sentiment.lower() == output.sentiment.lower()
    return {"correct": is_correct, "score": 1.0 if is_correct else 0.0}


@weave.op
def extraction_quality(email: str, output: CustomerEmail) -> Dict[str, Any]:
    """Evaluate overall extraction quality."""
    score = 0.0
    feedback = []

    # Check if all fields are extracted
    if output.customer_name and output.customer_name != "Unknown":
        score += 0.33
    else:
        feedback.append("Missing customer name")

    if output.product and output.product != "Unknown":
        score += 0.33
    else:
        feedback.append("Missing product")

    if output.issue and len(output.issue) > 10:
        score += 0.34
    else:
        feedback.append("Issue description too short")

    return {
        "score": score,
        "feedback": "; ".join(feedback)
        if feedback
        else "All fields extracted successfully",
    }


# 🚀 Run the evaluation
evaluation = Evaluation(
    name="email_analyzer_eval",
    dataset=support_dataset,
    scorers=[name_accuracy, sentiment_accuracy, extraction_quality],
)

print("🏃 Running evaluation...")
eval_results = asyncio.run(evaluation.evaluate(analyze_customer_email))
print("✅ Evaluation complete! Check the Weave UI for detailed results.")

# %% [markdown]
# ## 🏆 Part 4: Model Comparison
#
# Let's compare different approaches using Weave's Model class.


# %%
# Define different model variants
class EmailAnalyzerModel(Model):
    """Base model for email analysis with configurable parameters."""

    model_name: str = "gpt-4o-mini"
    temperature: float = 0.1
    system_prompt: str = "You are a customer support analyst."

    @weave.op
    def predict(self, email: str) -> CustomerEmail:
        """Analyze email with configurable parameters."""
        client = OpenAI()

        response = client.beta.chat.completions.parse(
            model=self.model_name,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": f"Analyze this email:\n{email}"},
            ],
            response_format=CustomerEmail,
            temperature=self.temperature,
        )

        return response.choices[0].message.parsed


# Create model variants
basic_model = EmailAnalyzerModel(
    name="basic_analyzer",
    system_prompt="Extract customer name, product, issue, and sentiment from the email.",
)

detailed_model = EmailAnalyzerModel(
    name="detailed_analyzer",
    system_prompt="""You are an expert customer support analyst. 
    Carefully extract:
    - Customer name (look for signatures or greetings)
    - Product name (exact product mentioned)
    - Issue description (concise but complete)
    - Sentiment (positive/neutral/negative based on tone)
    Be precise and thorough.""",
    temperature=0.0,
)

empathetic_model = EmailAnalyzerModel(
    name="empathetic_analyzer",
    system_prompt="""You are an empathetic customer support specialist.
    Read between the lines to understand the customer's emotional state.
    Extract customer information while being sensitive to their frustration level.""",
    temperature=0.2,
)

# %% [markdown]
# ## 🔄 Part 5: A/B Testing Models


# %%
@weave.op
async def compare_models(models: List[Model], dataset: Dataset) -> Dict[str, Any]:
    """Run A/B comparison of multiple models."""
    results = {}

    for model in models:
        print(f"\n📊 Evaluating {model.name}...")
        evaluation = Evaluation(
            name=f"comparison_{model.name}",
            dataset=dataset,
            scorers=[name_accuracy, sentiment_accuracy, extraction_quality],
        )

        # Run evaluation
        eval_result = await evaluation.evaluate(model)
        results[model.name] = eval_result

        print(f"✅ {model.name} evaluation complete!")

    return results


# Run the comparison
print("🏁 Starting model comparison...")
comparison_results = asyncio.run(
    compare_models([basic_model, detailed_model, empathetic_model], support_dataset)
)
print("\n🎉 Comparison complete! View the results in the Weave UI.")

# %% [markdown]
# ## 📈 Part 6: Cost & Performance Tracking
#
# Weave automatically tracks metrics like latency and token usage. Let's explore these features.


# %%
@weave.op
def analyze_with_fallback(
    email: str,
    primary_model: str = "gpt-4o-mini",
    fallback_model: str = "gpt-3.5-turbo",
) -> CustomerEmail:
    """Analyze email with automatic fallback on error."""
    client = OpenAI()

    try:
        # Try primary model first
        response = client.beta.chat.completions.parse(
            model=primary_model,
            messages=[
                {"role": "system", "content": "Extract customer info from email."},
                {"role": "user", "content": email},
            ],
            response_format=CustomerEmail,
        )
        print(f"✅ Used primary model: {primary_model}")
        return response.choices[0].message.parsed

    except Exception as e:
        print(f"⚠️ Primary model failed: {e}")
        print(f"🔄 Falling back to {fallback_model}")

        # Fallback to secondary model
        response = client.beta.chat.completions.parse(
            model=fallback_model,
            messages=[
                {"role": "system", "content": "Extract customer info from email."},
                {"role": "user", "content": email},
            ],
            response_format=CustomerEmail,
        )
        return response.choices[0].message.parsed


# Test the fallback mechanism
test_emails = [
    "Hi, I'm Alice Brown. My UltraPhone is overheating constantly!",
    "Bob Green here. The MegaTablet screen is cracked after dropping it.",
    "Carol White needs help with CloudBackup not syncing properly.",
]

print("🔄 Testing fallback mechanism...")
for email in test_emails:
    result = analyze_with_fallback(email)
    print(f"  Processed: {result.customer_name} - {result.sentiment}")

print("\n💰 Check the Weave UI to see:")
print("  - Token usage for each call")
print("  - Latency comparisons")
print("  - Cost tracking (when available)")

# %% [markdown]
# ## 🎯 Part 7: Production Monitoring
#
# Use Weave to monitor your application in production.

# %%
import random
from datetime import datetime


@weave.op
def production_email_handler(email: str, request_id: str = None) -> Dict[str, Any]:
    """Production-ready email handler with monitoring."""
    start_time = datetime.now()

    # Generate request ID if not provided
    if not request_id:
        request_id = f"req_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{random.randint(1000, 9999)}"

    try:
        # Process the email
        analysis = analyze_customer_email(email)
        urgency = classify_urgency(email, analysis.sentiment)

        # Log success metrics
        processing_time = (datetime.now() - start_time).total_seconds()

        result = {
            "request_id": request_id,
            "status": "success",
            "processing_time_seconds": processing_time,
            "analysis": analysis.model_dump(),
            "urgency": urgency,
            "timestamp": datetime.now().isoformat(),
        }

        # Log for monitoring
        if urgency == "high":
            print(f"🚨 HIGH URGENCY TICKET: {request_id}")

        return result

    except Exception as e:
        # Log error metrics
        return {
            "request_id": request_id,
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


# Simulate production traffic
print("🏭 Simulating production traffic...")
production_emails = [
    "URGENT: I'm CEO Jane Smith. Our Enterprise Suite is down and we're losing money!",
    "Hi, just checking if CloudSync has a mobile app? Thanks, Tom",
    "My DataVault backup failed. Need help ASAP! - Mary Johnson",
]

for email in production_emails:
    result = production_email_handler(email)
    print(f"  [{result['request_id']}] Status: {result['status']}")

# %% [markdown]
# ## 🔍 Part 8: Debugging Failed Calls
#
# Weave makes it easy to debug when things go wrong.


# %%
@weave.op
def problematic_analyzer(email: str) -> Optional[CustomerEmail]:
    """An analyzer that might fail - perfect for debugging!"""
    # Simulate different failure modes
    if "error" in email.lower():
        raise ValueError("Email contains error keyword!")

    if len(email) < 20:
        print("⚠️ Email too short, returning None")
        return None

    if "urgent" in email.lower():
        # Simulate a timeout or rate limit
        import time

        print("⏳ Processing urgent email (simulating delay)...")
        time.sleep(2)

    # Normal processing
    return analyze_customer_email(email)


# Test with problematic inputs
test_cases = [
    ("normal@example.com: Help with login", "Normal case"),
    ("Short email", "Too short"),
    ("error@example.com: System error occurred", "Contains error keyword"),
    ("URGENT: Database is down!", "Slow processing"),
]

print("🐛 Testing edge cases...")
for email, description in test_cases:
    print(f"\n📧 Test: {description}")
    try:
        result = problematic_analyzer(email)
        if result:
            print(f"  ✅ Success: {result.customer_name}")
        else:
            print("  ⚠️ Returned None")
    except Exception as e:
        print(f"  ❌ Error: {e}")

print("\n🔍 Check the Weave UI to:")
print("  - See failed calls highlighted in red")
print("  - Inspect error messages and stack traces")
print("  - Review inputs that caused failures")

# %% [markdown]
# ## 🚀 Part 9: Advanced Features
#
# Let's explore some advanced Weave features.


# %%
# Custom metadata and tags
@weave.op
def analyze_with_metadata(
    email: str, source: str = "unknown", priority: str = "normal"
) -> Dict[str, Any]:
    """Analyze email with custom metadata tracking."""
    # Add custom attributes to the Weave trace
    weave_op = analyze_with_metadata

    # Process email
    result = analyze_customer_email(email)

    # Return enriched result
    return {
        "analysis": result.model_dump(),
        "metadata": {
            "source": source,
            "priority": priority,
            "processed_at": datetime.now().isoformat(),
            "model_used": "gpt-4o-mini",
        },
    }


# Test with metadata
sources = ["web_form", "email", "chat", "phone_transcript"]
priorities = ["low", "normal", "high", "urgent"]

print("📊 Processing emails from different sources...")
for i, email in enumerate(test_emails):
    source = sources[i % len(sources)]
    priority = priorities[i % len(priorities)]

    result = analyze_with_metadata(email, source=source, priority=priority)
    print(f"  {source} ({priority}): {result['analysis']['sentiment']}")

# %% [markdown]
# ## 🎓 Workshop Summary
#
# ### What you've learned:
#
# 1. **🔍 Tracing**: Every function call is automatically tracked with `@weave.op`
# 2. **🐛 Debugging**: See complete call traces, inputs, outputs, and errors
# 3. **📊 Evaluation**: Build rigorous evaluations with custom scorers
# 4. **🏆 Comparison**: Compare different models and approaches
# 5. **📈 Monitoring**: Track performance, costs, and errors in production
# 6. **🎯 Insights**: Use data to improve your application
#
# ### Next steps:
#
# - 📚 Explore the [Weave documentation](https://weave-docs.wandb.ai/)
# - 🧪 Try building your own evaluations
# - 🔄 Integrate Weave into your existing projects
# - 📊 Use the Weave UI to analyze your application's behavior
#
# ### Pro tips:
#
# - Use descriptive names for your `@weave.op` functions
# - Add type hints for better trace visualization
# - Create reusable Models for easy comparison
# - Build comprehensive evaluation datasets
# - Monitor key metrics in production
#
# Happy building with Weave! 🐝
