# %% [markdown]
# # 🚀 Prompt Engineering Workshop with Weave
# 
# Welcome to this hands-on workshop where we'll explore prompt engineering techniques while learning how Weave can help us build better LLM applications!
# 
# ## What we'll cover:
# 1. **Basic Prompt Engineering** - Extracting structured data from unstructured text
# 2. **Prompt Iteration** - Using Weave to track and compare different prompts
# 3. **Few-shot Learning** - Improving results with examples
# 4. **Evaluation** - Building datasets and scoring functions
# 5. **Advanced Techniques** - Chain of thought, role playing, and more
# 
# ## Our Use Case: Customer Support Triage 📧
# We'll build a system that extracts key information from customer support emails to help route them efficiently.

# %%
# Install dependencies
# %pip install weave openai pydantic -qqq

# %%
# Setup
import os
import json
from typing import List, Dict, Optional
from getpass import getpass
from openai import OpenAI
from pydantic import BaseModel, Field
import weave

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
    "My SmartTV X500 won't connect to WiFi anymore. It was working fine yesterday. - Bob Wilson"
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
        response_format={"type": "json_object"}
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
        temperature=0.1  # Lower temperature for more consistent outputs
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
            "issue_description": "AirPods won't charge, case shows no lights"
        }
    },
    {
        "email": "This laptop is terrible! The screen keeps flickering. Model: ThinkPad X1 Carbon Gen 9. -Mike Chen",
        "extracted": {
            "customer_name": "Mike Chen",
            "product_model": "ThinkPad X1 Carbon Gen 9",
            "issue_description": "Screen keeps flickering"
        }
    }
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
        temperature=0.1
    )
    
    parsed = json.loads(response.choices[0].message.content)
    return MessageProperties(**parsed)

# Test few-shot version
print("Few-shot learning result:")
v3_result = extract_properties_v3_fewshot(sample_emails[1])
print(v3_result.model_dump_json(indent=2))

# %% [markdown]
# ## Part 4: Building an Evaluation Dataset 📊
# 
# Now let's create a proper evaluation dataset and scoring function to measure our improvements.

# %%
# Create evaluation dataset
eval_dataset = [
    {
        "email": "Hello support team, I'm John Doe. My XPhone 12 Pro keeps randomly shutting off during calls. This is really frustrating!",
        "expected": {
            "customer_name": "John Doe",
            "product_model": "XPhone 12 Pro",
            "issue_description": "Phone randomly shuts off during calls"
        }
    },
    {
        "email": "My new AeroWatch V2's strap completely fell apart after just one day of use. This is unacceptable! - Jane Smith",
        "expected": {
            "customer_name": "Jane Smith",
            "product_model": "AeroWatch V2",
            "issue_description": "Watch strap fell apart after one day"
        }
    },
    {
        "email": "Hi, Bob Wilson here. The SmartTV X500 I bought last month suddenly stopped connecting to my WiFi network.",
        "expected": {
            "customer_name": "Bob Wilson",
            "product_model": "SmartTV X500",
            "issue_description": "TV won't connect to WiFi"
        }
    },
    {
        "email": "URGENT: Gaming Console Z crashed and won't turn back on. Blue light flashes 3 times. -Alex Kumar",
        "expected": {
            "customer_name": "Alex Kumar",
            "product_model": "Gaming Console Z",
            "issue_description": "Console crashed, blue light flashes 3 times"
        }
    },
    {
        "email": "Lisa Park writing about my EcoVac R10 robot vacuum. It keeps getting stuck under furniture even though it's supposed to detect obstacles.",
        "expected": {
            "customer_name": "Lisa Park",
            "product_model": "EcoVac R10",
            "issue_description": "Robot vacuum gets stuck under furniture"
        }
    }
]

# Create a Weave Dataset
weave_dataset = weave.Dataset(name="support_emails", rows=eval_dataset)

# %%
# Define scoring functions
@weave.op
def exact_match_scorer(expected: dict, predicted: MessageProperties) -> dict:
    """Score based on exact field matches"""
    predicted_dict = predicted.model_dump()
    
    scores = {}
    for field in ['customer_name', 'product_model', 'issue_description']:
        scores[f"{field}_exact_match"] = int(
            expected.get(field, "").lower().strip() == 
            predicted_dict.get(field, "").lower().strip()
        )
    
    scores['all_fields_correct'] = int(all(scores.values()))
    return scores

