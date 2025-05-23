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

import asyncio
import json
import os
import random
from datetime import datetime
from getpass import getpass
from typing import Any, Optional

from openai import OpenAI
from pydantic import BaseModel, Field

import weave
from weave import Dataset, Evaluation, EvaluationLogger, Model, Scorer

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
print("✅ Weave initialized! Check your traces at https://wandb.ai/home")

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
        model="gpt-3.5-turbo",  # Using cheaper model to make errors more likely
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
# ## 📊 Part 3: Building Evaluations
#
# Now let's evaluate our email analyzer using Weave's evaluation framework.
# We'll use a more challenging dataset to expose model weaknesses.

# %%
# Create a challenging evaluation dataset
eval_examples = [
    {
        "email": "John Smith here. My DataProcessor-Pro v2.5 isn't working correctly. The data export feature that worked yesterday is now producing corrupted files.",
        "expected_name": "John Smith",
        "expected_product": "DataProcessor-Pro v2.5",
        "expected_sentiment": "negative",
    },
    {
        "email": "Jane from accounting. CloudSync Plus Enterprise works but sometimes the sync is delayed by 10-15 minutes. Not urgent but would like it fixed.",
        "expected_name": "Jane",
        "expected_product": "CloudSync Plus Enterprise",
        "expected_sentiment": "neutral",
    },
    {
        "email": "My SmartHub (model SH-2000) won't connect. - Bob Wilson, Senior Manager",
        "expected_name": "Bob Wilson",
        "expected_product": "SmartHub SH-2000",
        "expected_sentiment": "negative",
    },
    {
        "email": "Hi! Dr. Alice Chen writing. The AI-Assistant tool is fantastic! Minor suggestion: could you add dark mode? Overall very happy.",
        "expected_name": "Dr. Alice Chen",
        "expected_product": "AI-Assistant",
        "expected_sentiment": "positive",
    },
    {
        "email": "URGENT!!! System completely down! Can't access anything on WorkflowMax! This is costing us thousands per hour! Contact: Mike O'Brien, CEO",
        "expected_name": "Mike O'Brien",
        "expected_product": "WorkflowMax",
        "expected_sentiment": "negative",
    },
]

# Create a Weave Dataset
support_dataset = Dataset(name="support_emails", rows=eval_examples)


# 🎯 Define scoring functions
@weave.op
def name_accuracy(expected_name: str, output: CustomerEmail) -> dict[str, Any]:
    """Check if the extracted name matches."""
    is_correct = expected_name.lower() == output.customer_name.lower()
    return {"correct": is_correct, "score": 1.0 if is_correct else 0.0}


@weave.op
def sentiment_accuracy(
    expected_sentiment: str, output: CustomerEmail
) -> dict[str, Any]:
    """Check if the sentiment analysis is correct."""
    is_correct = expected_sentiment.lower() == output.sentiment.lower()
    return {"correct": is_correct, "score": 1.0 if is_correct else 0.0}


@weave.op
def extraction_quality(email: str, output: CustomerEmail) -> dict[str, Any]:
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


# 🚀 Run the evaluation (notebook-friendly version)
evaluation = Evaluation(
    dataset=support_dataset,
    scorers=[name_accuracy, sentiment_accuracy, extraction_quality],
)

print("🏃 Running evaluation...")
# For notebooks, use await instead of asyncio.run
# In Jupyter/IPython notebooks, you can use await directly
# eval_results = await evaluation.evaluate(analyze_customer_email)
# For Python scripts, use:
import nest_asyncio

nest_asyncio.apply()
eval_results = asyncio.run(evaluation.evaluate(analyze_customer_email))
print("✅ Evaluation complete! Check the Weave UI for detailed results.")

# %% [markdown]
# ## 📝 Part 3b: Using EvaluationLogger
#
# The `EvaluationLogger` provides a flexible way to log evaluation data incrementally.
# This is perfect when you don't have all your data upfront or want more control.
#
# **Important**: Since EvaluationLogger doesn't use Model/Dataset objects, the `model`
# and `dataset` parameters are crucial for identification. You can use strings or
# dictionaries for rich metadata!

