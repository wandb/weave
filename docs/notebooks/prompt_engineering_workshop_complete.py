# %% [markdown]
# # 🚀 Prompt Engineering Workshop with Weave
#
# Welcome to this hands-on workshop where we'll explore prompt engineering techniques while learning how Weave can help us build better LLM applications!
#
# ## What we'll cover:
# 1. **Basic Prompt Engineering** - Extracting structured data from unstructured text
# 2. **Prompt Iteration** - Using Weave to track and compare different prompts
# 3. **Few-shot Learning** - Improving results with examples
# 4. **Evaluation** - Building datasets and scoring functions with Weave's evaluation framework
# 5. **Advanced Techniques** - Chain of thought, role playing, and more
#
# ## Our Use Case: Customer Support Triage 📧
# We'll build a system that extracts key information from customer support emails to help route them efficiently.

# %%
# Install dependencies
# %pip install weave openai pydantic -qqq

# %%
# Setup
import asyncio
import json
import os
from getpass import getpass

from openai import OpenAI
from pydantic import BaseModel, Field

import weave
from weave import Dataset, Evaluation, Model

# Get OpenAI API key
if not os.environ.get("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = getpass("Enter your OpenAI API key: ")

# Initialize Weave - this will track all our experiments!
weave.init("prompt_engineering_workshop")

# %% [markdown]
# ## Part 1: Basic Extraction 🎯
#
# Let's start with a simple task: extracting customer information from support emails.


# %%
# Define our data model
class MessageProperties(BaseModel):
    customer_name: str = Field(description="The name of the customer")
    product_model: str = Field(description="The product model mentioned")
    issue_description: str = Field(description="A brief description of the issue")


# Sample emails
sample_emails = [
    "Hello, My name is John Doe. My XPhone 12 Pro keeps randomly shutting off mid-call. Please help!",
    "Hi support, This is Jane Smith. I bought an AeroWatch V2 last week. The strap broke after one day.",
    "My SmartTV X500 won't connect to WiFi anymore. It was working fine yesterday. - Bob Wilson",
]


# %%
@weave.op
def extract_properties_v1(message: str) -> MessageProperties:
    """Version 1: Basic extraction with minimal prompting"""
    system_prompt = """Extract customer information from support emails."""

    user_prompt = f"""Extract the customer name, product model, and issue description from this email:

{message}

Return as JSON."""

    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
    )

    try:
        parsed = json.loads(response.choices[0].message.content)
        return MessageProperties(**parsed)
    except Exception as e:
        print(f"Error parsing response: {e}")
        print(f"Raw response: {response.choices[0].message.content}")
        raise


# Test it out!
result = extract_properties_v1(sample_emails[0])
print(f"Customer: {result.customer_name}")
print(f"Product: {result.product_model}")
print(f"Issue: {result.issue_description}")

# %% [markdown]
# ## Part 2: Improving with Better Prompts 🔧
#
# Let's iterate on our prompt to make it more robust and specific.


# %%
@weave.op
def extract_properties_v2(message: str) -> MessageProperties:
    """Version 2: More detailed instructions"""
    system_prompt = """You are an expert at analyzing customer support emails.
    Your task is to extract key information accurately and consistently.
    Always return valid JSON with the exact field names specified."""

    user_prompt = f"""Extract the following information from this customer support email:

1. customer_name: The full name of the customer (if not explicitly stated, look for signatures)
2. product_model: The exact product model mentioned (include version numbers)
3. issue_description: A concise summary of the problem (max 100 characters)

Email:
{message}

Return ONLY a JSON object with these exact field names."""

    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,  # Lower temperature for more consistent outputs
    )

    parsed = json.loads(response.choices[0].message.content)
    return MessageProperties(**parsed)


# Compare versions
print("Testing both versions on the same email:\n")
test_email = sample_emails[2]
print(f"Email: {test_email}\n")

print("Version 1:")
v1_result = extract_properties_v1(test_email)
print(v1_result.model_dump_json(indent=2))

print("\nVersion 2:")
v2_result = extract_properties_v2(test_email)
print(v2_result.model_dump_json(indent=2))

# %% [markdown]
# ## Part 3: Few-Shot Learning 📚
#
# Let's add examples to help the model understand exactly what we want.

# %%
# Define few-shot examples
few_shot_examples = [
    {
        "email": "Hi, I'm Sarah Johnson and my AirPods Pro 2 won't charge anymore. The case shows no lights.",
        "extracted": {
            "customer_name": "Sarah Johnson",
            "product_model": "AirPods Pro 2",
            "issue_description": "AirPods won't charge, case shows no lights",
        },
    },
    {
        "email": "This laptop is terrible! The screen keeps flickering. Model: ThinkPad X1 Carbon Gen 9. -Mike Chen",
        "extracted": {
            "customer_name": "Mike Chen",
            "product_model": "ThinkPad X1 Carbon Gen 9",
            "issue_description": "Screen keeps flickering",
        },
    },
]