@weave.op
def similarity_scorer(expected: dict, predicted: MessageProperties) -> dict:
    """Score based on semantic similarity (simplified version)"""
    from difflib import SequenceMatcher
    
    predicted_dict = predicted.model_dump()
    scores = {}
    
    for field in ['customer_name', 'product_model', 'issue_description']:
        expected_val = expected.get(field, "").lower().strip()
        predicted_val = predicted_dict.get(field, "").lower().strip()
        
        similarity = SequenceMatcher(None, expected_val, predicted_val).ratio()
        scores[f"{field}_similarity"] = similarity
    
    scores['avg_similarity'] = sum(scores.values()) / len(scores)
    return scores

# %%
# Create evaluation function
@weave.op
def evaluate_extractor(extractor_func, dataset: weave.Dataset):
    """Evaluate an extraction function on a dataset"""
    results = []
    
    for row in dataset.rows:
        try:
            # Extract properties
            extracted = extractor_func(row['email'])
            
            # Score the extraction
            exact_scores = exact_match_scorer(row['expected'], extracted)
            similarity_scores = similarity_scorer(row['expected'], extracted)
            
            results.append({
                'email': row['email'],
                'expected': row['expected'],
                'predicted': extracted.model_dump(),
                **exact_scores,
                **similarity_scores
            })
        except Exception as e:
            print(f"Error processing email: {e}")
            results.append({
                'email': row['email'],
                'error': str(e)
            })
    
    # Calculate summary metrics
    summary = {
        'total_examples': len(results),
        'avg_exact_match': sum(r.get('all_fields_correct', 0) for r in results) / len(results),
        'avg_similarity': sum(r.get('avg_similarity', 0) for r in results) / len(results)
    }
    
    return results, summary

# Run evaluation on all versions
print("Evaluating all versions...\n")

for version, func in [
    ("v1_basic", extract_properties_v1),
    ("v2_improved", extract_properties_v2),
    ("v3_fewshot", extract_properties_v3_fewshot)
]:
    results, summary = evaluate_extractor(func, weave_dataset)
    print(f"{version}:")
    print(f"  Exact match rate: {summary['avg_exact_match']:.2%}")
    print(f"  Average similarity: {summary['avg_similarity']:.2%}")
    print()

# %% [markdown]
# ## Part 5: Advanced Techniques 🚀
# 
# Let's explore some advanced prompt engineering techniques.

# %%
# Chain of Thought (CoT) approach
@weave.op
def extract_properties_v4_cot(message: str) -> MessageProperties:
    """Version 4: Chain of Thought reasoning"""
    
    system_prompt = """You are an expert at analyzing customer support emails.
    Think step-by-step to extract information accurately."""
    
    user_prompt = f"""Analyze this customer support email step by step:

Email: {message}

Follow these steps:
1. First, identify any names mentioned or signatures
2. Then, look for product names and model numbers
3. Finally, summarize the main issue in a concise way
4. Return your findings as JSON with fields: customer_name, product_model, issue_description

Think through each step before providing your final answer."""

    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.1
    )
    
    parsed = json.loads(response.choices[0].message.content)
    return MessageProperties(**parsed)

# Role-based approach
@weave.op
def extract_properties_v5_role(message: str) -> MessageProperties:
    """Version 5: Role-based persona"""
    
    system_prompt = """You are a senior customer support specialist with 10 years of experience.
    You excel at quickly identifying key information from customer emails to route them to the right team.
    You're known for your accuracy and attention to detail."""
    
    user_prompt = f"""As an experienced support specialist, extract the key information from this email:

{message}

Provide a JSON summary with:
- customer_name: The customer's full name
- product_model: The exact product model (be specific)
- issue_description: A clear, concise summary suitable for ticket routing"""

    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.1
    )
    
    parsed = json.loads(response.choices[0].message.content)
    return MessageProperties(**parsed)

# %%
# Test advanced techniques
test_email = """Subject: HELP! Expensive headphones failing

I can't believe this is happening. I paid $350 for these SoundMax Pro Elite 
headphones just 2 months ago and now the left ear cup has completely stopped 
working. No sound at all! I've tried different devices, different cables, 
even reset them multiple times. Nothing works.

This is completely unacceptable for such expensive headphones.

Frustrated customer,
Patricia Martinez"""

