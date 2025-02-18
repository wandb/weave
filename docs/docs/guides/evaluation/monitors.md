# Monitors

![Monitors](./../../../static/img/guardrails_scorers.png)

:::note Prerequisites
Before implementing monitors, make sure you understand:
- [Scorer basics and implementation](./scorers.md)
- [Real-time evaluation concepts](./guardrails_and_monitors.md)
:::

## Using Scorers as Monitors

Monitors help track quality metrics over time without blocking operations. This is useful for:
- Identifying quality trends
- Detecting model drift
- Gathering data for model improvements

Here's a basic example of implementing monitors:

```python
import weave
from weave import Scorer
from weave.scorers import ValidJSONScorer, ValidXMLScorer
import random

@weave.op
def generate_text(prompt: str) -> str:
    """Generate text using an LLM."""
    return "Generated response..."

async def generate_with_monitoring(prompt: str) -> str:
    # Get both the result and tracking information
    result, call = generate_text.call(prompt)
    
    # Sample monitoring (only monitor 10% of calls)
    if random.random() < 0.1:
        # Monitor multiple aspects asynchronously
        await call.apply_scorer(ValidJSONScorer())
        await call.apply_scorer(ValidXMLScorer())
    
    return result
```

## Best Practices

### 1. Set Appropriate Sampling Rates
```python
@weave.op
def generate_text(prompt: str) -> str:
    return generate_response(prompt)

async def generate_with_sampling(prompt: str) -> str:
    result, call = generate_text.call(prompt)
    
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
Scorer results are stored with their associated calls and can be accessed through:
- The Call object's `feedback` field
- The Weave Dashboard
- Our query APIs

### Performance Considerations
For monitors:
- Use sampling to reduce load
- Can use more complex logic
- Can make external API calls

## Complete Example

Here's a comprehensive example that demonstrates monitor implementation:

```python
import weave
from weave import Scorer
import asyncio
import random
from typing import Optional

class QualityScorer(Scorer):
    @weave.op
    async def score(self, output: str, prompt: str) -> dict:
        """Evaluate response quality and relevance."""
        return {
            "coherence": evaluate_coherence(output),
            "relevance": evaluate_relevance(output, prompt),
            "grammar": evaluate_grammar(output)
        }

# Initialize monitors at module level
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

async def generate_with_monitoring(
    prompt: str,
    style: Optional[str] = None,
    temperature: float = 0.7
) -> str:
    """Generate a response with quality monitoring."""
    try:
        # Generate initial response
        result, call = generate_text.call(
            prompt=prompt,
            style=style,
            temperature=temperature
        )

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
    response = await generate_with_monitoring(
        prompt="Tell me a story",
        style="noir",
        temperature=0.8
    )
    print(f"Response: {response}")
```

This example demonstrates:
- Proper monitor initialization
- Efficient sampling implementation
- Parallel scoring for better performance
- Production-ready error handling
