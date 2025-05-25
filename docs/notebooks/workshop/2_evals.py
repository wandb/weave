# %% [markdown]
# # Part 2: Evaluations with Weave
#
# <img src="http://wandb.me/logo-im-png" width="400" alt="Weights & Biases" />
#
# Learn how to systematically evaluate LLM applications using Weave's evaluation framework.
#
# **In this section:**
# - 📊 **Dataset Creation**: Build evaluation datasets with challenging examples
# - 🎯 **Custom Scorers**: Write scoring functions to measure performance
# - 🏃 **Running Evaluations**: Execute evaluations and analyze results
# - 📈 **Pre-built Scorers**: Use Weave's built-in evaluation metrics
# - 🔄 **Model Comparison**: Compare different models and configurations
# - 📝 **EvaluationLogger**: Flexible evaluation logging for custom workflows

# %% [markdown]
# ## Setup
#
# Install dependencies and configure API keys.

# %%
# Install dependencies
# %pip install wandb weave openai pydantic nest_asyncio 'weave[scorers]' -qqq

import asyncio
import os
from datetime import datetime
from getpass import getpass
from typing import Any

from openai import OpenAI
from pydantic import BaseModel, Field

import weave
from weave import Dataset, Evaluation, EvaluationLogger, Model

# Setup API keys
if not os.environ.get("OPENAI_API_KEY"):
    print("Get your OpenAI API key: https://platform.openai.com/api-keys")
    os.environ["OPENAI_API_KEY"] = getpass("Enter your OpenAI API key: ")

# Initialize Weave
weave_client = weave.init("weave-workshop")


# %% [markdown]
# ## 📊 Part 2: Building Evaluations
#
# Now let's evaluate our email analyzer using Weave's evaluation framework.
# We'll use a more challenging dataset to expose model weaknesses.

# **Understanding Weave's Evaluation Data Model:**
# 1. An **evaluation** is the pairing of a dataset and a set of scorers (think of it like a test suite for a specific task)
# 2. An **evaluation run** is the result of running an evaluation against a specific model
# 3. Within an evaluation run, there are (num_rows * num_trials) **predict_and_score** blocks which contain the prediction calls and the scoring calls for a single row of the dataset
# 4. Scores are stored within the predict_and_score output, but also directly on the prediction call itself


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
    trials=3,
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
# ### 🎯 Part 2.1: Using Pre-built Scorers
#
# Weave provides many pre-built scorers for common evaluation tasks!
# No need to reinvent the wheel for standard metrics.
#
# **Note**: To use pre-built scorers, install with: `pip install weave[scorers]`

# %%
# Import pre-built scorers
from weave.scorers import (
    EmbeddingSimilarityScorer,
    OpenAIModerationScorer,
    PydanticScorer,
    ValidJSONScorer,
)

# Example 1: ValidJSONScorer - Check if output is valid JSON
json_scorer = ValidJSONScorer()

print("🎯 Example 1: ValidJSONScorer")
# Test with valid JSON
valid_json = '{"name": "John Doe", "age": 30, "email": "john@example.com"}'
json_result = asyncio.run(json_scorer.score(output=valid_json))
print(f"  Valid JSON: {json_result['json_valid']}")

# Test with invalid JSON
invalid_json = (
    '{"name": "Jane Doe", "age": 25, "email"'  # Missing closing quote and brace
)
invalid_result = asyncio.run(json_scorer.score(output=invalid_json))
print(f"  Invalid JSON: {invalid_result['json_valid']}")

# Example 2: PydanticScorer - Validate against a schema
from pydantic import EmailStr


class UserData(BaseModel):
    name: str
    age: int
    email: EmailStr


# Use PydanticScorer with our schema
pydantic_scorer = PydanticScorer(model=UserData)

print("\n🎯 Example 2: PydanticScorer")
# Test with valid data
valid_data = '{"name": "Alice Smith", "age": 28, "email": "alice@example.com"}'
pydantic_result = asyncio.run(pydantic_scorer.score(output=valid_data))
print(f"  Valid schema: {pydantic_result['pydantic_valid']}")