# %%
# Example using EvaluationLogger for custom evaluation flow
# You can use simple strings for identification
eval_logger = EvaluationLogger(
    model="email_analyzer_gpt35",  # Model name/version
    dataset="support_emails",  # Dataset name stays consistent
)

# Or use dictionaries for richer identification (recommended!)
eval_logger_rich = EvaluationLogger(
    model={
        "name": "email_analyzer",
        "version": "v1.2",
        "llm": "gpt-3.5-turbo",
        "temperature": 0.7,
        "prompt_version": "2024-01",
    },
    dataset={
        "name": "support_emails",
        "version": "2024Q1",
        "size": len(eval_examples),
        "source": "production_samples",
    },
)

# Let's use the rich logger for our demo
print("📊 Using EvaluationLogger with rich metadata...")

# Process each example with more control
for i, example in enumerate(eval_examples[:3]):  # Just first 3 for demo
    # Analyze the email
    try:
        output = analyze_customer_email(example["email"])

        # Log the prediction
        pred_logger = eval_logger_rich.log_prediction(
            inputs={"email": example["email"]}, output=output.model_dump()
        )

        # Log multiple scores for this prediction
        # Check name accuracy
        name_match = example["expected_name"].lower() == output.customer_name.lower()
        pred_logger.log_score(scorer="name_accuracy", score=1.0 if name_match else 0.0)

        # Check sentiment
        sentiment_match = example["expected_sentiment"] == output.sentiment
        pred_logger.log_score(
            scorer="sentiment_accuracy", score=1.0 if sentiment_match else 0.0
        )

        # Custom business logic score
        if "urgent" in example["email"].lower() and output.sentiment != "negative":
            pred_logger.log_score(
                scorer="urgency_detection",
                score=0.0,  # Failed to detect urgency
            )
        else:
            pred_logger.log_score(scorer="urgency_detection", score=1.0)

        # Always finish logging for each prediction
        pred_logger.finish()

    except Exception as e:
        print(f"Error processing example {i+1}: {e}")
        # You can still log failed predictions
        pred_logger = eval_logger_rich.log_prediction(
            inputs={"email": example["email"]}, output={"error": str(e)}
        )
        pred_logger.log_score(scorer="success", score=0.0)
        pred_logger.finish()

# Log summary statistics
eval_logger_rich.log_summary(
    {
        "total_examples": 3,
        "evaluation_type": "manual",
        "timestamp": datetime.now().isoformat(),
        "notes": "Workshop demo with rich metadata",
    }
)

print("✅ EvaluationLogger demo complete! Check the Weave UI.")
print("💡 Tip: The rich metadata makes it easy to filter and compare evaluations!")

# %% [markdown]
# ## 🏆 Part 4: Model Comparison
#
# Let's compare different approaches using Weave's Model class.
# We'll create models with varying quality to see clear differences.


# %%
# Define different model variants
class EmailAnalyzerModel(Model):
    """Base model for email analysis with configurable parameters."""

    model_name: str = "gpt-3.5-turbo"
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


# Create model variants with different quality levels
basic_model = EmailAnalyzerModel(
    name="basic_analyzer",
    system_prompt="Extract name, product, issue, sentiment.",  # Too simple
    temperature=0.9,  # Too high - more random
)

detailed_model = EmailAnalyzerModel(
    name="detailed_analyzer",
    system_prompt="""You are an expert customer support analyst.
    Carefully extract:
    - Customer name (full name, check signatures and greetings)
    - Product name (include version/model numbers)
    - Issue description (be specific)
    - Sentiment (positive/neutral/negative based on tone and urgency)
    
    Pay attention to edge cases like names in signatures or product versions.""",
    temperature=0.0,
    model_name="gpt-4o-mini",  # Better model
)

