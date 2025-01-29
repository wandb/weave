import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Guardrails and Monitors

![Feedback](./../../../static/img/guardrails_scorers.png)

## Introduction

Building production LLM applications? Two questions likely keep you up at night:
1. How do you ensure your LLMs generate safe, appropriate content?
2. How do you measure and improve output quality over time?

Weave's unified scoring system answers both questions through a simple yet powerful framework. Whether you need active safety controls (guardrails) or passive quality monitoring, this guide will show you how to implement robust evaluation systems for your LLM applications.

## Overview

The foundation of Weave's evaluation system is the [**Scorer**](./scorers.md) - a component that evaluates your function's inputs and outputs to measure quality, safety, or any other metric you care about. Scorers are versatile and can be used in two ways:

- **As Guardrails**: Block or modify unsafe content before it reaches users
- **As Monitors**: Track quality metrics over time to identify trends and improvements

:::tip
Every scorer result is automatically stored in Weave's database. This means your guardrails double as monitors without any extra work! You can always analyze historical scorer results, regardless of how they were originally used.
:::

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

For example, a toxicity scorer could be used to:
- 🛡️ **As a Guardrail**: Block toxic content immediately
- 📊 **As a Monitor**: Track toxicity levels over time

## Using Scorers as Guardrails

Guardrails act as safety checks that run before allowing LLM output to reach users. Here's a practical example:

```python
import weave
from weave import Scorer

@weave.op()
def generate_text(prompt: str) -> str:
    """Generate text using an LLM."""
    # Your LLM generation logic here
    return "Generated response..."

class ToxicityScorer(Scorer):
    @weave.op
    def score(self, output: str) -> dict:
        """
        Evaluate content for toxic language.
        Returns scores between 0 (safe) and 1 (toxic).
        """
        # Your toxicity detection logic here
        return {
            "toxicity_score": 0.1,
            "profanity_score": 0.0
        }

async def generate_safe_response(prompt: str) -> str:
    # Get result and tracking information
    result, call = generate_text.call(prompt)
    
    # Check safety
    safety = await call.apply_scorer(ToxicityScorer())
    if safety.score["toxicity_score"] > 0.7:
        return "I cannot generate that content."
    
    return result
```

## Using Scorers as Monitors

Monitors help track quality metrics over time without blocking operations. This is useful for:
- Identifying quality trends
- Detecting model drift
- Gathering data for model improvements

```python
@weave.op()
def generate_text(prompt: str) -> str:
    """Generate text using an LLM."""
    return "Generated response..."

async def generate_with_monitoring(prompt: str) -> str:
    # Get both the result and tracking information
    result, call = generate_text.call(prompt)
    
    # Sample monitoring (only monitor 10% of calls)
    if random.random() < 0.1:
        # Monitor multiple aspects asynchronously
        await call.apply_scorer(QualityScorer())
        await call.apply_scorer(RelevanceScorer())
    
    return result
```

## Implementation Details

### The Scorer Interface

A scorer is a class that inherits from `Scorer` and implements a `score` method. The method receives:
- `output`: The result from your function
- Any input parameters matching your function's parameters

Here's a comprehensive example:

```python
@weave.op()
def generate_styled_text(prompt: str, style: str, temperature: float) -> str:
    """Generate text in a specific style."""
    return "Generated text..."

class StyleScorer(Scorer):
    @weave.op
    def score(self, output: str, prompt: str, style: str) -> dict:
        """
        Evaluate if the output matches the requested style.
        
        Args:
            output: The generated text (automatically provided)
            prompt: Original prompt (matched from function input)
            style: Requested style (matched from function input)
            
        Note: We don't need temperature, so we don't include it
        """
        return {
            "style_match": 0.9,  # How well it matches requested style
            "prompt_relevance": 0.8  # How relevant to the prompt
        }
```

:::tip Parameter Matching Rules
- The `output` parameter is special and always contains the function's result
- Other parameters must match the function's parameter names exactly
- Scorers can use any subset of the function's parameters
- Parameter types should match the function's type hints
:::

### Using Scorers: Two Approaches

1. **With Weave's Op System** (Recommended)
```python
result, call = my_op.call(input)
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

## Production Best Practices

### 1. Set Appropriate Sampling Rates
```python
@weave.op()
def my_llm_function(prompt: str) -> str:
    return generate_response(prompt)

async def generate_with_sampling(prompt: str) -> str:
    result, call = my_llm_function.call(prompt)
    
    # Only monitor 10% of calls
    if random.random() < 0.1:
        await call.apply_scorer(ToxicityScorer())
        await call.apply_scorer(QualityScorer())
    
    return result
```

### 2. Monitor Multiple Aspects
```python
async def evaluate_comprehensively(call):
    await call.apply_scorer(ToxicityScorer())
    await call.apply_scorer(QualityScorer())
    await call.apply_scorer(LatencyScorer())
```

### 3. Analyze and Improve
- Review trends in the Weave Dashboard
- Look for patterns in low-scoring outputs
- Use insights to improve your LLM system
- Set up alerts for concerning patterns (coming soon)

### 4. Access Historical Data
```python
# Query results through API
calls = my_llm_function.calls()

# Access through Python SDK
call = client.get_call(call_id)
feedback_data = call.feedback
```

:::caution Performance Tips
For Guardrails:
- Keep logic simple and fast
- Consider caching common results
- Avoid heavy external API calls

For Monitors:
- Use sampling to reduce load
- Can use more complex logic
- Can make external API calls
:::

## Next Steps

- Explore [Available Scorers](./scorers.md)
- Learn about [Weave Ops](../../guides/tracking/ops.md)