# Test with invalid data
invalid_data = '{"name": "Bob", "age": "twenty-five", "email": "not-an-email"}'
invalid_pydantic_result = asyncio.run(pydantic_scorer.score(output=invalid_data))
print(f"  Invalid schema: {invalid_pydantic_result['pydantic_valid']}")

# Example 3: EmbeddingSimilarityScorer - Semantic similarity
# Use EmbeddingSimilarityScorer (requires OpenAI API key)
similarity_scorer = EmbeddingSimilarityScorer(
    model_id="openai/text-embedding-3-small",
    threshold=0.7,  # Cosine similarity threshold
)

print("\n🎯 Example 3: EmbeddingSimilarityScorer")
# Test semantic similarity between two similar phrases
output = "What are the weather conditions today?"
target = "How is the weather right now?"

similarity_result = asyncio.run(similarity_scorer.score(output=output, target=target))
print(f"  Similarity score: {similarity_result['similarity_score']:.3f}")
print(f"  Above threshold: {similarity_result['similarity_above_threshold']}")

# Example 4: OpenAIModerationScorer - Content safety
# Use OpenAIModerationScorer
moderation_scorer = OpenAIModerationScorer()

print("\n🎯 Example 4: OpenAIModerationScorer")
# Test content moderation on potentially problematic text
test_content = "I'm so frustrated with this terrible service!"

moderation_result = asyncio.run(moderation_scorer.score(output=test_content))
print(f"  Flagged: {moderation_result['flagged']}")
print(f"  Categories: {moderation_result['categories']}")

# Test with safe content
safe_content = "Thank you for the wonderful support!"
safe_result = asyncio.run(moderation_scorer.score(output=safe_content))
print(f"  Safe content flagged: {safe_result['flagged']}")

# %% [markdown]
# ### 📝 Part 2.2: Pairwise Scoring
#
# Pairwise evaluation compares outputs from two models by ranking them relative to each other.
# This is particularly useful for subjective tasks where absolute scoring is difficult.

# %%
from weave.flow.model import ApplyModelError, apply_model_async


# Create two different email analysis models for comparison
class BasicEmailModel(Model):
    """A basic email analyzer with simple prompts."""

    @weave.op
    def predict(self, email: str) -> CustomerEmail:
        client = OpenAI()
        response = client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Extract customer info from email."},
                {"role": "user", "content": email},
            ],
            response_format=CustomerEmail,
            temperature=0.7,
        )
        return response.choices[0].message.parsed