print("Testing advanced techniques on complex email:\n")
print(f"Email:\n{test_email}\n")
print("-" * 50)

# Test each advanced version
for name, func in [
    ("Chain of Thought", extract_properties_v4_cot),
    ("Role-based", extract_properties_v5_role)
]:
    print(f"\n{name} approach:")
    result = func(test_email)
    print(result.model_dump_json(indent=2))

# %% [markdown]
# ## Part 6: Using Weave to Compare and Analyze 📈
# 
# Now let's use Weave's features to compare all our approaches and understand what works best.

# %%
# Create a comprehensive comparison
@weave.op
def compare_all_versions(test_emails: List[str]):
    """Compare all extraction versions"""
    
    versions = {
        "v1_basic": extract_properties_v1,
        "v2_improved": extract_properties_v2,
        "v3_fewshot": extract_properties_v3_fewshot,
        "v4_cot": extract_properties_v4_cot,
        "v5_role": extract_properties_v5_role
    }
    
    comparison_results = []
    
    for email in test_emails:
        email_results = {"email": email[:50] + "...", "results": {}}
        
        for version_name, func in versions.items():
            try:
                result = func(email)
                email_results["results"][version_name] = result.model_dump()
            except Exception as e:
                email_results["results"][version_name] = {"error": str(e)}
        
        comparison_results.append(email_results)
    
    return comparison_results

# Run comparison
comparison = compare_all_versions([row['email'] for row in eval_dataset[:3]])

print("Comparison of all versions (first email):")
first_email_results = comparison[0]['results']
for version, result in first_email_results.items():
    print(f"\n{version}:")
    if 'error' not in result:
        print(f"  Customer: {result['customer_name']}")
        print(f"  Product: {result['product_model']}")
        print(f"  Issue: {result['issue_description'][:50]}...")
    else:
        print(f"  Error: {result['error']}")

# %% [markdown]
# ## Workshop Exercises 🎯
# 
# Now it's your turn! Try these exercises to practice prompt engineering:
# 
# ### Exercise 1: Handle Edge Cases
# Create a new version that handles emails where:
# - The customer name is not explicitly stated
# - Multiple products are mentioned
# - The issue is vague or unclear
# 
# ### Exercise 2: Add New Fields
# Extend the extraction to include:
# - Urgency level (low/medium/high)
# - Customer sentiment (positive/neutral/negative)
# - Category (hardware/software/other)
# 
# ### Exercise 3: Multi-language Support
# Create a version that can handle emails in different languages
# 
# ### Exercise 4: Custom Evaluation Metrics
# Design your own scoring function that better reflects real-world requirements

# %%
# Exercise starter code
class ExtendedMessageProperties(BaseModel):
    customer_name: str
    product_model: str
    issue_description: str
    urgency_level: str = Field(description="low/medium/high")
    customer_sentiment: str = Field(description="positive/neutral/negative")
    category: str = Field(description="hardware/software/other")

@weave.op
def extract_properties_extended(message: str) -> ExtendedMessageProperties:
    """Your implementation here!"""
    # TODO: Implement your enhanced extraction
    pass

# Test with edge cases
edge_case_emails = [
    "Your product is terrible! Nothing works anymore!",  # No name, no specific product
    "Both my iPhone 14 and iPad Pro are having issues with the screen. Very urgent!",  # Multiple products
    "Something's wrong with my device. Please help."  # Vague description
]

# %% [markdown]
# ## Key Takeaways 🎓
# 
# 1. **Start Simple**: Begin with basic prompts and iterate
# 2. **Be Specific**: Clear instructions improve results
# 3. **Use Examples**: Few-shot learning can significantly improve accuracy
# 4. **Test Systematically**: Use evaluation datasets to measure improvements
# 5. **Track Everything**: Weave helps you understand what works and why
# 
# ## Weave Features Showcased:
# - **@weave.op**: Track function calls and compare versions
# - **weave.Dataset**: Organize evaluation data
# - **Automatic Logging**: See inputs, outputs, and errors
# - **Version Comparison**: Understand which prompts work best
# - **Performance Tracking**: Monitor latency and costs
# 
# ## Next Steps:
# 1. Explore the Weave dashboard to see all your tracked experiments
# 2. Try different models (GPT-4, Claude, etc.)
# 3. Build more complex chains and workflows
# 4. Create production-ready evaluations
# 
# Happy prompting! 🚀 