balanced_model = EmailAnalyzerModel(
    name="balanced_analyzer",
    system_prompt="""Extract customer information from support emails.
    Look for: customer name (anywhere in email), product (with any version info),
    issue description, and sentiment. Be thorough but concise.""",
    temperature=0.3,
)

# %% [markdown]
# ## 🔄 Part 5: A/B Testing Models
#
# **Important Concept**: When comparing models, we use the SAME evaluation definition
# (same dataset + scorers) for all models. This ensures fair comparison and allows
# everyone in the workshop to see aggregated results. Each evaluation run gets a
# unique ID automatically, but the evaluation definition stays consistent.


# %%
async def compare_models(models: list[Model], dataset: Dataset) -> dict[str, Any]:
    """Run A/B comparison of multiple models."""
    results = {}

    # Create a single evaluation definition that will be used for all models
    evaluation = Evaluation(
        name="email_analyzer_comparison",  # Same eval for all models
        dataset=dataset,
        scorers=[name_accuracy, sentiment_accuracy, extraction_quality],
    )

    for model in models:
        print(f"\n📊 Evaluating {model.name}...")

        # Run evaluation with optional display name for this specific run
        eval_result = await evaluation.evaluate(
            model, __weave={"display_name": f"Run: {model.name}"}
        )
        results[model.name] = eval_result

        print(f"✅ {model.name} evaluation complete!")

    return results


# Run the comparison
print("🏁 Starting model comparison...")
# For notebooks: comparison_results = await compare_models(...)
# For scripts:
comparison_results = asyncio.run(
    compare_models([basic_model, detailed_model, balanced_model], support_dataset)
)
print("\n🎉 Comparison complete! View the results in the Weave UI.")

# %% [markdown]
# ## 🐞 Part 6: Exception Tracking
#
# Weave automatically tracks exceptions, helping you debug failures in production.
# This is especially useful when dealing with structured outputs.


# %%
# Define a stricter data structure that's more likely to fail
class DetailedCustomerEmail(BaseModel):
    customer_name: str = Field(description="Full name of the customer")
    customer_title: Optional[str] = Field(description="Job title if mentioned")
    company: Optional[str] = Field(description="Company name if mentioned")
    product: str = Field(description="Product name including version")
    product_version: Optional[str] = Field(description="Specific version number")
    issue: str = Field(description="Detailed issue description")
    severity: str = Field(description="critical, high, medium, or low")
    sentiment: str = Field(description="positive, neutral, or negative")


@weave.op
def analyze_detailed_email(email: str) -> DetailedCustomerEmail:
    """Analyze email with strict schema - more likely to fail."""
    client = OpenAI()

    response = client.beta.chat.completions.parse(
        model="gpt-3.5-turbo",  # Using weaker model
        messages=[
            {
                "role": "system",
                "content": "Extract ALL fields. Use 'Unknown' if not found.",
            },
            {
                "role": "user",
                "content": email,
            },
        ],
        response_format=DetailedCustomerEmail,
        temperature=0.8,  # Higher temperature = more errors
    )

    return response.choices[0].message.parsed


# Test with various emails to see exceptions
test_emails_for_errors = [
    "Fix this NOW!",  # Too short, missing info
    "The thing is broken - Anonymous",  # Missing key details
    test_email,  # Should work
]

print("🐞 Testing exception tracking...")
for i, email in enumerate(test_emails_for_errors):
    print(f"\n📧 Test {i+1}:")
    try:
        result = analyze_detailed_email(email)
        print(f"✅ Success: {result.customer_name} - {result.product}")
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {str(e)}")
        print("   Check Weave UI to see the full error trace!")


# Demonstrate JSON parsing errors
@weave.op
def parse_customer_response(response_text: str) -> dict:
    """Parse a JSON response - demonstrates parsing errors."""
    # This will fail if response_text is not valid JSON
    data = json.loads(response_text)

    # This will fail if required fields are missing
    return {
        "name": data["customer"]["name"],  # Nested field access
        "issue": data["issue"]["description"],
        "priority": data["priority"],
    }


