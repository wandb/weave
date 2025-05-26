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
#
# OpenAI API key can be found at https://platform.openai.com/api-keys

# %%
# Install dependencies
# %pip install wandb weave openai pydantic nest_asyncio 'pydantic[email]' set-env-colab-kaggle-dotenv -qqq

import asyncio
import os
from datetime import datetime
from typing import Any

from openai import OpenAI
from pydantic import BaseModel, Field
from set_env import set_env

import weave
from weave import Dataset, Evaluation, EvaluationLogger, Model

# Setup API keys
os.environ["OPENAI_API_KEY"] = set_env("OPENAI_API_KEY")

# Initialize Weave
weave_client = weave.init("weave-workshop")

# %% [markdown]
# ## 📊 Part 2: Building Evaluations
#
# Let's evaluate our email analyzer using Weave's evaluation framework with a challenging dataset.
#
# **Understanding Weave's Evaluation Data Model:**
# 1. An **evaluation** is the pairing of a dataset and a set of scorers
# 2. An **evaluation run** is the result of running an evaluation against a specific model
# 3. Within an evaluation run, there are **predict_and_score** blocks for each dataset row
# 4. Scores are stored in the predict_and_score output and on the prediction call


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
    # Challenging examples - names buried in complex contexts
    {
        "email": "FWD: Issue Report\n\nOriginal sender: tech@company.com\nSubject: Critical Bug\n\nHi team, forwarding this from our client. The customer (Sarah Mitchell) reported that DataProcessor-Pro v2.5 crashes during export. Please investigate ASAP.\n\n—Forwarded by Alex Thompson, Support Lead",
        "expected_name": "Alex Thompson",  # The forwarder, NOT Sarah Mitchell
        "expected_product": "DataProcessor-Pro v2.5",
        "expected_sentiment": "negative",  # Urgent/critical issue
    },
    {
        "email": "RE: Meeting with Dr. Chen\n\nJust to clarify what Alice mentioned in our call - the AI-Assistant tool works great for basic tasks but struggles with complex queries. Overall satisfied though.\n\nBest,\nMichael Rodriguez\nProduct Manager",
        "expected_name": "Michael Rodriguez",  # NOT Dr. Chen or Alice
        "expected_product": "AI-Assistant",
        "expected_sentiment": "positive",  # Overall satisfied despite limitations
    },
    # Extremely challenging - multiple people, products, and misdirection
    {
        "email": "Update from Jane in accounting: CloudSync Plus deployment went smoothly. However, I'm personally experiencing severe delays with the Enterprise Sync Module during peak hours. This is becoming a bottleneck for our quarterly reports.\n\nUrgent attention needed.\n\nRegards,\nDr. Patricia Williams\nCFO",
        "expected_name": "Dr. Patricia Williams",  # NOT Jane
        "expected_product": "Enterprise Sync Module",  # NOT CloudSync Plus
        "expected_sentiment": "negative",  # Urgent attention needed, bottleneck
    },
    {
        "email": "CC: Bob Wilson, Sarah Chen\n\nTeam update: Wilson mentioned SmartHub connectivity issues last week. However, my main concern is with the NetworkBridge Pro v4.2 - it's completely unreliable during video conferences. This is embarrassing in client meetings.\n\nPlease escalate immediately.\n\nDr. Amanda Foster\nSenior Manager, Tech Solutions Inc",
        "expected_name": "Dr. Amanda Foster",  # NOT Bob Wilson or Sarah Chen
        "expected_product": "NetworkBridge Pro v4.2",  # NOT SmartHub
        "expected_sentiment": "negative",  # Embarrassing, unreliable, escalate
    },
    {
        "email": "Following up on Sarah's ticket #4567. She mentioned WorkflowMax stability issues, but that's resolved now. My current problem is with DataSync Enterprise - it's corrupting files during overnight backups. This is a disaster for our compliance audits.\n\nMike O'Brien\nCEO, DataCorp",
        "expected_name": "Mike O'Brien",  # NOT Sarah
        "expected_product": "DataSync Enterprise",  # NOT WorkflowMax
        "expected_sentiment": "negative",  # Disaster, corrupting files
    },
    # Extremely hard - sarcasm and hidden sentiment
    {
        "email": "Wow, the ProSuite 3000 update is just *fantastic*! 🙄 Now nothing works and I've lost 3 hours of work. Really appreciate the 'improved stability' you promised.\n\nThanks for nothing,\nZhang Wei\nFrustrated Developer",
        "expected_name": "Zhang Wei",
        "expected_product": "ProSuite 3000",
        "expected_sentiment": "negative",  # Heavy sarcasm = very negative
    },
    {
        "email": "CONFIDENTIAL - Internal Use Only\n\nRE: Ticket #1234 - CloudVault Investigation\n\nPer our conversation, María García from Legal called to discuss the data breach. While she's satisfied with our response, I'm deeply concerned about CloudVault's encryption protocols. This could expose us to regulatory violations.\n\nRequesting immediate security audit.\n\nConfidentially yours,\nDr. Rebecca Martinez\nChief Security Officer",
        "expected_name": "Dr. Rebecca Martinez",  # NOT María García
        "expected_product": "CloudVault",
        "expected_sentiment": "negative",  # Deeply concerned, regulatory violations
    },
    {
        "email": "Jennifer from IT will handle the technical details, but I need to address the elephant in the room. DataMiner Pro's new 'AI-powered insights' feature is producing completely nonsensical results. Our quarterly projections are now worthless.\n\nThis is unacceptable.\n\n—Dr. Rajesh Patel\nHead of Analytics",
        "expected_name": "Dr. Rajesh Patel",  # NOT Jennifer
        "expected_product": "DataMiner Pro",
        "expected_sentiment": "negative",  # Unacceptable, worthless results
    },
    # Extremely challenging - multiple layers of misdirection
    {
        "email": "Johnson's team loves your software. Smith specifically mentioned how CloudSync transformed their workflow. However, I must report that our implementation of QuantumDB has been an absolute catastrophe. Three weeks of downtime and counting.\n\nDemanding immediate executive intervention.\n\nJames Brown\nCTO, Enterprise Solutions",
        "expected_name": "James Brown",  # NOT Johnson or Smith
        "expected_product": "QuantumDB",  # NOT CloudSync (which others love)
        "expected_sentiment": "negative",  # Absolute catastrophe, demanding intervention
    },
    {
        "email": "Stockholm office feedback: Anna's team reports InvoiceGen crashes frequently during month-end processing. While they've found workarounds, I'm concerned about the reliability for our IPO audit requirements. This could jeopardize our public offering timeline.\n\nEscalating to board level.\n\nLars Eriksson\nCFO, Nordic Enterprises",
        "expected_name": "Lars Eriksson",  # NOT Anna
        "expected_product": "InvoiceGen",
        "expected_sentiment": "negative",  # Jeopardize IPO, board escalation
    },
    # Deceptive context and buried information
    {
        "email": "Thompson's case update attached. Regarding Lee's WorkStation Pro error 0x80004005 - previous tech support was inadequate. However, my real issue is with the CloudRenderer Enterprise license server. It's rejecting valid certificates and blocking our entire 3D animation pipeline.\n\nProduction has been halted for 48 hours.\n\nEmergency response required.\n\nDavid Kim\nVP of Production",
        "expected_name": "David Kim",  # NOT Thompson or Lee
        "expected_product": "CloudRenderer Enterprise",  # NOT WorkStation Pro
        "expected_sentiment": "negative",  # Production halted, emergency
    },
    {
        "email": "Emma from support was incredibly helpful during our integration call. She walked us through the ReportBuilder setup perfectly. Unfortunately, I must escalate a critical performance issue - our quarterly board reports are timing out after 6+ hours. This is completely unacceptable for executive presentations.\n\nImmediate optimization required.\n\nSamantha Park\nCTO, DataFlow Corp",
        "expected_name": "Samantha Park",  # NOT Emma
        "expected_product": "ReportBuilder",
        "expected_sentiment": "negative",  # Critical issue, unacceptable, immediate action needed
    },
    {
        "email": "URGENT: Customer escalation\n\nPierre-Alexandre Dubois called regarding API-Gateway documentation gaps. While he praised the core functionality, I'm writing to report a showstopper bug: the authentication module is leaking memory and crashing our production servers every 4-6 hours.\n\nThis is a P0 incident affecting 50,000+ users.\n\nTechnical Lead: Maria Santos\nIncident Commander",
        "expected_name": "Maria Santos",  # NOT Pierre-Alexandre Dubois
        "expected_product": "API-Gateway",
        "expected_sentiment": "negative",  # Showstopper bug, P0 incident, affecting users
    },
    {
        "email": "Your tech support team's response time is absolutely abysmal - 72 hours for a P1 ticket! However, I must acknowledge that ProductX's core functionality exceeds expectations. But this support experience has damaged our relationship irreparably.\n\nConsidering contract termination.\n\nFrancis O'Sullivan\nDirector of IT Operations",
        "expected_name": "Francis O'Sullivan",
        "expected_product": "ProductX",
        "expected_sentiment": "negative",  # Abysmal support, damaged relationship, considering termination
    },
    # Products with human names - extremely tricky
    {
        "email": "Maxwell's performance has degraded significantly since the last update. Li Chen from our QA team mentioned similar issues, but I'm the one filing this complaint. The software crashes every 30 minutes during peak usage.\n\nThis is affecting our entire customer service operation.\n\nDr. Jennifer Walsh\nOperations Director",
        "expected_name": "Dr. Jennifer Walsh",  # NOT Li Chen
        "expected_product": "Maxwell",  # Maxwell is the product, not a person
        "expected_sentiment": "negative",  # Degraded performance, crashes, affecting operations
    },
    {
        "email": "Gordon from procurement asked me to follow up on the Morgan Analytics Suite deployment. While the initial setup went smoothly, I'm experiencing severe data corruption issues during large dataset processing. Our financial models are now unreliable.\n\nThis threatens our audit compliance.\n\nYuki Tanaka\nSenior Data Analyst",
        "expected_name": "Yuki Tanaka",  # NOT Gordon
        "expected_product": "Morgan Analytics Suite",
        "expected_sentiment": "negative",  # Severe corruption, unreliable, threatens compliance
    },
    # Extreme sarcasm and subtle negativity
    {
        "email": "DataFlow Pro delivers exactly the 'enterprise-grade reliability' your marketing promised. 🙄 Another classic example of your company's commitment to quality. Three system crashes this morning alone.\n\nTruly impressive consistency.\n\nJoão Silva\nProduct Manager, TechFlow Solutions",
        "expected_name": "João Silva",
        "expected_product": "DataFlow Pro",
        "expected_sentiment": "negative",  # Heavy sarcasm throughout, system crashes
    },
    {
        "email": "Kim mentioned ChromaEdit in our team meeting. Honestly, I couldn't care less about photo editing tools right now. My priority is the VideoProcessor Enterprise license that's blocking our entire creative pipeline. Deadlines are approaching fast.\n\nNeed resolution ASAP.\n\nAlex Thompson\nCreative Director",
        "expected_name": "Alex Thompson",  # NOT Kim
        "expected_product": "VideoProcessor Enterprise",  # NOT ChromaEdit
        "expected_sentiment": "negative",  # Blocking pipeline, deadlines, need ASAP resolution
    },
    # Complex product migration scenarios
    {
        "email": "Our TaskMaster to ProjectPro migration was supposed to improve efficiency. Instead, ProjectPro's gantt chart module is corrupting our project timelines. Anne-Marie from the PMO flagged this, but I'm the one dealing with angry stakeholders.\n\nThis is a complete disaster.\n\nRobert Chen\nVP of Engineering",
        "expected_name": "Robert Chen",  # NOT Anne-Marie Rousseau
        "expected_product": "ProjectPro",  # The problematic one
        "expected_sentiment": "negative",  # Complete disaster, angry stakeholders
    },
    {
        "email": "Muhammad's team loves VideoEdit and PhotoEdit for basic tasks. However, I need to escalate a critical issue with AudioEdit Pro - it's introducing artifacts in our podcast production. Our sponsors are threatening to pull contracts due to audio quality issues.\n\nThis is jeopardizing our revenue stream.\n\nSarah Williams\nPodcast Production Manager",
        "expected_name": "Sarah Williams",  # NOT Muhammad
        "expected_product": "AudioEdit Pro",  # The problematic one
        "expected_sentiment": "negative",  # Critical issue, sponsors threatening, jeopardizing revenue
    },
    # Extremely challenging - informal language with serious issues
    {
        "email": "Dmitri from DevOps mentioned SystemMonitor issues last week. Whatever, that's old news. My current nightmare is CloudWatch Enterprise - it's missing 40% of our server alerts. We've had two undetected outages this month.\n\nThis is a security and compliance disaster.\n\nTechnical Director: Alexandra Petrov\nxXx_CloudMaster_xXx",
        "expected_name": "Alexandra Petrov",  # NOT Dmitri, real name in signature
        "expected_product": "CloudWatch Enterprise",  # NOT SystemMonitor
        "expected_sentiment": "negative",  # Nightmare, missing alerts, disaster
    },
    {
        "email": "¡Hola! Carlos Méndez from Finance mentioned FinanceTracker pricing concerns. However, I'm writing about a catastrophic bug in our CryptoTrader Pro implementation. It's executing trades without authorization, resulting in $50K+ losses.\n\nLegal action is being considered.\n\nGracias por su atención urgente,\nDr. Isabella Rodriguez\nChief Financial Officer",
        "expected_name": "Dr. Isabella Rodriguez",  # NOT Carlos Méndez
        "expected_product": "CryptoTrader Pro",  # NOT FinanceTracker
        "expected_sentiment": "negative",  # Catastrophic bug, $50K losses, legal action
    },
    {
        "email": "Re: Jackson's Scheduler App complaint\n\nWhile Jackson's team finds the basic scheduling adequate, I must report a critical flaw in TaskFlow Enterprise. The automated workflow engine is creating infinite loops, consuming 100% CPU and crashing our production servers.\n\nImmediate hotfix required.\n\nPriya Sharma\nHead of IT Infrastructure",
        "expected_name": "Priya Sharma",  # NOT Jackson
        "expected_product": "TaskFlow Enterprise",  # NOT Scheduler App
        "expected_sentiment": "negative",  # Critical flaw, crashing servers, immediate hotfix needed
    },
    {
        "email": "Following up on Jennifer Chen's CloudBackup Pro ticket. While her backup issues are resolved, I'm escalating a more serious problem with DataVault Enterprise. The encryption keys are being corrupted during automated rotations, making 30% of our backups unrecoverable.\n\nThis violates our disaster recovery SLA.\n\nDavid Kim\nIT Operations Manager",
        "expected_name": "David Kim",  # NOT Jennifer Chen
        "expected_product": "DataVault Enterprise",  # NOT CloudBackup Pro
        "expected_sentiment": "negative",  # Serious problem, unrecoverable backups, SLA violation
    },
    {
        "email": "Singh from warehouse called about InventoryMaster earlier. That's handled. My crisis is with SupplyChain Pro - it's double-ordering everything! We now have $2M in excess inventory and our cash flow is destroyed.\n\n😡😡😡 EMERGENCY BOARD MEETING CALLED 😭😭😭\n\nCFO: Patricia Williams\n//SupplyChainNightmare",
        "expected_name": "Patricia Williams",  # NOT Singh
        "expected_product": "SupplyChain Pro",  # NOT InventoryMaster
        "expected_sentiment": "negative",  # Crisis, $2M excess, cash flow destroyed, emergency meeting
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
def product_accuracy(expected_product: str, output: CustomerEmail) -> dict[str, Any]:
    """Check if the extracted product matches."""
    is_correct = expected_product.lower() == output.product.lower()
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


# 🚀 Run the evaluation
evaluation = Evaluation(
    dataset=support_dataset,
    scorers=[name_accuracy, product_accuracy, sentiment_accuracy, extraction_quality],
    trials=3,  # Run each example 3 times to check consistency
)

# For notebooks, use nest_asyncio to handle async properly
import nest_asyncio

nest_asyncio.apply()
eval_results = asyncio.run(evaluation.evaluate(analyze_customer_email))
print("✅ Evaluation complete! Check the Weave UI for detailed results.")

# %% [markdown]
# ### 🎯 Part 2.1: Pre-built Scorers
#
# Weave provides many pre-built scorers for common evaluation tasks.
# No need to reinvent the wheel for standard metrics!
#
# **Note**: To use pre-built scorers, install with: `pip install weave[scorers]`

# %%
# %pip install 'weave[scorers]' -qqq

# Import pre-built scorers
from weave.scorers import (
    EmbeddingSimilarityScorer,
    PydanticScorer,
    ValidJSONScorer,
)

# Example 1: ValidJSONScorer - Check if output is valid JSON
json_scorer = ValidJSONScorer()

print("🎯 Example 1: ValidJSONScorer")
# Test with valid JSON
valid_json = '{"name": "John Doe", "age": 30, "email": "john@example.com"}'
json_result = json_scorer.score(output=valid_json)
print(f"  Valid JSON: {json_result['json_valid']}")

# Test with invalid JSON
invalid_json = (
    '{"name": "Jane Doe", "age": 25, "email"'  # Missing closing quote and brace
)
invalid_result = json_scorer.score(output=invalid_json)
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
pydantic_result = pydantic_scorer.score(output=valid_data)
print(f"  Valid schema: {pydantic_result['valid_pydantic']}")

# Test with invalid data
invalid_data = '{"name": "Bob", "age": "twenty-five", "email": "not-an-email"}'
invalid_pydantic_result = pydantic_scorer.score(output=invalid_data)
print(f"  Invalid schema: {invalid_pydantic_result['valid_pydantic']}")

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

# %% [markdown]
# ### 📝 Part 2.2: Pairwise Evaluation
#
# Compare outputs from two models by ranking them relative to each other.
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
                {"role": "system", "content": "Extract."},
                {"role": "user", "content": email},
            ],
            response_format=CustomerEmail,
            temperature=0.7,  # Higher temperature for more variation
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
                    - Sentiment: Overall emotional tone (and customer perception based on thread)""",
                },
                {"role": "user", "content": email},
            ],
            response_format=CustomerEmail,
            temperature=0.1,  # Lower temperature for consistency
        )
        return response.choices[0].message.parsed


class EmailPreferenceScorer(weave.Scorer):
    """Compare two email analysis models and determine which performs better."""

    other_model: Model

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
        expected_product: str,
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

        # Check product accuracy
        if output.product.lower() == expected_product.lower():
            primary_score += 1
        if other_output.product.lower() == expected_product.lower():
            other_score += 1

        # Check sentiment accuracy
        if output.sentiment.lower() == expected_sentiment.lower():
            primary_score += 1
        if other_output.sentiment.lower() == expected_sentiment.lower():
            other_score += 1

        primary_is_better = primary_score > other_score

        if primary_score == other_score:
            reason = f"Tie: Both models scored {primary_score}/3"
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
        "expected_product": "ProWidget 3000",
        "expected_sentiment": "negative",
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
# ### 📝 Part 2.3: EvaluationLogger
#
# The `EvaluationLogger` provides flexible evaluation logging for custom workflows.
# This is perfect when you don't have all your data upfront or want more control.
#
# **Important**: Since EvaluationLogger doesn't use Model/Dataset objects, the `model`
# and `dataset` parameters are crucial for identification.

# %%
# Create evaluation logger with rich metadata
# Model can use dictionaries for richer identification (recommended!)
eval_logger = EvaluationLogger(
    model={
        "name": "email_analyzer",
        "version": "v1.2",
        "llm": "gpt-3.5-turbo",
        "temperature": 0.7,
        "prompt_version": "2024-01",
    },
    dataset="support_emails_2024Q1",  # Dataset must be string
)

print("📊 Using EvaluationLogger with rich metadata...")

# Process examples with custom logging - more control than standard Evaluation
for i, example in enumerate(eval_examples[:3]):  # First 3 for demo
    try:
        output = analyze_customer_email(example["email"])

        # Log the prediction
        pred_logger = eval_logger.log_prediction(
            inputs={"email": example["email"]}, output=output.model_dump()
        )

        # Log multiple scores for this prediction
        # Check name accuracy
        name_match = example["expected_name"].lower() == output.customer_name.lower()
        pred_logger.log_score(scorer="name_accuracy", score=1.0 if name_match else 0.0)

        # Check product accuracy
        product_match = example["expected_product"].lower() == output.product.lower()
        pred_logger.log_score(
            scorer="product_accuracy", score=1.0 if product_match else 0.0
        )

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
        pred_logger = eval_logger.log_prediction(
            inputs={"email": example["email"]}, output={"error": str(e)}
        )
        pred_logger.log_score(scorer="success", score=0.0)
        pred_logger.finish()

# Log summary statistics
eval_logger.log_summary(
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
# Compare different approaches using Weave's Model class with varying quality levels.
# We'll create models with different quality to see clear differences.


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
    system_prompt="Extract stuff, get it wrong sometimes.",
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
# everyone in the workshop to see aggregated results.

# %%
# Create a single evaluation definition that will be used for all models
evaluation = Evaluation(
    name="email_analyzer_comparison",  # Same eval for all models
    dataset=support_dataset,
    scorers=[name_accuracy, sentiment_accuracy, product_accuracy, extraction_quality],
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
2. **Product Accuracy**: Fraction of emails where the product was correctly identified
3. **Sentiment Accuracy**: Fraction of emails where the sentiment was correctly identified  
4. **Extraction Quality**: Overall quality score for extracting all required fields

### Tips for Success
- Focus on clear, specific prompts
- Handle edge cases (names in signatures, multiple products mentioned)
- Distinguish between the actual problematic product vs. other products mentioned
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
            scorer_name="product_accuracy",
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
my_model = MyEmailModel(name="NAME_YOUR_MODEL")

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
        },  # You can customize this name  (if you want)
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
#
# **Key Takeaways:**
# - Systematic evaluation reveals model strengths and weaknesses
# - Challenging datasets expose edge cases and failure modes
# - Leaderboards encourage continuous improvement and collaboration
# - Weave makes it easy to compare models and track progress over time
