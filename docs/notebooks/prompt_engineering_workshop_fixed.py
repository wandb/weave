# %%
"""First, let's install the pre-requisites for this workshop."""

# %pip install weave openai pydantic -qqq

# %%
"""Basic authentication setup for OpenAI"""
import os
from getpass import getpass

if not os.environ.get("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = getpass("Enter your OpenAI API key: ")

# %%
"""Next, let's define a simple use case: Support Triage"""
import json

from openai import OpenAI
from pydantic import BaseModel
import weave


class MessageProperties(BaseModel):
    customer_name: str
    product_model: str
    issue_description: str

@weave.op
def extract_properties_from_message(message: str) -> MessageProperties:
    # Define the system prompt
    system_prompt = """
    You are a helpful assistant that extracts properties from a customer support message.
    Always respond with valid JSON containing exactly these fields:
    - customer_name
    - product_model
    - issue_description
    """

    # Define the user prompt
    user_prompt = f"""
    Extract the following properties:
    - customer_name
    - product_model
    - issue_description

    from the customer support message:
    {message}
    
    Return as JSON with exactly these field names.
    """

    # Initialize the OpenAI client
    openai = OpenAI()

    # Fetch the response
    response = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"}  # This ensures JSON output
    )

    # Parse the response
    parsed = json.loads(response.choices[0].message.content)

    # Validate the response
    result = MessageProperties.model_validate(parsed)

    # Return the result
    return result

# %%
"""
Now, let's run this on a basic example:
"""

weave.init("prompt_eng_workshop")

result = extract_properties_from_message(
    "Hello, My XPhone 12 Pro keeps randomly shutting off mid-call. Please help."
)
print(result)
print(f"\nCustomer: {result.customer_name}")
print(f"Product: {result.product_model}")
print(f"Issue: {result.issue_description}")

# %%
# 1. Define the synthetic dataset
dataset = [
    {
        "email": "Hello,\nI'm John Doe. My XPhone 12 Pro keeps randomly shutting off mid-call. Please help!\nThanks, John.",
        "gold": {
            "customer_name": "John Doe",
            "product_model": "XPhone 12 Pro",
            "issue_description": "My XPhone 12 Pro keeps randomly shutting off mid-call",
        },
    },
    {
        "email": "Hi support,\nThis is Jane. I bought an AeroWatch V2 last week. The strap fell apart after one day.\nRegards,\nJane",
        "gold": {
            "customer_name": "Jane",
            "product_model": "AeroWatch V2",
            "issue_description": "The strap fell apart after one day",
        },
    },
]

# 2. Schema and fields
SCHEMA_FIELDS = ["customer_name", "product_model", "issue_description"]

# 3. Few-shot exemplars (use first 3 of dataset)
FEW_SHOT_EXAMPLES = dataset[:3]

# 4. Prompt templates
ZERO_SHOT_TEMPLATE = """
Extract the following fields from the customer email and output valid JSON:
- customer_name
- product_model
- issue_description

Email:
\"\"\"{email}\"\"\"
"""

FEW_SHOT_TEMPLATE = """
Here are some examples of extracting information from customer emails:

{examples}

Now extract the same fields from this email:
Email:
\"\"\"{email}\"\"\"
"""

# 5. Helper function to format few-shot examples
def format_few_shot_examples(examples):
    formatted = []
    for ex in examples:
        formatted.append(f"Email: {ex['email']}")
        formatted.append(f"Extracted: {json.dumps(ex['gold'], indent=2)}\n")
    return "\n".join(formatted)

# 6. Updated call_model function using our existing function
@weave.op
def call_model(prompt: str) -> str:
    """
    Call the LLM with the given prompt and return JSON string.
    """
    openai = OpenAI()
    response = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "Extract information and return valid JSON."},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"}
    )
    return response.choices[0].message.content

# 7. Evaluation function
def evaluate(prompt_fn, use_few_shot: bool = False):
    """
    Runs the model against the dataset, returning per-field correct counts
    and the number of full-pass examples.
    """
    results = {f: 0 for f in SCHEMA_FIELDS}
    full_pass = 0

    few_shot_block = format_few_shot_examples(FEW_SHOT_EXAMPLES) if use_few_shot else ""

    for example in dataset:
        email = example["email"]
        gold = example["gold"]

        if use_few_shot:
            prompt = prompt_fn(few_shot_block, email)
        else:
            prompt = prompt_fn(email)

        try:
            output = call_model(prompt)
            parsed = json.loads(output)
        except Exception as e:
            # Malformed JSON or API error counts as failure on all fields
            print(f"Error: {e}")
            continue

        ok = True
        for f in SCHEMA_FIELDS:
            if parsed.get(f, "").strip() == gold[f].strip():
                results[f] += 1
            else:
                ok = False
        if ok:
            full_pass += 1

    return results, full_pass

# 8. Prompt builder functions
def build_zero_shot_prompt(email: str) -> str:
    return ZERO_SHOT_TEMPLATE.format(email=email)

def build_few_shot_prompt(few_shot_block: str, email: str) -> str:
    return FEW_SHOT_TEMPLATE.format(examples=few_shot_block, email=email)

# 9. Main demonstration
if __name__ == "__main__":
    print("=== Zero-Shot Evaluation ===")
    try:
        zs_results, zs_full = evaluate(build_zero_shot_prompt, use_few_shot=False)
        total = len(dataset)
        for f in SCHEMA_FIELDS:
            print(f"{f}: {zs_results[f]}/{total} correct")
        print(f"Full-pass: {zs_full}/{total}")
    except Exception as e:
        print(f"Error in zero-shot: {e}")

    print("\n=== Few-Shot Evaluation ===")
    try:
        fs_results, fs_full = evaluate(build_few_shot_prompt, use_few_shot=True)
        total = len(dataset)
        for f in SCHEMA_FIELDS:
            print(f"{f}: {fs_results[f]}/{total} correct")
        print(f"Full-pass: {fs_full}/{total}")
    except Exception as e:
        print(f"Error in few-shot: {e}") 