# Test parsing errors
test_responses = [
    '{"customer": {"name": "John"}, "issue": {"description": "Bug"}, "priority": "high"}',  # Valid
    '{"name": "Jane", "issue": "Problem"}',  # Missing nested structure
    "Not JSON at all!",  # Invalid JSON
]

print("\n\n🔍 Testing JSON parsing errors...")
for i, response in enumerate(test_responses):
    print(f"\n📄 Test {i+1}:")
    try:
        result = parse_customer_response(response)
        print(f"✅ Parsed successfully: {result}")
    except json.JSONDecodeError as e:
        print(f"❌ JSON Error: {e}")
    except KeyError as e:
        print(f"❌ Missing field: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {type(e).__name__}: {e}")

# %% [markdown]
# ## 📈 Part 7: Cost & Performance Tracking
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
# ## 🎯 Part 8: Production Monitoring with Scorers
#
# Use Weave's scorer system for real-time guardrails and quality monitoring.
# This demonstrates the apply_scorer pattern for production use.

# %%
from datetime import datetime


# Define custom scorers for production monitoring
class ToxicityScorer(Scorer):
    @weave.op
    def score(self, output: dict) -> dict:
        """Check for toxic or inappropriate content."""
        # Simplified toxicity check - in production, use a real model
        toxic_words = ["stupid", "hate", "terrible", "worst"]

        text_to_check = str(output.get("issue", "")).lower()

        for word in toxic_words:
            if word in text_to_check:
                return {
                    "flagged": True,
                    "reason": f"Contains potentially toxic word: {word}",
                    "severity": "medium",
                }

        return {"flagged": False, "reason": None, "severity": None}


class ResponseQualityScorer(Scorer):
    @weave.op
    def score(self, output: dict, email: str) -> dict:
        """Evaluate the quality of the extraction."""
        score = 0.0
        issues = []

        # Check completeness
        if not output.get("customer_name") or output["customer_name"] == "Unknown":
            issues.append("Missing customer name")
        else:
            score += 0.25

        if not output.get("product") or output["product"] == "Unknown":
            issues.append("Missing product")
        else:
            score += 0.25

        if not output.get("issue") or len(output["issue"]) < 10:
            issues.append("Insufficient issue description")
        else:
            score += 0.25

        # Check relevance
        if email and len(output.get("issue", "")) > 0:
            # Simple relevance check - in production, use embeddings
            email_words = set(email.lower().split())
            issue_words = set(output.get("issue", "").lower().split())
            overlap = len(email_words & issue_words) / max(len(email_words), 1)
            if overlap > 0.2:
                score += 0.25
            else:
                issues.append("Issue description may not match email content")

        return {"quality_score": score, "passed": score >= 0.75, "issues": issues}