class AdvancedEmailModel(Model):
    """An advanced email analyzer with detailed prompts."""

    @weave.op
    def predict(self, email: str) -> CustomerEmail:
        client = OpenAI()
        response = client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": """You are an expert customer support analyst. Extract information carefully:
                    - Customer name: The person WRITING the email (check signatures)
                    - Product: The specific product with issues
                    - Issue: Brief description of the problem
                    - Sentiment: Overall emotional tone""",
                },
                {"role": "user", "content": email},
            ],
            response_format=CustomerEmail,
            temperature=0.1,
        )
        return response.choices[0].message.parsed


class EmailPreferenceScorer(weave.Scorer):
    """Compare two email analysis models and determine which performs better."""

    def __init__(self, other_model: Model):
        self.other_model = other_model

    @weave.op
    async def _get_other_model_output(self, example: dict) -> Any:
        """Get output from the comparison model."""
        try:
            other_model_result = await apply_model_async(
                self.other_model,
                example,
                None,
            )

            if isinstance(other_model_result, ApplyModelError):
                return None

            return other_model_result.model_output
        except Exception:
            return None

    @weave.op
    async def score(
        self,
        output: CustomerEmail,
        email: str,
        expected_name: str,
        expected_sentiment: str,
    ) -> dict:
        """Compare primary model output with other model output."""
        other_output = await self._get_other_model_output({"email": email})

        if other_output is None:
            return {
                "primary_is_better": False,
                "reason": "Comparison model failed",
                "primary_score": 0,
                "other_score": 0,
            }

        # Score both models on accuracy
        primary_score = 0
        other_score = 0

        # Check name accuracy
        if output.customer_name.lower() == expected_name.lower():
            primary_score += 1
        if other_output.customer_name.lower() == expected_name.lower():
            other_score += 1

        # Check sentiment accuracy
        if output.sentiment.lower() == expected_sentiment.lower():
            primary_score += 1
        if other_output.sentiment.lower() == expected_sentiment.lower():
            other_score += 1

        primary_is_better = primary_score > other_score

        if primary_score == other_score:
            reason = f"Tie: Both models scored {primary_score}/2"
        else:
            winner = "Primary" if primary_is_better else "Other"
            reason = f"{winner} model more accurate ({primary_score} vs {other_score})"

        return {
            "primary_is_better": primary_is_better,
            "reason": reason,
            "primary_score": primary_score,
            "other_score": other_score,
        }


# Create test dataset for pairwise comparison
pairwise_examples = [
    {
        "email": "Hi, I'm Sarah Johnson and my ProWidget 3000 is broken. Very frustrated!",
        "expected_name": "Sarah Johnson",
        "expected_sentiment": "negative",
    },
    {
        "email": "Thanks for the help! The DataSync tool works perfectly now. - Mike Chen",
        "expected_name": "Mike Chen",
        "expected_sentiment": "positive",
    },
    {
        "email": "My assistant will call about the CloudVault issue. Regards, Dr. Patel",
        "expected_name": "Dr. Patel",
        "expected_sentiment": "neutral",
    },
]

pairwise_dataset = Dataset(name="pairwise_comparison", rows=pairwise_examples)

# Set up models and scorer
basic_model = BasicEmailModel()
advanced_model = AdvancedEmailModel()

# Create preference scorer that compares basic model (primary) vs advanced model (other)
preference_scorer = EmailPreferenceScorer(other_model=advanced_model)

# Run pairwise evaluation
pairwise_evaluation = Evaluation(
    name="email_model_pairwise", dataset=pairwise_dataset, scorers=[preference_scorer]
)

print("🥊 Running pairwise evaluation: Basic vs Advanced model...")
pairwise_results = asyncio.run(pairwise_evaluation.evaluate(basic_model))
print("✅ Pairwise evaluation complete! Check Weave UI for detailed comparisons.")

# %% [markdown]
# ### 📝 Part 2.3: Using EvaluationLogger
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
# ### 🏆 Part 2.4: Model Comparison
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
# ### 🔄 Part 2.5: A/B Testing Models
#
# **Important Concept**: When comparing models, we use the SAME evaluation definition
# (same dataset + scorers) for all models. This ensures fair comparison and allows
# everyone in the workshop to see aggregated results. Each evaluation run gets a
# unique ID automatically, but the evaluation definition stays consistent.


# %%
# Create a single evaluation definition that will be used for all models
evaluation = Evaluation(
    name="email_analyzer_comparison",  # Same eval for all models
    dataset=support_dataset,
    scorers=[name_accuracy, sentiment_accuracy, extraction_quality],
)


async def compare_models(models: list[Model]) -> dict[str, Any]:
    """Run A/B comparison of multiple models."""
    results = {}

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
    compare_models([basic_model, detailed_model, balanced_model])
)
print("\n🎉 Comparison complete! View the results in the Weave UI.")


# %% [markdown]
# ### 🎯 Part 2.6: Leaderboard Competition
#
# Now it's time for a friendly competition! We'll use Weave's leaderboard feature to track
# who can create the best email analysis model. Everyone will use the same evaluation
# (`email_analyzer_comparison`) so results are directly comparable.
#
# **Your challenge**: Improve the prompt/model to get the highest scores on:
# - Name accuracy
# - Sentiment accuracy
# - Overall extraction quality
#
# **Leaderboard Setup**: We can create a leaderboard to track all submissions using the
# same evaluation definition. This ensures fair comparison across all participants.

# %%
from weave.flow import leaderboard
from weave.trace.ref_util import get_ref

# Create a leaderboard for the workshop competition
leaderboard_spec = leaderboard.Leaderboard(
    name="Email Analysis Workshop Competition",
    description="""
This leaderboard tracks the best email analysis models from workshop participants.

### Scoring Metrics

