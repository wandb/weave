import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Guardrails and Monitors

![Feedback](./../../../static/img/guardrails_scorers.png)

## Introduction

When deploying LLM applications in production, two critical challenges emerge:
1. How do we ensure our LLMs generate safe and appropriate content?
2. How do we track and improve the quality of LLM outputs over time?

Weave addresses these challenges through a unified scoring system that enables both active safety controls (guardrails) and passive quality monitoring. This guide explains how to implement these safety mechanisms in your LLM applications.

## Overview

At the heart of Weave's evaluation system is the concept of **Scorers** - components that evaluate a function's inputs and outputs in order to assign quality/safety scores. While all scorers share the same underlying infrastructure, they can be used in two distinct ways:

- **As Guardrails**: Actively prevent unsafe or low-quality outputs by evaluating content before it reaches users
- **As Monitors**: Passively track quality metrics over time to identify trends and areas for improvement

:::tip
There is no need to use a scorer for both guardrails and monitors. The underlying database will automatically store all scorer results, so in pracice, all guardrails are effectively monitors.
:::

### Guardrails vs. Monitors

While both guardrails and monitors use the same scorer infrastructure, they serve different purposes and have different implementation considerations:

| Aspect | Guardrails | Monitors |
|--------|------------|----------|
| **Purpose** | Active intervention to prevent issues | Passive observation for analysis |
| **Timing** | Real-time, before output reaches users | Can be asynchronous or batched |
| **Performance Requirements** | Must be fast (affects response time) | Can tolerate higher latency |
| **Sampling** | Usually run on every call | Often sampled (e.g., 10% of calls) |
| **Control Flow** | Affects application flow (can block/modify outputs) | No impact on application flow |
| **Resource Usage** | Need to be resource-efficient | Can use more resources if needed |

For example, you might use the same toxicity scorer in two ways:
- As a guardrail: Block toxic content before it reaches users (needs to be fast, runs on every request)
- As a monitor: Track toxicity levels over time (can be slower, samples 10% of requests)

For a comprehensive overview of available scorers and how to create custom ones, see our [Evaluation Metrics](./scorers.md) guide.

## Using Scorers as Guardrails

Guardrails act as safety checks that run before allowing LLM output to reach users. Here's a practical example:

```python
import weave
from weave import Scorer

# Define your LLM function as a Weave op
# See our guide on Ops for more details: /guides/tracking/ops
@weave.op()
def generate_text(prompt: str) -> str:
    """Generate text using an LLM."""
    # Your LLM generation logic here
    return "Generated response..."

# Define your safety criteria
class ToxicityScorer(Scorer):
    @weave.op
    def score(self, output: str) -> float:
        """
        Evaluate content for toxic language.
        Returns 1.0 for safe content, lower scores for potentially toxic content.
        """
        # Your toxicity detection logic here
        return score

# Example usage in an API endpoint
async def generate_safe_response(user_input: str) -> str:
    # Call the op and get both result and tracking information
    result, call = generate_text.call(user_input)
    
    # Apply safety check
    safety_check = await call.apply_scorer(ToxicityScorer())
    
    if safety_check.score < 0.7:
        return "I cannot generate that content as it may be inappropriate."
    
    return result
```

## Using Scorers as Monitors

Monitors help track quality metrics over time without blocking operations. This is useful for:
- Identifying quality trends
- Detecting model drift
- Gathering data for model improvements

```python
import weave

# Define your LLM function as a Weave op
@weave.op()
def generate_text(prompt: str) -> str:
    """Generate text using an LLM."""
    return "Generated response..."

async def generate_with_monitoring(user_input: str) -> str:
    # Get both the result and tracking information
    result, call = generate_text.call(user_input)
    
    # Monitor quality metrics (runs asynchronously)
    await call.apply_scorer(QualityScorer())
    await call.apply_scorer(RelevanceScorer())
    
    return result
```

## Implementation Details

### The Scorer Interface

All scorers in Weave implement the `Scorer` base class. For a complete guide on creating custom scorers, see our [Evaluation Metrics](./scorers.md) documentation.

#### Parameter Conventions

Scorers follow specific conventions for their `score` method parameters:

1. **`output` Parameter**: Always represents the result of the op being scored
2. **Input Parameters**: Must match the parameter names of the op being scored
3. **Parameter Subset**: Scorers can use all or a subset of the op's input parameters

Here's an example showing these conventions:

```python
import weave
from weave import Scorer

# An op that generates a response given a prompt and style
@weave.op()
def generate_styled_text(prompt: str, style: str, temperature: float) -> str:
    """Generate text in a specific style."""
    # LLM generation logic here
    return "Generated response..."

# A scorer that evaluates both style adherence and quality
class StyleAdherenceScorer(Scorer):
    @weave.op
    def score(self, output: str, prompt: str, style: str) -> dict:
        """
        Evaluate if the output matches the requested style.
        
        Args:
            output: The generated text (automatically provided from op result)
            prompt: The original prompt (matched from op input)
            style: The requested style (matched from op input)
            
        Returns:
            dict: Scoring results
        """
        # Note: We don't need temperature, so we didn't include it
        return {
            "style_match": self._check_style_match(output, style),
            "prompt_relevance": self._check_relevance(output, prompt)
        }

# Using the scorer
async def generate_with_style_check(prompt: str, style: str):
    result, call = generate_styled_text.call(
        prompt=prompt,
        style=style,
        temperature=0.7
    )
    
    # The scorer automatically receives matching parameters
    evaluation = await call.apply_scorer(StyleAdherenceScorer())
    
    if evaluation.score["style_match"] < 0.8:
        return "Failed to generate text in the requested style."
    
    return result
```