@weave.op
def production_email_handler(
    email: str, request_id: Optional[str] = None
) -> dict[str, Any]:
    """Production-ready email handler that returns analysis results."""
    # Generate request ID if not provided
    if not request_id:
        request_id = f"req_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{random.randint(1000, 9999)}"

    try:
        # Process the email
        analysis = analyze_customer_email(email)
        urgency = classify_urgency(email, analysis.sentiment)

        # Return the result
        return {
            "request_id": request_id,
            "status": "success",
            "analysis": analysis.model_dump(),
            "urgency": urgency,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        # Log error and return error response
        return {
            "request_id": request_id,
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


# Initialize scorers once (for performance)
toxicity_scorer = ToxicityScorer()
quality_scorer = ResponseQualityScorer()


async def handle_email_with_monitoring(email: str) -> dict[str, Any]:
    """Handle email with production monitoring and guardrails."""
    # Process the email and get the Call object
    result, call = production_email_handler.call(email)

    if result["status"] == "success":
        # Apply scorers for monitoring
        toxicity_check = await call.apply_scorer(toxicity_scorer)
        quality_check = await call.apply_scorer(
            quality_scorer, additional_scorer_kwargs={"email": email}
        )

        # Check toxicity (guardrail)
        if toxicity_check.result["flagged"]:
            print(f"⚠️ Content flagged: {toxicity_check.result['reason']}")
            # In production, you might modify or block the response
            result["warning"] = "Content flagged for review"

        # Check quality (monitoring)
        if not quality_check.result["passed"]:
            print(f"📊 Quality issues: {quality_check.result['issues']}")
            # Log for improvement but don't block
            result["quality_score"] = quality_check.result["quality_score"]

    return result


# Test production monitoring
print("🏭 Testing production monitoring with scorers...")
production_test_emails = [
    "Hi, I'm CEO Jane Smith. Our Enterprise Suite is down and this stupid system is costing us money!",
    "Hi support, my product isn't working. Please help. Thanks, Tom",
    "My DataVault backup failed. Need help ASAP! The error says 'connection timeout'. - Mary Johnson",
]

# For notebooks:
# for email in production_test_emails:
#     result = await handle_email_with_monitoring(email)
# For scripts:
for email in production_test_emails:
    print(f"\n📧 Processing: {email[:50]}...")
    result = asyncio.run(handle_email_with_monitoring(email))
    print(f"  Status: {result['status']}")
    if "warning" in result:
        print(f"  ⚠️ Warning: {result['warning']}")
    if "quality_score" in result:
        print(f"  📊 Quality Score: {result['quality_score']:.2f}")

print("\n✅ Check the Weave UI to see scorer results attached to each call!")

# %% [markdown]
# ## 🐛 Part 9: Debugging Failed Calls
#
# Weave makes it easy to debug when things go wrong.


# %%
@weave.op
def problematic_analyzer(email: str) -> Optional[CustomerEmail]:
    """An analyzer that might fail - perfect for debugging!"""
    if "error" in email.lower():
        raise ValueError("Email contains error keyword!")
    if len(email) < 20:
        print("⚠️ Email too short, returning None")
        return None
    if "urgent" in email.lower():
        # Simulate a timeout
        import time

        time.sleep(0.1)  # In real scenarios, this might be a network timeout

    return analyze_customer_email(email)


# Test with problematic inputs
debug_test_emails = [
    "Error in system",  # Will raise exception
    "Too short",  # Will return None
    "URGENT: Normal email from Alice about ProductX not working properly",  # Will be slow
]

print("🔍 Testing problematic analyzer...")
for email in debug_test_emails:
    print(f"\n📧 Testing: {email}")
    try:
        result = problematic_analyzer(email)
        if result:
            print(f"✅ Success: {result.customer_name}")
        else:
            print("⚠️ Returned None")
    except Exception as e:
        print(f"❌ Exception: {type(e).__name__}: {e}")

print("\n💡 Check the Weave UI to see:")
print("  - Red highlighted failed calls")
print("  - Full stack traces for exceptions")
print("  - Timing information for slow calls")

# %% [markdown]
# ## 🎉 Wrap Up
#
# Congratulations! You've learned how to:
#
# ✅ **Trace** - Track every function call with `@weave.op`
# ✅ **Evaluate** - Build comprehensive evaluation suites
# ✅ **Compare** - Make data-driven model decisions
# ✅ **Monitor** - Use scorers as guardrails and monitors
# ✅ **Debug** - Track exceptions and analyze failures
#
# ### 🚀 Next Steps
#
# 1. **This week**: Add Weave to one of your existing projects
# 2. **Explore**: Try the built-in scorers (HallucinationFreeScorer, SummarizationScorer, etc.)
# 3. **Share**: Join the W&B Community and share your experiences
#
# ### 📚 Resources
#
# - [Weave Documentation](https://weave-docs.wandb.ai/)
# - [Built-in Scorers](https://weave-docs.wandb.ai/guides/evaluation/builtin_scorers)
# - [W&B Community](https://wandb.ai/community)
#
# Happy building with Weave! 🐝