1. **Name Accuracy**: Fraction of emails where the customer name was correctly extracted
2. **Sentiment Accuracy**: Fraction of emails where the sentiment was correctly identified  
3. **Extraction Quality**: Overall quality score for extracting all required fields

### Tips for Success
- Focus on clear, specific prompts
- Handle edge cases (names in signatures, multiple products mentioned)
- Consider the context and nuances in sentiment analysis
""",
    columns=[
        leaderboard.LeaderboardColumn(
            evaluation_object_ref=get_ref(evaluation).uri(),
            scorer_name="name_accuracy",
            summary_metric_path="score.mean",
        ),
        leaderboard.LeaderboardColumn(
            evaluation_object_ref=get_ref(evaluation).uri(),
            scorer_name="sentiment_accuracy",
            summary_metric_path="score.mean",
        ),
        leaderboard.LeaderboardColumn(
            evaluation_object_ref=get_ref(evaluation).uri(),
            scorer_name="extraction_quality",
            summary_metric_path="score.mean",
        ),
    ],
)

# Publish the leaderboard
leaderboard_ref = weave.publish(leaderboard_spec)
print("🏆 Leaderboard created! View it in the Weave UI")
print(f"📊 All participants will use the same evaluation: {evaluation.name}")

# %% [markdown]
# ### 🚀 Your Turn: Create Your Best Model
#
# **Instructions:**
# 1. Modify the system prompt below to improve performance
# 2. Run the evaluation to see your scores
# 3. Iterate and improve!
# 4. Your results will automatically appear on the leaderboard
#
# **Pro Tips:**
# - Study the challenging examples in the dataset
# - Be specific about edge cases (signatures, multiple names, etc.)
# - Consider temperature settings (lower = more consistent)


# %%
class MyEmailModel(Model):
    """Your custom email analysis model - modify the prompt to improve performance!"""

    # TODO: Modify this prompt to get better results!
    system_prompt: str = """You are an expert customer support analyst. Extract information from emails:

1. Customer name: The person WRITING the email (check signatures and sign-offs)
2. Product: The specific product mentioned that has issues
3. Issue: Brief description of the problem
4. Sentiment: positive, negative, or neutral based on overall tone

Be careful with edge cases and ambiguous information."""

    temperature: float = 0.1  # You can adjust this too!

    @weave.op
    def predict(self, email: str) -> CustomerEmail:
        client = OpenAI()

        response = client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": f"Analyze this email:\n\n{email}"},
            ],
            response_format=CustomerEmail,
            temperature=self.temperature,
        )

        return response.choices[0].message.parsed


# Create your model instance
my_model = MyEmailModel()

# Test on a single example first
test_result = my_model.predict(eval_examples[0]["email"])
print("🧪 Test result:")
print(f"  Name: {test_result.customer_name}")
print(f"  Product: {test_result.product}")
print(f"  Sentiment: {test_result.sentiment}")

# %% [markdown]
# ### 🏃 Submit to Leaderboard
#
# Run this cell to evaluate your model and submit to the leaderboard!

# %%
# Run your model on the full evaluation
print("🏃 Running your model on the competition dataset...")
print("⏱️  This may take a minute...")

my_results = asyncio.run(
    evaluation.evaluate(
        my_model,
        __weave={
            "display_name": "email_analyzer_comparison - MyModel"
        },  # You can customize this name
    )
)

print("✅ Evaluation complete!")
print("🏆 Check the leaderboard in the Weave UI to see how you rank!")
print(
    "💡 Tip: Iterate on your prompt above and run this cell again to improve your score"
)

# %% [markdown]
# ## Summary
#
# You've learned how to use Weave's evaluation framework:
#
# - ✅ **Dataset Creation**: Built challenging evaluation datasets
# - ✅ **Custom Scorers**: Created scoring functions for specific metrics
# - ✅ **Pre-built Scorers**: Used Weave's built-in evaluation tools
# - ✅ **Pairwise Evaluation**: Compared models head-to-head
# - ✅ **Model Comparison**: Ran systematic A/B tests
# - ✅ **Leaderboards**: Tracked performance across participants
#
# **Next Steps:**
# - Continue to Part 3: Production Monitoring
# - Experiment with different prompts and models
# - Try the evaluation framework on your own use cases
