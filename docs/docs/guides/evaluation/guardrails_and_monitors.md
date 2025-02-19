import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Online Evaluation

![Feedback](./../../../static/img/guardrails_scorers.png)

## Introduction

Building production LLM applications? Two questions likely keep you up at night:
1. How do you ensure your LLMs generate safe, appropriate content?
2. How do you measure and improve output quality over time?

Weave's unified scoring system answers both questions through a simple yet powerful framework. Whether you need active safety controls (guardrails) or passive quality monitoring, this guide will show you how to implement robust evaluation systems for your LLM applications.

The foundation of Weave's evaluation system is the [**Scorer**](./scorers.md) - a component that evaluates your function's inputs and outputs to measure quality, safety, or any other metric you care about. Scorers are versatile and can be used in two ways:

- **As Guardrails**: Block or modify unsafe content before it reaches users
- **As Monitors**: Track quality metrics over time to identify trends and improvements

:::note Terminology
Throughout this guide, we'll refer to functions decorated with `@weave.op` as "ops". These are regular Python functions that have been enhanced with Weave's tracking capabilities.
:::

#### Ready-to-Use Scorers
While this guide shows you how to create custom scorers, Weave comes with a variety of [predefined scorers](./builtin_scorers.mdx) that you can use right away, including:
- [Hallucination detection](./builtin_scorers.mdx#hallucinationfreescorer)
- [Summarization quality](./builtin_scorers.mdx#summarizationscorer)
- [Embedding similarity](./builtin_scorers.mdx#embeddingsimilarityscorer)
- [Relevancy evaluation](./builtin_scorers.mdx#ragas---contextrelevancyscorer)
- And more!


### Guardrails vs. Monitors: When to Use Each

While scorers power both guardrails and monitors, they serve different purposes:

| Aspect | Guardrails | Monitors |
|--------|------------|----------|
| **Purpose** | Active intervention to prevent issues | Passive observation for analysis |
| **Timing** | Real-time, before output reaches users | Can be asynchronous or batched |
| **Performance** | Must be fast (affects response time) | Can be slower, run in background |
| **Sampling** | Usually every request | Often sampled (e.g., 10% of calls) |
| **Control Flow** | Can block/modify outputs | No impact on application flow |
| **Resource Usage** | Must be efficient | Can use more resources if needed |

For example, a toxicity scorer could be used:
- 🛡️ **As a Guardrail**: Block toxic content immediately
- 📊 **As a Monitor**: Track toxicity levels over time

:::note
Every scorer result is automatically stored in Weave's database. This means your guardrails double as monitors without any extra work! You can always analyze historical scorer results, regardless of how they were originally used.
:::

### Using the `.call()` Method

To use scorers with Weave ops, you'll need access to both the operation's result and its tracking information. The `.call()` method provides both:

```python
# Instead of calling the op directly:
result = generate_text(input)  # Primary way to call the op but doesn't give access to the Call object

# Use the .call() method to get both result and Call object:
result, call = generate_text.call(input)  # Now you can use the call object with scorers
```

:::tip Why Use `.call()`?
The Call object is essential for associating the score with the call in the database. While you can directly call the scoring function, this would not be associated with the call, and therefore not searchable, filterable, or exportable for later analysis.

For more details about Call objects, see our [Calls guide section on Call objects](../tracking/tracing.mdx#getting-a-handle-to-the-call-object-during-execution).
:::

## Getting Started with Scorers

### Basic Example

Here's a simple example showing how to use `.call()` with a scorer:

```python
import weave
from weave import Scorer

class LengthScorer(Scorer):
    @weave.op
    def score(self, output: str) -> dict:
        """A simple scorer that checks output length."""
        return {
            "length": len(output),
            "is_short": len(output) < 100
        }

@weave.op
def generate_text(prompt: str) -> str:
    return "Hello, world!"

# Get both result and Call object
result, call = generate_text.call("Say hello")

# Now you can apply scorers
await call.apply_scorer(LengthScorer())
```

:::note Scorer Timing
When applying scorers:
- The main operation (`generate_text`) completes and is marked as finished in the UI
- Scorers run asynchronously after the main operation
- Scorer results are attached to the call once they complete
- You can view scorer results in the UI or query them via the API
:::

## Implementation Details

### The Scorer Interface

A scorer is a class that inherits from `Scorer` and implements a `score` method. The method receives:
- `output`: The result from your function
- Any input parameters matching your function's parameters

Here's a comprehensive example:

```python
@weave.op
def generate_styled_text(prompt: str, style: str, temperature: float) -> str:
    """Generate text in a specific style."""
    return "Generated text in requested style..."

class StyleScorer(Scorer):
    @weave.op
    def score(self, output: str, prompt: str, style: str) -> dict:
        """
        Evaluate if the output matches the requested style.
        
        Args:
            output: The generated text (automatically provided)
            prompt: Original prompt (matched from function input)
            style: Requested style (matched from function input)
        """
        return {
            "style_match": 0.9,  # How well it matches requested style
            "prompt_relevance": 0.8  # How relevant to the prompt
        }

# Example usage
async def generate_and_score():
    # Generate text with style
    result, call = generate_styled_text.call(
        prompt="Write a story",
        style="noir",
        temperature=0.7
    )
    
    # Score the result
    score = await call.apply_scorer(StyleScorer())
    print(f"Style match score: {score.result['style_match']}")
```

### Score Parameters

#### Parameter Matching Rules
- The `output` parameter is special and always contains the function's result
- Other parameters must match the function's parameter names exactly
- Scorers can use any subset of the function's parameters
- Parameter types should match the function's type hints

#### Handling Parameter Name Mismatches

Sometimes your scorer's parameter names might not match your function's parameter names exactly. For example:

```python
@weave.op
def generate_text(user_input: str):  # Uses 'user_input'
    return process(user_input)

class QualityScorer(Scorer):
    @weave.op
    def score(self, output: str, prompt: str):  # Expects 'prompt'
        """Evaluate response quality."""
        return {"quality_score": evaluate_quality(prompt, output)}

result, call = generate_text.call(user_input="Say hello")

# Map 'prompt' parameter to 'user_input'
scorer = QualityScorer(column_map={"prompt": "user_input"})
await call.apply_scorer(scorer)
```

Common use cases for `column_map`:
- Different naming conventions between functions and scorers
- Reusing scorers across different functions
- Using third-party scorers with your function names


#### Adding Additional Parameters

Sometimes scorers need extra parameters that aren't part of your function. You can provide these using `additional_scorer_kwargs`:

```python
class ReferenceScorer(Scorer):
    @weave.op
    def score(self, output: str, reference_answer: str):
        """Compare output to a reference answer."""
        similarity = compute_similarity(output, reference_answer)
        return {"matches_reference": similarity > 0.8}

# Provide the reference answer as an additional parameter
await call.apply_scorer(
    ReferenceScorer(),
    additional_scorer_kwargs={
        "reference_answer": "The Earth orbits around the Sun."
    }
)
```

This is useful when your scorer needs context or configuration that isn't part of the original function call.


### Using Scorers: Two Approaches

1. **With Weave's Op System** (Recommended)
```python
result, call = generate_text.call(input)
score = await call.apply_scorer(MyScorer())
```

2. **Direct Usage** (Quick Experiments)
```python
scorer = MyScorer()
score = scorer.score(output="some text")
```

**When to use each:**
- 👉 Use the op system for production, tracking, and analysis
- 👉 Use direct scoring for quick experiments or one-off evaluations

**Tradeoffs of Direct Usage:**
- ✅ Simpler for quick tests
- ✅ No Op required
- ❌ No association with the LLM/Op call

### Score Analysis


For detailed information about querying calls and their scorer results, see our [Score Analysis Guide](./scorers.md#score-analysis) and our [Data Access Guide](/guides/tracking/tracing#querying--exporting-calls).


## Production Best Practices

### 1. Analyze and Improve
- Review trends in the Weave Dashboard
- Look for patterns in low-scoring outputs
- Use insights to improve your LLM system
- Set up alerts for concerning patterns (coming soon)

### 2. Access Historical Data
Scorer results are stored with their associated calls and can be accessed through:
- The Call object's `feedback` field
- The Weave Dashboard
- Our query APIs

See the Complete Example section below for a demonstration of this pattern.

## Complete Example

Here's a comprehensive example that brings together all the concepts we've covered:

```python
import weave
from weave import Scorer
import asyncio
import random
from typing import Optional

class ToxicityScorer(Scorer):
    def __init__(self):
        # Initialize any expensive resources here
        self.model = load_toxicity_model()
    
    @weave.op
    async def score(self, output: str) -> dict:
        """Check content for toxic language."""
        try:
            result = await self.model.evaluate(output)
            return {
                "flagged": result.is_toxic,
                "reason": result.explanation if result.is_toxic else None
            }
        except Exception as e:
            # Log error and default to conservative behavior
            print(f"Toxicity check failed: {e}")
            return {"flagged": True, "reason": "Safety check unavailable"}

class QualityScorer(Scorer):
    @weave.op
    async def score(self, output: str, prompt: str) -> dict:
        """Evaluate response quality and relevance."""
        return {
            "coherence": evaluate_coherence(output),
            "relevance": evaluate_relevance(output, prompt),
            "grammar": evaluate_grammar(output)
        }

# Initialize scorers at module level (optional optimization)
toxicity_guard = ToxicityScorer()
quality_monitor = QualityScorer()
relevance_monitor = RelevanceScorer()

@weave.op
def generate_text(
    prompt: str,
    style: Optional[str] = None,
    temperature: float = 0.7
) -> str:
    """Generate an LLM response."""
    # Your LLM generation logic here
    return "Generated response..."

async def generate_safe_response(
    prompt: str,
    style: Optional[str] = None,
    temperature: float = 0.7
) -> str:
    """Generate a response with safety checks and quality monitoring."""
    try:
        # Generate initial response
        result, call = generate_text.call(
            prompt=prompt,
            style=style,
            temperature=temperature
        )

        # Apply safety check (guardrail)
        safety = await call.apply_scorer(toxicity_guard)
        if safety.result["flagged"]:
            return f"I cannot generate that content: {safety.result['reason']}"

        # Sample quality monitoring (10% of requests)
        if random.random() < 0.1:
            # Run quality checks in parallel
            await asyncio.gather(
                call.apply_scorer(quality_monitor),
                call.apply_scorer(relevance_monitor)
            )
        
        return result

    except Exception as e:
        # Log error and return user-friendly message
        print(f"Generation failed: {e}")
        return "I'm sorry, I encountered an error. Please try again."

# Example usage
async def main():
    # Basic usage
    response = await generate_safe_response("Tell me a story")
    print(f"Basic response: {response}")
    
    # Advanced usage with all parameters
    response = await generate_safe_response(
        prompt="Tell me a story",
        style="noir",
        temperature=0.8
    )
    print(f"Styled response: {response}")

```

This example demonstrates:
- Proper scorer initialization and error handling
- Combined use of guardrails and monitors
- Async operation with parallel scoring
- Production-ready error handling and logging

## Next Steps

For detailed implementation guidance, see:
- [Implementing Guardrails](./guardrails.md)
- [Implementing Monitors](./monitors.md)
- [Available Scorers](./scorers.md)
- [Weave Ops](../../guides/tracking/ops.md)