:::tip Parameter Matching Rules
- The `output` parameter is special and always contains the op's result
- Other parameters must match the op's parameter names exactly
- Scorers can use any subset of the op's parameters
- Parameter types should match the op's type hints
- If a scorer needs a parameter not in the op, use the op's context or scorer initialization
:::

For more complex cases, you can also initialize scorers with additional context:

```python
class ContextAwareScorer(Scorer):
    def __init__(self, reference_data: dict):
        self.reference = reference_data
    
    @weave.op
    def score(self, output: str, prompt: str) -> dict:
        """Score using both op parameters and initialized context."""
        return {
            "accuracy": self._check_against_reference(
                output, prompt, self.reference
            )
        }

# Using a context-aware scorer
scorer = ContextAwareScorer(reference_data={"key": "value"})
evaluation = await call.apply_scorer(scorer)
```

### Technical Notes

When applying scorers in Weave:

1. Your functions must be decorated with `@weave.op()` to enable tracking (see [Ops guide](/guides/tracking/ops))
2. Use the `.call()` method to get both the result and tracking object
3. Scorer results are automatically logged and accessible through Weave's interfaces

:::tip
While the implementation requires using Weave ops and the `.call()` method, this enables powerful features like:
- Automatic logging of all evaluations
- Integration with Weave's monitoring dashboard
- Historical tracking and analysis
:::

### Direct Scorer Usage

While the examples above show using scorers with Weave's op system, you can also use scorers directly:

```python
# Direct usage of a scorer
toxicity_scorer = ToxicityScorer()
score = toxicity_scorer.score("Some text to evaluate")

# vs using with Weave's op system
result, call = my_llm_op.call("Input prompt")
evaluation = await call.apply_scorer(ToxicityScorer())
```

**Tradeoffs of Direct Usage:**
- ✅ Simpler to use for quick experiments or one-off evaluations
- ✅ No need to set up Weave ops for simple scoring tasks
- ❌ Scores aren't associated with specific LLM calls in the database
- ❌ Can't use Weave's analysis features (filtering calls by score, tracking trends, etc.)
- ❌ No automatic logging or monitoring capabilities

:::tip When to Use Direct Scoring
Use direct scoring for:
- Quick experiments and prototyping
- One-off evaluations
- Cases where you don't need to track the relationship between LLM calls and their scores

Use the op system when:
- You want to track scores alongside LLM calls
- You need to analyze trends over time
- You want to filter/query calls based on their scores
:::

## Analysis and Observability

All scorer results are automatically logged and can be accessed through:

1. **UI Dashboard**: View detailed scoring history
2. **Call Tables**: Analyze trends across operations
3. **API Access**: Query results programmatically

![Feedback](./../../../static/img/guardrails_scorers.png)

### Production Monitoring Best Practices

When implementing monitoring in production:

1. **Set Appropriate Sampling Rates**
   ```python
   @weave.op
   def my_llm_function(prompt: str) -> str:
       return generate_response(prompt)

   # Sample 10% of calls
   if random.random() < 0.1:
       await call.apply_scorer(ToxicityScorer())
   ```

2. **Monitor Multiple Aspects**
   - Content safety (toxicity, bias)
   - Output quality (relevance, coherence)
   - Performance metrics (latency, token usage)
   ```python
   async def comprehensive_monitoring(result, call):
       await call.apply_scorer(ToxicityScorer())
       await call.apply_scorer(QualityScorer())
       await call.apply_scorer(LatencyScorer())
   ```
3. **Set Up Alerts** (Coming Soon)
   - Alerting capabilities are under development and will be available in a future release
   - Stay tuned for features like trend monitoring, change detection, and threshold alerts

4. **Regular Analysis**
   - Review scorer results periodically
   - Look for patterns in low-scoring outputs
   - Use insights to improve your LLM system

### Accessing Results

```python
# Query results through API
calls = client.server.calls_query_stream({
    "include_feedback": True  # Include scorer results
})

# Access through Python SDK
call = client.get_call(call_id)
feedback_data = call.feedback

# Example: Analyze trends
async def analyze_toxicity_trend(start_date, end_date):
    calls = client.server.calls_query_stream({
        "include_feedback": True,
        "start_date": start_date,
        "end_date": end_date
    })
    # Process and analyze the results
    return analysis
```

:::caution Performance Considerations
When implementing scorers, consider their usage pattern:

**For Guardrails:**
- Keep evaluation logic simple and fast
- Consider caching common evaluations
- Avoid heavy external API calls when possible

**For Monitors:**
- Use sampling to reduce load (`tracing_sample_rate` in op decorator)
- Can use more complex evaluation logic
- Can make external API calls or use more expensive models
:::

## Next Steps

- Learn more about [Weave Ops](/guides/tracking/ops)
- Explore available [Evaluation Metrics](./scorers.md)
- Learn how to [Create Custom Scorers](./scorers.md)