@weave.op
def extract_properties_v3_fewshot(message: str) -> MessageProperties:
    """Version 3: Few-shot learning with examples"""
    system_prompt = """You are an expert at extracting information from customer support emails.
    Follow the examples provided to ensure consistent formatting."""

    # Build few-shot prompt
    examples_text = "Here are some examples:\n\n"
    for ex in few_shot_examples:
        examples_text += f"Email: {ex['email']}\n"
        examples_text += f"Extracted: {json.dumps(ex['extracted'], indent=2)}\n\n"

    user_prompt = f"""{examples_text}
Now extract information from this email:

Email: {message}
Extracted:"""

    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
    )

    parsed = json.loads(response.choices[0].message.content)
    return MessageProperties(**parsed)


# Test few-shot version
print("Few-shot learning result:")
v3_result = extract_properties_v3_fewshot(sample_emails[1])
print(v3_result.model_dump_json(indent=2))

# %% [markdown]
# ## Part 4: Building Evaluations with Weave 📊
#
# Now let's use Weave's evaluation framework to systematically measure our improvements.
# We'll explore two approaches: the structured `Evaluation` class and the flexible `EvaluationLogger`.

# %%
# Create evaluation dataset
eval_examples = [
    {
        "email": "Hello support team, I'm John Doe. My XPhone 12 Pro keeps randomly shutting off during calls. This is really frustrating!",
        "expected_customer_name": "John Doe",
        "expected_product_model": "XPhone 12 Pro",
        "expected_issue_description": "Phone randomly shuts off during calls",
    },
    {
        "email": "My new AeroWatch V2's strap completely fell apart after just one day of use. This is unacceptable! - Jane Smith",
        "expected_customer_name": "Jane Smith",
        "expected_product_model": "AeroWatch V2",
        "expected_issue_description": "Watch strap fell apart after one day",
    },
    {
        "email": "Hi, Bob Wilson here. The SmartTV X500 I bought last month suddenly stopped connecting to my WiFi network.",
        "expected_customer_name": "Bob Wilson",
        "expected_product_model": "SmartTV X500",
        "expected_issue_description": "TV won't connect to WiFi",
    },
    {
        "email": "URGENT: Gaming Console Z crashed and won't turn back on. Blue light flashes 3 times. -Alex Kumar",
        "expected_customer_name": "Alex Kumar",
        "expected_product_model": "Gaming Console Z",
        "expected_issue_description": "Console crashed, blue light flashes 3 times",
    },
    {
        "email": "Lisa Park writing about my EcoVac R10 robot vacuum. It keeps getting stuck under furniture even though it's supposed to detect obstacles.",
        "expected_customer_name": "Lisa Park",
        "expected_product_model": "EcoVac R10",
        "expected_issue_description": "Robot vacuum gets stuck under furniture",
    },
]

# Create a Weave Dataset
support_emails_dataset = Dataset(name="support_emails", rows=eval_examples)

# %% [markdown]
# ### Define Scoring Functions
#
# Weave scorers take the `output` from your function and any other fields from your dataset examples.


# %%
# Define scoring functions
@weave.op
def exact_match_scorer(
    expected_customer_name: str,
    expected_product_model: str,
    expected_issue_description: str,
    output: MessageProperties,
) -> dict:
    """Score based on exact field matches"""
    scores = {
        "customer_name_match": int(
            expected_customer_name.lower().strip()
            == output.customer_name.lower().strip()
        ),
        "product_model_match": int(
            expected_product_model.lower().strip()
            == output.product_model.lower().strip()
        ),
        "issue_description_match": int(
            expected_issue_description.lower().strip()
            == output.issue_description.lower().strip()
        ),
    }

    scores["all_fields_correct"] = int(all(scores.values()))
    return scores


@weave.op
def similarity_scorer(
    expected_customer_name: str,
    expected_product_model: str,
    expected_issue_description: str,
    output: MessageProperties,
) -> dict:
    """Score based on string similarity"""
    from difflib import SequenceMatcher

    scores = {}

    # Calculate similarity for each field
    scores["customer_name_similarity"] = SequenceMatcher(
        None, expected_customer_name.lower(), output.customer_name.lower()
    ).ratio()

    scores["product_model_similarity"] = SequenceMatcher(
        None, expected_product_model.lower(), output.product_model.lower()
    ).ratio()

    scores["issue_similarity"] = SequenceMatcher(
        None, expected_issue_description.lower(), output.issue_description.lower()
    ).ratio()

    scores["avg_similarity"] = sum(scores.values()) / len(scores)
    return scores


# %% [markdown]
# ### Method 1: Using the Structured Evaluation Framework
#
# This approach is great when you have a predefined dataset and want to evaluate functions or models systematically.

