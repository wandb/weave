import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Learn Weave with W&B Inference

This guide shows you how to use W&B Weave with [W&B Inference](https://docs.wandb.ai/guides/inference/). Using W&B Inference, you can build and trace LLM applications using live open-source models without setting up your own infrastructure or managing API keys from multiple providers. Just obtain your W&B API key and use it to interact with [all models hosted by W&B Inference](https://docs.wandb.ai/guides/inference/models/).

## What you'll learn

In this guide, you'll:
- Set up Weave and W&B Inference
- Build a simple LLM application with automatic tracing
- Compare multiple models
- Evaluate model performance on a dataset
- View your results in the Weave UI

## Prerequisites

Before you begin, you need a [W&B account](https://app.wandb.ai/login?signup=true) and an API key from from [https://wandb.ai/authorize](https://wandb.ai/authorize).

Then, in a Python environment running version 3.8 or later, install the required libraries: 

```bash
pip install weave openai
```

The `openai` library is installed because you use the standard `openai` client to interact with W&B Inference, regardless of which hosted model you're actually calling. This allows you to swap between supported models by only changing the slug, and make use of any existing code you have that was written to use the OpenAI API. 

## Step 1: Trace your first LLM call

Start with a simple example that uses Llama 3.1-8B through W&B Inference. 

When you run this code, Weave:
- Traces your LLM call automatically
- Logs inputs, outputs, latency, and token usage
- Provides a link to view your trace in the Weave UI

```python
import weave
import openai

# Initialize Weave - replace with your-team/your-project
weave.init("my-first-weave-project")

# Create an OpenAI-compatible client pointing to W&B Inference
client = openai.OpenAI(
    base_url='https://api.inference.wandb.ai/v1',
    api_key="YOUR_WANDB_API_KEY",  # Replace with your actual API key
    project="my-first-weave-project",  # Required for usage tracking
)

# Decorate your function to enable tracing; use the standard OpenAI client
@weave.op()
def ask_llama(question: str) -> str:
    response = client.chat.completions.create(
        model="meta-llama/Llama-3.1-8B-Instruct",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": question}
        ],
    )
    return response.choices[0].message.content

# Call your function - Weave automatically traces everything
result = ask_llama("What are the benefits of using W&B Weave for LLM development?")
print(result)
```

## Step 2: Build a text summarization application

Create a simple summarization app that shows how Weave traces nested operations:

```python
@weave.op()
def extract_key_points(text: str) -> list[str]:
    """Extract key points from a text."""
    response = client.chat.completions.create(
        model="meta-llama/Llama-3.1-8B-Instruct",
        messages=[
            {"role": "system", "content": "Extract 3-5 key points from the text. Return each point on a new line."},
            {"role": "user", "content": text}
        ],
    )
    return response.choices[0].message.content.strip().split('\n')

@weave.op()
def create_summary(text: str, key_points: list[str]) -> str:
    """Create a concise summary based on key points."""
    points_text = "\n".join([f"- {point}" for point in key_points])
    response = client.chat.completions.create(
        model="meta-llama/Llama-3.1-8B-Instruct",
        messages=[
            {"role": "system", "content": "Create a 2-3 sentence summary based on these key points."},
            {"role": "user", "content": f"Key points:\n{points_text}"}
        ],
    )
    return response.choices[0].message.content

@weave.op()
def summarize_text(text: str) -> dict:
    """Main summarization pipeline."""
    key_points = extract_key_points(text)
    summary = create_summary(text, key_points)
    return {
        "key_points": key_points,
        "summary": summary
    }

# Try it with sample text
sample_text = """
The Apollo 11 mission was a historic spaceflight that landed the first humans on the Moon 
on July 20, 1969. Commander Neil Armstrong and lunar module pilot Buzz Aldrin descended 
to the lunar surface while Michael Collins remained in orbit. Armstrong became the first 
person to step onto the Moon, followed by Aldrin 19 minutes later. They spent about 
two and a quarter hours together outside the spacecraft, collecting samples and taking photographs.
"""

result = summarize_text(sample_text)
print("Key Points:", result["key_points"])
print("\nSummary:", result["summary"])
```

## Step 3: Compare multiple models

W&B Inference provides access to multiple models. Compare their performance:

```python
# Define a Model class to compare different LLMs
class InferenceModel(weave.Model):
    model_name: str
    
    @weave.op()
    def predict(self, question: str) -> str:
        response = client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "user", "content": question}
            ],
        )
        return response.choices[0].message.content

# Create instances for different models
llama_model = InferenceModel(model_name="meta-llama/Llama-3.1-8B-Instruct")
deepseek_model = InferenceModel(model_name="deepseek-ai/DeepSeek-V3-0324")

# Compare their responses
test_question = "Explain quantum computing in one paragraph for a high school student."

print("Llama 3.1 8B response:")
print(llama_model.predict(test_question))
print("\n" + "="*50 + "\n")
print("DeepSeek V3 response:")
print(deepseek_model.predict(test_question))
```

## Step 4: Evaluate model performance

Evaluate how well different models perform on a Q&A task:

```python
# Create a simple dataset
dataset = [
    {"question": "What is 2 + 2?", "expected": "4"},
    {"question": "What is the capital of France?", "expected": "Paris"},
    {"question": "Name a primary color", "expected_one_of": ["red", "blue", "yellow"]},
]

# Define a scorer
@weave.op()
def accuracy_scorer(expected: str, output: str, expected_one_of: list[str] = None) -> dict:
    """Score the accuracy of the model output."""
    output_clean = output.strip().lower()
    
    if expected_one_of:
        is_correct = any(option.lower() in output_clean for option in expected_one_of)
    else:
        is_correct = expected.lower() in output_clean
    
    return {"correct": is_correct, "score": 1.0 if is_correct else 0.0}

# Evaluate a model
@weave.op()
def evaluate_model(model: InferenceModel, dataset: list[dict]) -> dict:
    """Run evaluation on a dataset."""
    scores = []
    
    for example in dataset:
        # Get model prediction
        output = model.predict(example["question"])
        
        # Score the output
        score = accuracy_scorer(
            expected=example.get("expected", ""),
            output=output,
            expected_one_of=example.get("expected_one_of")
        )
        scores.append(score["score"])
    
    return {
        "model": model.model_name,
        "accuracy": sum(scores) / len(scores),
        "total_correct": sum(scores),
        "total_examples": len(dataset)
    }

# Run evaluation
results = evaluate_model(llama_model, dataset)
print(f"Model: {results['model']}")
print(f"Accuracy: {results['accuracy']:.2%}")
print(f"Correct: {results['total_correct']}/{results['total_examples']}")
```

After running these examples, you'll see links in your terminal. Click any link to view traces in the Weave UI.

In the Weave UI, you can:
- See a timeline of all your LLM calls
- Inspect inputs and outputs for each operation
- View token usage and estimated costs
- Analyze latency and performance metrics
- Compare different runs

## Available models

For a complete list of available models, see the [Available Models section](https://docs.wandb.ai/guides/inference/models/) in the W&B Inference documentation.

## Next steps

- **Use the Playground**: [Try models interactively](guides/tools/playground.md#access-the-playground) in the Weave Playground
- **Build evaluations**: Learn about [systematic evaluation](guides/core-types/evaluations.md) of your LLM applications
- **Try other integrations**: Weave works with [OpenAI, Anthropic, and many more](guides/integrations/index.md)
- **Deploy your app**: Use [Weave Serve](guides/tools/serve.md) to deploy your applications

## Troubleshooting

<details>
<summary>Authentication errors</summary>

If you get authentication errors:
1. Verify you have a valid W&B account
2. Check that you're using the correct API key from [wandb.ai/authorize](https://wandb.ai/authorize)
3. Ensure your project name follows the format `team-name/project-name`

</details>

<details>
<summary>Rate limit errors</summary>

W&B Inference has concurrency limits per project. If you hit rate limits:
- Reduce the number of concurrent requests
- Add delays between calls
- Consider upgrading your plan for higher limits

For more details, see the [limits documentation for W&B Inference](https://docs.wandb.ai/guides/inference/usage-limits/).

</details>

<details>
<summary>Running out of credits</summary>

The free tier includes limited credits. See the [usage and limits documentation](https://docs.wandb.ai/guides/inference/usage-limits/) for details.

</details>