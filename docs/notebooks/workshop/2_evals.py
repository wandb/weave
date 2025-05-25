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
import os
from datetime import datetime
from getpass import getpass
from typing import Any

from openai import OpenAI
from pydantic import BaseModel, Field

import weave
from weave import Dataset, Evaluation, EvaluationLogger, Model

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
    trails=3,
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
try:
    from weave.scorers import (
        EmbeddingSimilarityScorer,
        OpenAIModerationScorer,
        PydanticScorer,
        ValidJSONScorer,
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
# ### 📝 Part 2.2: Pairwise Scoring
# TODO: (New Cell) - Let's add a cell specifically to showcase pairwise scoring (Human to link to content here.)

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
# ### 🎯 Part 2.6: Leaderboard Competition
# TODO: Interactive challenge time. (leaderboard competition)
# Now we are going to see who can creat the best model
# TODO: setup the leaderboard (either interactively in the UI, or add a cell below)
# Invite students to iterate on the prompt / model to get higher performance (which we will track in the leaderboard!)