# %%
# Create evaluation for our extraction functions
evaluation = Evaluation(
    dataset=support_emails_dataset,
    scorers=[exact_match_scorer, similarity_scorer],
    name="Email Extraction Evaluation",
)

# Evaluate each version
print("Evaluating Version 1 (Basic)...")
results_v1 = asyncio.run(evaluation.evaluate(extract_properties_v1))

print("\nEvaluating Version 2 (Improved)...")
results_v2 = asyncio.run(evaluation.evaluate(extract_properties_v2))

print("\nEvaluating Version 3 (Few-shot)...")
results_v3 = asyncio.run(evaluation.evaluate(extract_properties_v3_fewshot))

print(
    "\n✅ Evaluations complete! Check the Weave UI to see detailed results and comparisons."
)

# %% [markdown]
# ### Method 2: Using EvaluationLogger for Flexible Evaluation
#
# The `EvaluationLogger` is perfect for more complex workflows where you want to log evaluations incrementally.

# %%
from weave import EvaluationLogger


# Example of using EvaluationLogger for more flexible evaluation
@weave.op
def evaluate_with_logger(extractor_func, dataset_rows):
    """Demonstrate EvaluationLogger for incremental evaluation"""
    # Initialize the logger
    eval_logger = EvaluationLogger(
        model=extractor_func.__name__, dataset="support_emails"
    )

    # Process each example
    for row in dataset_rows:
        # Extract properties
        extracted = extractor_func(row["email"])

        # Log the prediction
        pred_logger = eval_logger.log_prediction(
            inputs={"email": row["email"]}, output=extracted.model_dump()
        )

        # Calculate and log exact match score
        exact_match = all(
            [
                row["expected_customer_name"].lower()
                == extracted.customer_name.lower(),
                row["expected_product_model"].lower()
                == extracted.product_model.lower(),
                row["expected_issue_description"].lower()
                == extracted.issue_description.lower(),
            ]
        )
        pred_logger.log_score(scorer="exact_match", score=exact_match)

        # Calculate and log field-level scores
        pred_logger.log_score(
            scorer="customer_name_correct",
            score=row["expected_customer_name"].lower()
            == extracted.customer_name.lower(),
        )
        pred_logger.log_score(
            scorer="product_model_correct",
            score=row["expected_product_model"].lower()
            == extracted.product_model.lower(),
        )

        # Finish logging for this prediction
        pred_logger.finish()

    # Log summary statistics
    eval_logger.log_summary(
        {"evaluation_method": "incremental_logger", "total_examples": len(dataset_rows)}
    )

    print(f"✅ Logged evaluation for {extractor_func.__name__}")


# Run logger-based evaluation for comparison
print("\nDemonstrating EvaluationLogger approach:")
evaluate_with_logger(extract_properties_v1, eval_examples)
evaluate_with_logger(extract_properties_v2, eval_examples)
evaluate_with_logger(extract_properties_v3_fewshot, eval_examples)

# %% [markdown]
# ## Part 5: Advanced Techniques with Models 🚀
#
# Let's explore advanced prompt engineering techniques using Weave's `Model` class for better parameter tracking.


# %%
# Define extraction models with different strategies
class ExtractionModel(Model):
    """Base model for email extraction with configurable prompts"""

    system_prompt: str
    user_prompt_template: str
    temperature: float = 0.1

    @weave.op
    def predict(self, email: str) -> MessageProperties:
        user_prompt = self.user_prompt_template.format(email=email)

        client = OpenAI()
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=self.temperature,
        )

        parsed = json.loads(response.choices[0].message.content)
        return MessageProperties(**parsed)


# Chain of Thought Model
cot_model = ExtractionModel(
    system_prompt="""You are an expert at analyzing customer support emails.
    Think step-by-step to extract information accurately.""",
    user_prompt_template="""Analyze this customer support email step by step:

Email: {email}

Follow these steps:
1. First, identify any names mentioned or signatures
2. Then, look for product names and model numbers
3. Finally, summarize the main issue in a concise way
4. Return your findings as JSON with fields: customer_name, product_model, issue_description

Think through each step before providing your final answer.""",
    temperature=0.1,
)

# Role-based Model
role_model = ExtractionModel(
    system_prompt="""You are a senior customer support specialist with 10 years of experience.
    You excel at quickly identifying key information from customer emails to route them to the right team.
    You're known for your accuracy and attention to detail.""",
    user_prompt_template="""As an experienced support specialist, extract the key information from this email:

{email}

Provide a JSON summary with:
- customer_name: The customer's full name
- product_model: The exact product model (be specific)
- issue_description: A clear, concise summary suitable for ticket routing""",
    temperature=0.1,
)

