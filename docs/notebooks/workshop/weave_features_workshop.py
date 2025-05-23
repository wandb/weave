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
import re
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
# Create a challenging evaluation dataset with tricky examples
eval_examples = [
    # Easy examples (even basic model should get these)
    {
        "email": "Hi Support, I'm John Smith and my DataProcessor-Pro v2.5 isn't working correctly. The data export feature is producing corrupted files. Very frustrated!",
        "expected_name": "John Smith",
        "expected_product": "DataProcessor-Pro v2.5",
        "expected_sentiment": "negative",
    },
    {
        "email": "Hello, this is Dr. Alice Chen. I wanted to say that your AI-Assistant tool is fantastic! Everything works perfectly. Thank you!",
        "expected_name": "Dr. Alice Chen",
        "expected_product": "AI-Assistant",
        "expected_sentiment": "positive",
    },
    # Medium difficulty - ambiguous names/products
    {
        "email": "Jane from accounting here. The CloudSync Plus works fine but Enterprise Sync Module has delays. Not critical.",
        "expected_name": "Jane",
        "expected_product": "Enterprise Sync Module",  # NOT CloudSync Plus!
        "expected_sentiment": "neutral",
    },
    {
        "email": "My SmartHub won't connect to anything. Super annoying. - Bob Wilson\nSenior Manager\nTech Solutions Inc",
        "expected_name": "Bob Wilson",
        "expected_product": "SmartHub",  # Model info missing
        "expected_sentiment": "negative",
    },
    {
        "email": "Spoke with Sarah about the issue. Still having problems with WorkflowMax crashing. Mike O'Brien, CEO",
        "expected_name": "Mike O'Brien",  # NOT Sarah
        "expected_product": "WorkflowMax",
        "expected_sentiment": "negative",
    },
    # Hard examples - names in unusual places
    {
        "email": "The new update broke everything! Nothing works anymore on the ProSuite 3000. Call me - signed, frustrated customer Zhang Wei",
        "expected_name": "Zhang Wei",
        "expected_product": "ProSuite 3000",
        "expected_sentiment": "negative",
    },
    {
        "email": "RE: Ticket #1234\nCustomer María García called about CloudVault. She says thanks for fixing the sync issue! Works great now.",
        "expected_name": "María García",
        "expected_product": "CloudVault",
        "expected_sentiment": "positive",
    },
    {
        "email": "My assistant Jennifer will send the logs. The actual problem is with DataMiner Pro, not the viewer. -Raj (Dr. Rajesh Patel)",
        "expected_name": "Dr. Rajesh Patel",  # NOT Jennifer, and full name from signature
        "expected_product": "DataMiner Pro",  # NOT the viewer
        "expected_sentiment": "neutral",  # Matter-of-fact, not emotional
    },
    # Very hard - misleading information
    {
        "email": "Johnson recommended your software. Smith from our team loves CloudSync. But I'm having issues with it. Brown, James Brown.",
        "expected_name": "James Brown",  # NOT Johnson or Smith
        "expected_product": "CloudSync",
        "expected_sentiment": "negative",  # Having issues despite others liking it
    },
    {
        "email": "Great product! Though the InvoiceGen module crashes sometimes. Still recommend it! Anna from Stockholm",
        "expected_name": "Anna",
        "expected_product": "InvoiceGen module",
        "expected_sentiment": "positive",  # Overall positive despite crashes
    },
    {
        "email": "Update on case by Thompson: Lee's WorkStation Pro still showing error 0x80004005. Previous tech couldn't resolve.",
        "expected_name": "Lee",  # NOT Thompson
        "expected_product": "WorkStation Pro",
        "expected_sentiment": "negative",
    },
    # Extremely hard - complex scenarios
    {
        "email": "Hi, chatted with your colleague Emma (super helpful!). Anyway, ReportBuilder works ok but takes forever. —Samantha Park, CTO",
        "expected_name": "Samantha Park",  # NOT Emma
        "expected_product": "ReportBuilder",
        "expected_sentiment": "neutral",  # "works ok" but slow - not fully negative
    },
    {
        "email": "FYI - Customer called: Pierre-Alexandre Dubois mentioned the API-Gateway is fantastic, just needs better docs. Direct quote.",
        "expected_name": "Pierre-Alexandre Dubois",
        "expected_product": "API-Gateway",
        "expected_sentiment": "positive",  # "fantastic" outweighs doc complaint
    },
    {
        "email": "Worst experience ever with tech support! Though I admit ProductX works well. O'Sullivan here (Francis).",
        "expected_name": "Francis O'Sullivan",  # Name split across sentence
        "expected_product": "ProductX",
        "expected_sentiment": "negative",  # Support experience outweighs product working
    },
    # Trick examples - products that sound like names
    {
        "email": "Maxwell keeps crashing! This software is terrible. Signed, angry user Li Chen",
        "expected_name": "Li Chen",
        "expected_product": "Maxwell",  # Maxwell is the product, not a person
        "expected_sentiment": "negative",
    },
    {
        "email": "Please tell Gordon that the Morgan Analytics Suite works perfectly now. Thanks! - Yuki Tanaka",
        "expected_name": "Yuki Tanaka",  # NOT Gordon
        "expected_product": "Morgan Analytics Suite",  # Morgan is part of product name
        "expected_sentiment": "positive",
    },
    # Ambiguous sentiment
    {
        "email": "DataFlow Pro is exactly what I expected from your company. Classic experience. João Silva, Product Manager",
        "expected_name": "João Silva",
        "expected_product": "DataFlow Pro",
        "expected_sentiment": "negative",  # Sarcastic - "expected" and "classic" imply typically bad
    },
    {
        "email": "The ChromaEdit tool works... I guess. Does what it says. Whatever. -Kim",
        "expected_name": "Kim",
        "expected_product": "ChromaEdit tool",
        "expected_sentiment": "neutral",  # Apathetic, not negative or positive
    },
    # Multiple products mentioned
    {
        "email": "Upgraded from TaskMaster to ProjectPro. Having issues with ProjectPro's gantt charts. Anne-Marie Rousseau",
        "expected_name": "Anne-Marie Rousseau",
        "expected_product": "ProjectPro",  # The one with issues, not TaskMaster
        "expected_sentiment": "negative",
    },
    {
        "email": "Hi! love your VideoEdit, PhotoEdit, and AudioEdit apps! Especially AudioEdit! Muhammad here :)",
        "expected_name": "Muhammad",
        "expected_product": "AudioEdit",  # The one especially mentioned
        "expected_sentiment": "positive",
    },
    # Edge cases
    {
        "email": "Yo! Sup? Ur SystemMonitor thing is broke af. fix it asap!!!! - xXx_Dmitri_xXx",
        "expected_name": "Dmitri",  # Extract from gamertag
        "expected_product": "SystemMonitor",
        "expected_sentiment": "negative",
    },
    {
        "email": "¡Hola! Carlos Méndez aquí. Su programa FinanceTracker es excelente pero muy caro. Gracias.",
        "expected_name": "Carlos Méndez",
        "expected_product": "FinanceTracker",
        "expected_sentiment": "neutral",  # Good but expensive = neutral
    },
    {
        "email": "Re: Jackson's complaint\n\nI disagree with Jackson. The Scheduler App works fine for me.\n\nBest,\nPriya Sharma\nHead of IT",
        "expected_name": "Priya Sharma",  # NOT Jackson
        "expected_product": "Scheduler App",
        "expected_sentiment": "positive",  # Disagrees with complaint
    },
    {
        "email": "This is regarding the issue with CloudBackup Pro v3.2.1 that Jennifer Chen reported. I'm her manager, David Kim, following up.",
        "expected_name": "David Kim",  # The sender, not Jennifer
        "expected_product": "CloudBackup Pro v3.2.1",
        "expected_sentiment": "negative",  # Following up on an issue
    },
    {
        "email": "😡😡😡 InventoryMaster deleted everything!!! 😭😭😭 - call me back NOW! //Singh",
        "expected_name": "Singh",
        "expected_product": "InventoryMaster",
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
# ## 🎯 Part 3b: Using Pre-built Scorers
#
# Weave provides many pre-built scorers for common evaluation tasks!
# No need to reinvent the wheel for standard metrics.
#
# **Note**: To use pre-built scorers, install with: `pip install weave[scorers]`

# %%
# Import pre-built scorers
try:
    from weave.scorers import (
        EmbeddingSimilarityScorer,
        OpenAIModerationScorer,
        PydanticScorer,
        ValidJSONScorer,
        ValidXMLScorer,
    )

    SCORERS_AVAILABLE = True
except ImportError:
    SCORERS_AVAILABLE = False
    print("⚠️ Pre-built scorers not available. Install with: pip install weave[scorers]")

# Example 1: ValidJSONScorer - Check if output is valid JSON
if SCORERS_AVAILABLE:

    @weave.op
    def generate_user_data(request: str) -> str:
        """Generate user data in JSON format."""
        if "valid" in request.lower():
            return '{"name": "John Doe", "age": 30, "email": "john@example.com"}'
        elif "invalid" in request.lower():
            return '{"name": "Jane Doe", "age": 25, "email"'  # Invalid JSON
        else:
            return "This is not JSON at all"

    # Create a dataset
    json_dataset = Dataset(
        name="json_validation_test",
        rows=[
            {"request": "Generate valid user JSON"},
            {"request": "Generate invalid JSON"},
            {"request": "Generate plain text"},
        ],
    )

    # Use the ValidJSONScorer
    json_scorer = ValidJSONScorer()

    print("🎯 Example 1: ValidJSONScorer")
    # Quick test
    test_output = generate_user_data("Generate valid user JSON")
    json_result = asyncio.run(json_scorer.score(output=test_output))
    print(f"  Valid JSON? {json_result['json_valid']}")

# Example 2: PydanticScorer - Validate against a schema
if SCORERS_AVAILABLE:
    from pydantic import EmailStr

    class UserData(BaseModel):
        name: str
        age: int
        email: EmailStr

    @weave.op
    def generate_structured_data(request: str) -> str:
        """Generate data that should match UserData schema."""
        if "correct" in request.lower():
            return '{"name": "Alice Smith", "age": 28, "email": "alice@example.com"}'
        else:
            return '{"name": "Bob", "age": "twenty-five", "email": "not-an-email"}'

    # Use PydanticScorer with our schema
    pydantic_scorer = PydanticScorer(model=UserData)

    print("\n🎯 Example 2: PydanticScorer")
    test_output = generate_structured_data("Generate correct data")
    pydantic_result = asyncio.run(pydantic_scorer.score(output=test_output))
    print(f"  Valid schema? {pydantic_result['pydantic_valid']}")

# Example 3: EmbeddingSimilarityScorer - Semantic similarity
if SCORERS_AVAILABLE:
    similarity_dataset = Dataset(
        name="similarity_test",
        rows=[
            {
                "input": "What's the weather like?",
                "target": "How is the weather today?",  # Similar meaning
            },
            {
                "input": "Tell me about dogs",
                "target": "Explain quantum physics",  # Very different
            },
        ],
    )

    @weave.op
    def paraphrase_model(input: str) -> str:
        """A model that attempts to paraphrase."""
        # In reality, this would use an LLM
        if "weather" in input.lower():
            return "What are the weather conditions?"
        else:
            return "Something completely different"

    # Use EmbeddingSimilarityScorer (requires OpenAI API key)
    similarity_scorer = EmbeddingSimilarityScorer(
        model_id="openai/text-embedding-3-small",
        threshold=0.7,  # Cosine similarity threshold
    )

    print("\n🎯 Example 3: EmbeddingSimilarityScorer")
    print("  (Compares semantic similarity between outputs and targets)")

# Example 4: OpenAIModerationScorer - Content safety
if SCORERS_AVAILABLE:

    @weave.op
    def user_content_generator(prompt: str) -> str:
        """Generate user content based on prompt."""
        if "angry" in prompt.lower():
            return "I'm so frustrated with this terrible service!"
        else:
            return "Thank you for the wonderful support!"

    moderation_dataset = Dataset(
        name="moderation_test",
        rows=[
            {"prompt": "Write an angry review"},
            {"prompt": "Write a positive review"},
        ],
    )

    # Use OpenAIModerationScorer
    moderation_scorer = OpenAIModerationScorer()

    print("\n🎯 Example 4: OpenAIModerationScorer")
    print("  (Checks for potentially harmful content)")

# Show all available pre-built scorers
print("\n📚 Available Pre-built Scorers in Weave:")
print("  ✅ ValidJSONScorer - Validate JSON output")
print("  ✅ ValidXMLScorer - Validate XML output")
print("  ✅ PydanticScorer - Validate against Pydantic models")
print("  ✅ EmbeddingSimilarityScorer - Semantic similarity")
print("  ✅ OpenAIModerationScorer - Content moderation")
print("  ✅ HallucinationFreeScorer - Check for hallucinations")
print("  ✅ SummarizationScorer - Evaluate summaries")
print("  ✅ ContextEntityRecallScorer - RAGAS entity recall")
print("  ✅ ContextRelevancyScorer - RAGAS relevancy")
print("\n💡 Install with: pip install weave[scorers]")
print("📖 Full docs: https://docs.wandb.ai/guides/weave/evaluation/builtin_scorers")

# %% [markdown]
# ## 📝 Part 3c: Using EvaluationLogger
#
# The `EvaluationLogger` provides a flexible way to log evaluation data incrementally.
# This is perfect when you don't have all your data upfront or want more control.
#
# **Important**: Since EvaluationLogger doesn't use Model/Dataset objects, the `model`
# and `dataset` parameters are crucial for identification.
# - `model`: Can be a string OR dictionary (for rich metadata)
# - `dataset`: Must be a string

# %%
# Example using EvaluationLogger for custom evaluation flow
# You can use simple strings for identification (commented out on purpose)
# eval_logger = EvaluationLogger(
#     model="email_analyzer_gpt35",  # Model name/version
#     dataset="support_emails",  # Dataset name (must be string)
# )

# Model can use dictionaries for richer identification (recommended!)
# Dataset must be a string
eval_logger_rich = EvaluationLogger(
    model={
        "name": "email_analyzer",
        "version": "v1.2",
        "llm": "gpt-3.5-turbo",
        "temperature": 0.7,
        "prompt_version": "2024-01",
    },
    dataset="support_emails_2024Q1",  # Dataset must be string
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

    label: str = "email_analyzer"
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


# Create model variants with different quality levels
basic_model = EmailAnalyzerModel(
    label="basic_analyzer",
    system_prompt="Extract customer name, product name, issue, and sentiment from email.",  # Too simple - no guidance
    temperature=0.95,  # Very high - more random/mistakes
)

detailed_model = EmailAnalyzerModel(
    label="detailed_analyzer",
    system_prompt="""You are an expert customer support analyst. Carefully analyze the email:

CRITICAL RULES:
1. Customer name: Extract the name of the person WRITING the email (not people mentioned)
   - Check signatures, sign-offs, and self-introductions
   - If multiple names appear, identify who is actually writing
   - Include full name if available (e.g., "Dr. Rajesh Patel" not just "Raj")
   
2. Product: Identify the SPECIFIC product having issues
   - If multiple products mentioned, focus on the problematic one
   - Include version numbers if provided
   - Don't confuse product names with people names
   
3. Sentiment: Analyze the OVERALL tone
   - positive: satisfied, happy, thankful (even with minor complaints)
   - negative: frustrated, angry, disappointed
   - neutral: matter-of-fact, indifferent, mixed feelings
   - Consider sarcasm and actual meaning beyond words""",
    temperature=0.0,  # Precise
)

balanced_model = EmailAnalyzerModel(
    label="balanced_analyzer",
    system_prompt="""Extract customer support information from emails.
    
    Guidelines:
    - Customer name: The person sending the email (check signatures)
    - Product: The main product being discussed
    - Issue: Brief description of the problem
    - Sentiment: Overall tone (positive/negative/neutral)""",
    temperature=0.4,  # Moderate temperature
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
        print(f"\n📊 Evaluating {model.label}...")

        # Run evaluation with optional display name for this specific run
        eval_result = await evaluation.evaluate(
            model,
            __weave={"display_name": f"email_analyzer_comparison - {model.label}"},
        )
        results[model.label] = eval_result

        print(f"✅ {model.label} evaluation complete!")

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
#
# **Workshop Note**: We intentionally use an older model (gpt-3.5-turbo) without
# structured output support to demonstrate real-world parsing challenges and exceptions.


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

    # Use a less capable model without structured outputs
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",  # Older model, no structured outputs
        messages=[
            {
                "role": "system",
                "content": """Extract ALL fields from the email and return as JSON:
                {
                    "customer_name": "full name",
                    "customer_title": "job title or null",
                    "company": "company name or null", 
                    "product": "product name with version",
                    "product_version": "version number or null",
                    "issue": "detailed issue description",
                    "severity": "critical/high/medium/low",
                    "sentiment": "positive/neutral/negative"
                }
                Use null for missing optional fields. All fields are required.""",
            },
            {
                "role": "user",
                "content": email,
            },
        ],
        temperature=0.9,  # High temperature = more unpredictable
    )

    # Manual JSON parsing - prone to errors!
    try:
        # Extract JSON from response (model might add extra text)
        response_text = response.choices[0].message.content

        # Try to find JSON in the response (brittle!)
        json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
        if not json_match:
            raise ValueError("No JSON found in response")

        json_str = json_match.group(0)
        data = json.loads(json_str)

        # Manual validation and construction (many failure points!)
        return DetailedCustomerEmail(
            customer_name=data["customer_name"],
            customer_title=data.get("customer_title"),
            company=data.get("company"),
            product=data["product"],
            product_version=data.get("product_version"),
            issue=data["issue"],
            severity=data["severity"],
            sentiment=data["sentiment"],
        )
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        # Re-raise with more context
        raise ValueError(
            f"Failed to parse model response: {str(e)}. Response was: {response_text[:200]}..."
        )


# Test with various emails to see exceptions
test_emails_for_errors = [
    "Fix this NOW!",  # Too short, missing almost everything
    "The thing is broken - Anonymous",  # Missing key details
    "My product isn't working",  # No name, no specific product
    "😡😡😡",  # Just emojis
    "Contact: J. Smith\nProduct: Version 2.0\nIssue: Yes",  # Ambiguous/incomplete
    "HELP! Everything is on fire! Call 911!",  # Panic mode, no real info
    test_email,  # This one might work
    "I am very satisfied with your service. Thank you! -A Customer",  # Positive but missing product
]

print("🐞 Testing exception tracking with challenging emails...")
print("=" * 60)
for i, email in enumerate(test_emails_for_errors):
    print(f"\n📧 Test {i+1}: '{email[:50]}{'...' if len(email) > 50 else ''}'")
    try:
        result = analyze_detailed_email(email)
        print(f"✅ Success: {result.customer_name} - {result.product}")
        print(f"   Severity: {result.severity}, Sentiment: {result.sentiment}")
    except ValueError as e:
        print(f"❌ Parsing Error: {str(e)[:100]}...")
    except Exception as e:
        print(f"❌ {type(e).__name__}: {str(e)[:100]}...")
    print("   → Check Weave UI for full trace!")


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
    primary_model: str = "gpt-4o",
    fallback_model: str = "gpt-4o-mini",
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
#
# **Key Concepts**:
# - **Guardrails**: Block or modify responses (e.g., toxicity filter)
# - **Monitors**: Track quality metrics without blocking

# %%
from datetime import datetime


# Define more realistic production scorers
class ContentModerationScorer(Scorer):
    """Production-ready content moderation scorer."""

    @weave.op
    def score(self, output: dict) -> dict:
        """Check for inappropriate content using multiple signals."""
        # Handle both success and error cases
        if output.get("status") != "success":
            return {"flagged": False, "flags": [], "severity": "none", "action": "pass"}

        analysis = output.get("analysis", {})
        issue_text = analysis.get("issue", "").lower()
        sentiment = analysis.get("sentiment", "neutral")

        # Check for various inappropriate content patterns
        profanity_patterns = [
            "stupid",
            "idiotic",
            "garbage",
            "trash",
            "sucks",
            "terrible",
            "awful",
            "worst",
        ]
        threat_patterns = ["sue", "lawyer", "legal action", "court", "lawsuit"]

        flags = []
        severity = "none"

        # Check profanity
        profanity_found = []
        for word in profanity_patterns:
            if word in issue_text:
                profanity_found.append(word)

        if profanity_found:
            flags.append(f"Profanity detected: {', '.join(profanity_found)}")
            severity = "medium"

        # Check threats
        threats_found = []
        for pattern in threat_patterns:
            if pattern in issue_text:
                threats_found.append(pattern)

        if threats_found:
            flags.append(f"Legal threat: {', '.join(threats_found)}")
            severity = "high"

        # Check extreme sentiment with profanity
        if sentiment == "negative" and profanity_found:
            severity = "high"
            flags.append("Negative sentiment with profanity")

        return {
            "flagged": len(flags) > 0,
            "flags": flags,
            "severity": severity,
            "action": "block"
            if severity == "high"
            else ("review" if severity == "medium" else "pass"),
        }


class ExtractionQualityScorer(Scorer):
    """Monitor extraction quality and completeness."""

    @weave.op
    def score(self, output: dict, email: str) -> dict:
        """Comprehensive quality assessment."""
        if output.get("status") != "success":
            return {
                "quality_score": 0.0,
                "passed": False,
                "issues": ["Failed to process email"],
                "recommendations": [],
                "extraction_grade": "F",
            }

        analysis = output.get("analysis", {})
        quality_metrics = {
            "completeness": 0.0,
            "specificity": 0.0,
            "accuracy": 0.0,
            "consistency": 0.0,
        }
        issues = []
        recommendations = []

        # 1. Completeness checks (40% weight)
        if analysis.get("customer_name") and analysis["customer_name"] not in [
            "Unknown",
            "",
            None,
        ]:
            quality_metrics["completeness"] += 0.15
        else:
            issues.append("Missing customer name")
            recommendations.append("Check email signatures and greetings for names")

        if analysis.get("product") and analysis["product"] not in ["Unknown", "", None]:
            quality_metrics["completeness"] += 0.15
        else:
            issues.append("Missing product identification")
            recommendations.append("Look for product names mentioned in the email")

        if analysis.get("issue") and len(analysis["issue"]) > 10:
            quality_metrics["completeness"] += 0.10
        else:
            issues.append("Issue description too brief or missing")
            recommendations.append("Extract a more detailed problem description")

        # 2. Specificity checks (30% weight)
        product_name = analysis.get("product", "")
        if product_name and any(char.isdigit() for char in str(product_name)):
            # Product includes version/model number
            quality_metrics["specificity"] += 0.15
        elif product_name:
            recommendations.append(
                "Extract product version/model numbers when available"
            )

        issue_desc = analysis.get("issue", "")
        if issue_desc and len(str(issue_desc)) > 30:
            quality_metrics["specificity"] += 0.15
        elif issue_desc:
            recommendations.append("Provide more specific issue details")

        # 3. Accuracy checks (20% weight)
        # Check if extracted content actually appears in email
        email_lower = email.lower()
        customer_name = analysis.get("customer_name", "")
        if customer_name and customer_name != "Unknown":
            name_parts = customer_name.lower().split()
            # Check if at least part of the name appears in email
            if any(part in email_lower for part in name_parts if len(part) > 2):
                quality_metrics["accuracy"] += 0.10
            else:
                issues.append("Extracted name not found in original email")

        product_mentioned = analysis.get("product", "")
        if product_mentioned and product_mentioned != "Unknown":
            # Check for partial matches (product names might be extracted differently)
            product_words = product_mentioned.lower().split()
            if any(word in email_lower for word in product_words if len(word) > 3):
                quality_metrics["accuracy"] += 0.10
            else:
                issues.append("Extracted product not clearly mentioned in email")

        # 4. Consistency checks (10% weight)
        sentiment = analysis.get("sentiment", "neutral")
        urgency = output.get("urgency", "low")

        # Check sentiment/urgency consistency
        consistency_ok = True
        if sentiment == "negative" and urgency == "low":
            if not any(
                word in issue_desc.lower() for word in ["minor", "small", "slight"]
            ):
                consistency_ok = False
                issues.append(
                    "Negative sentiment but low urgency - might be inconsistent"
                )
        elif sentiment == "positive" and urgency == "high":
            consistency_ok = False
            issues.append("Positive sentiment with high urgency is unusual")

        if consistency_ok:
            quality_metrics["consistency"] += 0.10

        # Calculate overall score
        total_score = sum(quality_metrics.values())

        return {
            "quality_score": total_score,
            "quality_metrics": quality_metrics,
            "passed": total_score >= 0.6,  # Lowered threshold for demo
            "issues": issues,
            "recommendations": recommendations,
            "extraction_grade": "A"
            if total_score >= 0.9
            else (
                "B"
                if total_score >= 0.8
                else (
                    "C" if total_score >= 0.6 else ("D" if total_score >= 0.4 else "F")
                )
            ),
        }


class ResponseTimeScorer(Scorer):
    """Monitor response time SLAs."""

    @weave.op
    def score(self, output: dict, processing_time_ms: float) -> dict:
        """Check if response time meets SLA."""
        sla_ms = 1000  # 1 second SLA

        return {
            "processing_time_ms": processing_time_ms,
            "sla_met": processing_time_ms <= sla_ms,
            "sla_margin_ms": sla_ms - processing_time_ms,
            "performance_grade": "fast"
            if processing_time_ms < 500
            else ("normal" if processing_time_ms < 1000 else "slow"),
        }


@weave.op
def production_email_handler(
    email: str, request_id: Optional[str] = None
) -> dict[str, Any]:
    """Production-ready email handler that returns structured analysis results."""
    start_time = datetime.now()

    # Generate request ID if not provided
    if not request_id:
        request_id = f"req_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{random.randint(1000, 9999)}"

    try:
        # Process the email using our existing analyzer
        analysis = analyze_customer_email(email)

        # Calculate urgency based on the analysis
        urgency = classify_urgency(email, analysis.sentiment)

        # Calculate processing time
        processing_time_ms = (datetime.now() - start_time).total_seconds() * 1000

        # Return structured result that scorers expect
        return {
            "request_id": request_id,
            "status": "success",
            "analysis": {
                "customer_name": analysis.customer_name,
                "product": analysis.product,
                "issue": analysis.issue,
                "sentiment": analysis.sentiment,
            },
            "urgency": urgency,
            "processing_time_ms": processing_time_ms,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        # Log error and return error response
        processing_time_ms = (datetime.now() - start_time).total_seconds() * 1000
        return {
            "request_id": request_id,
            "status": "error",
            "error": str(e),
            "processing_time_ms": processing_time_ms,
            "timestamp": datetime.now().isoformat(),
        }


# Initialize scorers
content_moderation_scorer = ContentModerationScorer()
quality_scorer = ExtractionQualityScorer()
response_time_scorer = ResponseTimeScorer()


async def handle_email_with_monitoring(email: str) -> dict[str, Any]:
    """Handle email with production monitoring and guardrails."""
    # Process the email and get the Call object
    result, call = production_email_handler.call(email)

    # Always apply response time scorer
    time_score = await call.apply_scorer(
        response_time_scorer,
        additional_scorer_kwargs={
            "processing_time_ms": result.get("processing_time_ms", 0)
        },
    )

    if result["status"] == "success":
        # Apply content moderation (guardrail)
        moderation_check = await call.apply_scorer(content_moderation_scorer)

        # Apply quality monitoring
        quality_check = await call.apply_scorer(
            quality_scorer, additional_scorer_kwargs={"email": email}
        )

        # Handle moderation results
        if moderation_check.result["flagged"]:
            action = moderation_check.result["action"]
            if action == "block":
                print(f"🚫 Content BLOCKED: {moderation_check.result['flags']}")
                result["blocked"] = True
                result["block_reason"] = moderation_check.result["flags"]
            elif action == "review":
                print(
                    f"⚠️ Content flagged for review: {moderation_check.result['flags']}"
                )
                result["needs_review"] = True
                result["review_reason"] = moderation_check.result["flags"]

        # Add quality metrics
        result["quality_metrics"] = {
            "grade": quality_check.result["extraction_grade"],
            "score": quality_check.result["quality_score"],
            "passed": quality_check.result["passed"],
        }

        if quality_check.result["issues"]:
            print(f"📊 Quality issues: {quality_check.result['issues']}")

        if quality_check.result["recommendations"]:
            print(f"💡 Recommendations: {quality_check.result['recommendations']}")

    # Add performance metrics
    result["performance"] = {
        "sla_met": time_score.result["sla_met"],
        "grade": time_score.result["performance_grade"],
    }

    return result


# Test with varied examples showing both success and failure cases
print("🏭 Testing production monitoring with realistic scenarios...")
print("=" * 70)

production_test_emails = [
    # Good quality extraction - should pass all checks
    {
        "email": "Hello Support Team,\n\nI'm Sarah Mitchell from Acme Corp. Our CloudSync Enterprise v3.2.1 stopped syncing files yesterday at 2pm. The error message says 'Authentication failed'. This is really frustrating and affecting our entire team.\n\nBest regards,\nSarah Mitchell\nIT Manager, Acme Corp",
        "expected": "✅ High quality extraction with version numbers",
    },
    # Profanity with legal threat - should be blocked
    {
        "email": "This stupid software is absolute garbage! I'm John Davis and your DataSync Pro is the worst trash I've ever used. My lawyer will be contacting you about this terrible product that lost our data!",
        "expected": "🚫 Should be blocked - profanity + legal threat",
    },
    # Poor quality but processable - low score but not blocked
    {
        "email": "Hi support, product broken. Fix please. - Tom",
        "expected": "📊 Low quality - minimal details but processable",
    },
    # Good extraction with negative sentiment - quality pass
    {
        "email": "Dear Support,\n\nI'm Mary Johnson, CTO at TechStart Inc. Our DataVault Pro v2.5 backup failed last night with error code 'E501: connection timeout'. This is concerning as we rely on nightly backups for compliance.\n\nMary Johnson\nCTO, TechStart Inc",
        "expected": "✅ Good quality despite negative sentiment",
    },
    # Needs review - mild profanity - should flag for review
    {
        "email": "Mike Wilson here. Your EmailPro system really sucks compared to what was promised, but I guess it's still better than the competition. Can you help me configure the spam filter? It's blocking legitimate emails.",
        "expected": "⚠️ Should flag for review - mild profanity",
    },
    # Excellent quality - should get high scores
    {
        "email": "Hi there,\n\nI'm Lisa Chen from GlobalTech Solutions. I wanted to thank you for the excellent support on our CloudBackup Enterprise v4.2 deployment. Everything is working perfectly and the performance improvements are fantastic!\n\nBest,\nLisa Chen\nVP of Engineering",
        "expected": "✅ Excellent quality with positive sentiment",
    },
    # Missing critical info - should fail quality check
    {
        "email": "Your system crashed and we lost everything! This is unacceptable! Fix this immediately!!!",
        "expected": "❌ Should fail quality - missing customer/product info",
    },
    # Edge case - urgent but positive
    {
        "email": "Urgent: I'm Alex Kumar and I love your RapidDeploy tool! Need to purchase 50 more licenses ASAP for our new team starting Monday. Please expedite!\n\nAlex Kumar\nProcurement Manager",
        "expected": "📊 Unusual case - urgent but positive sentiment",
    },
]

for i, test_case in enumerate(production_test_emails):
    print(f"\n{'='*60}")
    print(f"📧 Test {i+1}/8: {test_case['expected']}")
    print(f"{'='*60}")

    # Show email preview
    email_lines = test_case["email"].split("\n")
    print("📝 Email Content:")
    for line in email_lines[:3]:  # Show first 3 lines
        if line.strip():
            print(f"   {line[:70]}{'...' if len(line) > 70 else ''}")
    if len(email_lines) > 3:
        print(f"   ... ({len(email_lines)-3} more lines)")

    # Process with monitoring
    result = asyncio.run(handle_email_with_monitoring(test_case["email"]))

    # Show extraction results
    print("\n🔍 Extraction Results:")
    if result["status"] == "success":
        analysis = result["analysis"]
        print(f"   Customer: {analysis.get('customer_name', 'Unknown')}")
        print(f"   Product: {analysis.get('product', 'Unknown')}")
        print(
            f"   Issue: {analysis.get('issue', 'Unknown')[:50]}{'...' if len(analysis.get('issue', '')) > 50 else ''}"
        )
        print(f"   Sentiment: {analysis.get('sentiment', 'Unknown')}")
        print(f"   Urgency: {result.get('urgency', 'Unknown')}")
    else:
        print(f"   ❌ Error: {result.get('error', 'Unknown error')}")

    # Show scorer results
    print("\n📊 Scorer Results:")

    # 1. Performance
    perf = result.get("performance", {})
    print(
        f"   ⏱️  Response Time: {perf.get('grade', 'unknown')} ({result.get('processing_time_ms', 0):.0f}ms)"
    )
    print(
        f"      SLA Status: {'✅ Met' if perf.get('sla_met', False) else '❌ Exceeded'}"
    )

    # 2. Content Moderation
    if result["status"] == "success":
        if result.get("blocked"):
            print("   🚫 Content Moderation: BLOCKED")
            print(f"      Reason: {result['block_reason']}")
        elif result.get("needs_review"):
            print("   ⚠️  Content Moderation: REVIEW NEEDED")
            print(f"      Flags: {result['review_reason']}")
        else:
            print("   ✅ Content Moderation: PASSED")

    # 3. Quality Assessment
    if result["status"] == "success":
        quality = result.get("quality_metrics", {})
        print(
            f"   📏 Quality Assessment: Grade {quality.get('grade', 'F')} (Score: {quality.get('score', 0):.2f})"
        )

        # Show what contributed to the score
        if quality.get("score", 0) < 0.6:
            print(
                f"      Status: {'⚠️ Below threshold' if quality.get('passed', False) else '❌ Failed'}"
            )
            # The actual issues are logged by the scorers and visible in Weave UI

print("\n" + "=" * 70)
print("\n🎯 Summary of Production Monitoring Demonstration:")
print("\n1. **Successful Cases** (Tests 1, 4, 6):")
print("   - High-quality extractions with version numbers")
print("   - All required fields present and accurate")
print("   - Fast response times meeting SLA")

print("\n2. **Blocked Content** (Test 2):")
print("   - Multiple profanity words + legal threats = automatic block")
print("   - Protects support agents from abusive content")

print("\n3. **Review Required** (Test 5):")
print("   - Mild profanity triggers review flag")
print("   - Human can decide if response is appropriate")

print("\n4. **Quality Issues** (Tests 3, 7):")
print("   - Missing customer name or product details")
print("   - Too brief to be actionable")
print("   - Would need human intervention")

print("\n5. **Edge Cases** (Test 8):")
print("   - Urgent + positive sentiment (unusual combination)")
print("   - System handles it correctly")

print("\n💡 Key Insights:")
print("   - Different scorers serve different purposes")
print("   - Guardrails (block/review) vs Monitors (quality/performance)")
print("   - All scorer results are tracked in Weave for analysis")
print("\n✅ Check the Weave UI to see detailed scorer results and traces!")

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