# %%
# Test advanced models
test_email = """Subject: HELP! Expensive headphones failing

I can't believe this is happening. I paid $350 for these SoundMax Pro Elite
headphones just 2 months ago and now the left ear cup has completely stopped
working. No sound at all! I've tried different devices, different cables,
even reset them multiple times. Nothing works.

This is completely unacceptable for such expensive headphones.

Frustrated customer,
Patricia Martinez"""

print("Testing advanced models on complex email:\n")
print(f"Email:\n{test_email}\n")
print("-" * 50)

# Test Chain of Thought model
print("\nChain of Thought approach:")
cot_result = cot_model.predict(test_email)
print(cot_result.model_dump_json(indent=2))

# Test Role-based model
print("\nRole-based approach:")
role_result = role_model.predict(test_email)
print(role_result.model_dump_json(indent=2))

# %%
# Evaluate the advanced models
print("\nEvaluating advanced models...")

print("Chain of Thought Model:")
cot_results = asyncio.run(evaluation.evaluate(cot_model))

print("\nRole-based Model:")
role_results = asyncio.run(evaluation.evaluate(role_model))

print("\n✅ Advanced model evaluations complete!")

# %% [markdown]
# ## Workshop Exercises 🎯
#
# Now it's your turn! Try these exercises to practice prompt engineering and evaluation:
#
# ### Exercise 1: Handle Edge Cases
# Create a new model that handles emails where:
# - The customer name is not explicitly stated
# - Multiple products are mentioned
# - The issue is vague or unclear
#
# ### Exercise 2: Add New Fields and Scorers
# Extend the extraction to include:
# - Urgency level (low/medium/high)
# - Customer sentiment (positive/neutral/negative)
# - Category (hardware/software/other)
#
# Then create custom scorers for these new fields!
#
# ### Exercise 3: Multi-language Support
# Create a model that can handle emails in different languages
#
# ### Exercise 4: Build Your Own Evaluation
# Create a comprehensive evaluation comparing all approaches using Weave's evaluation framework


# %%
# Exercise starter code
class ExtendedMessageProperties(BaseModel):
    customer_name: str
    product_model: str
    issue_description: str
    urgency_level: str = Field(description="low/medium/high")
    customer_sentiment: str = Field(description="positive/neutral/negative")
    category: str = Field(description="hardware/software/other")


class ExtendedExtractionModel(Model):
    """Your enhanced model here!"""

    system_prompt: str
    user_prompt_template: str

    @weave.op
    def predict(self, email: str) -> ExtendedMessageProperties:
        # TODO: Implement your enhanced extraction
        return ExtendedMessageProperties(
            customer_name="",
            product_model="",
            issue_description="",
            urgency_level="low",
            customer_sentiment="neutral",
            category="other",
        )


# Test with edge cases
edge_case_emails = [
    "Your product is terrible! Nothing works anymore!",  # No name, no specific product
    "Both my iPhone 14 and iPad Pro are having issues with the screen. Very urgent!",  # Multiple products
    "Something's wrong with my device. Please help.",  # Vague description
]


# Create a custom scorer for the new fields
@weave.op
def urgency_scorer(expected_urgency: str, output: ExtendedMessageProperties) -> dict:
    """Score urgency detection accuracy"""
    # TODO: Implement your scorer
    return {"score": 0}


# %% [markdown]
# ## Key Takeaways 🎓
#
# 1. **Start Simple**: Begin with basic prompts and iterate
# 2. **Be Specific**: Clear instructions improve results
# 3. **Use Examples**: Few-shot learning can significantly improve accuracy
# 4. **Test Systematically**: Use Weave's evaluation framework to measure improvements
# 5. **Track Everything**: Weave helps you understand what works and why
#
# ## Weave Features Showcased:
# - **@weave.op**: Track function calls and compare versions
# - **Model**: Organize prompts and parameters
# - **Dataset**: Structure your evaluation data
# - **Evaluation**: Systematic testing with multiple scorers
# - **EvaluationLogger**: Flexible, incremental evaluation logging
# - **Automatic Logging**: See inputs, outputs, and errors
# - **Performance Tracking**: Monitor latency and costs
#
# ## Next Steps:
# 1. Explore the Weave dashboard to see all your tracked experiments
# 2. Compare evaluation results across different models
# 3. Try different LLMs (GPT-4, Claude, etc.)
# 4. Build more complex evaluation pipelines
# 5. Create production-ready models with comprehensive testing
#
# Happy prompting! 🚀


def format_few_shot_examples(examples):
    """Format examples for few-shot learning."""
    formatted = []
    for example in examples:
        formatted.append(f"Input: {example['input']}")
        formatted.append(f"Output: {example['output']}")
        formatted.append("")
    return "\n".join(formatted)


def build_prompt(template, **kwargs):
    """Build a prompt from a template."""
    return template.format(**kwargs)
