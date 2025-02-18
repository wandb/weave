# Guardrails

![Guardrails](./../../../static/img/guardrails_scorers.png)

:::note Prerequisites
Before implementing guardrails, make sure you understand:
- [Scorer basics and implementation](./scorers.md)
- [Real-time evaluation concepts](./guardrails_and_monitors.md)
:::

## Using Scorers as Guardrails

Guardrails act as safety checks that run before allowing LLM output to reach users. Here's a practical example:

```python
import weave
from weave import Scorer

@weave.op
def generate_text(prompt: str) -> str:
    """Generate text using an LLM."""
    # Your LLM generation logic here
    return "Generated response..."

class ToxicityScorer(Scorer):
    @weave.op
    def score(self, output: str) -> dict:
        """
        Evaluate content for toxic language.
        """
        # Your toxicity detection logic here
        return {
            "flagged": False,  # True if content is toxic
            "reason": None     # Optional explanation if flagged
        }

async def generate_safe_response(prompt: str) -> str:
    # Get result and Call object
    result, call = generate_text.call(prompt)
    
    # Check safety
    safety = await call.apply_scorer(ToxicityScorer())
    if safety.result["flagged"]:
        return f"I cannot generate that content: {safety.result['reason']}"
    
    return result
```

:::note Scorer Timing
When applying scorers:
- The main operation (`generate_text`) completes and is marked as finished in the UI
- Scorers run asynchronously after the main operation
- Scorer results are attached to the call once they complete
- You can view scorer results in the UI or query them via the API
:::

## Performance Best Practices

For optimal performance with guardrails:
- Keep logic simple and fast
- Consider caching common results
- Avoid heavy external API calls
- Initialize guards outside of your main functions to avoid repeated initialization costs

### Initialize Guards Efficiently

For optimal performance, especially with locally-run models, initialize your guards outside of the main function. This pattern is particularly important when:
- Your scorers load ML models
- You're using local LLMs where latency is critical
- Your scorers maintain network connections
- You have high-traffic applications

## Complete Example

Here's a comprehensive example that demonstrates guardrail implementation:

```python
import weave
from weave import Scorer
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

# Initialize scorer at module level (optimization)
toxicity_guard = ToxicityScorer()

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
    """Generate a response with safety checks."""
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
        
        return result

    except Exception as e:
        # Log error and return user-friendly message
        print(f"Generation failed: {e}")
        return "I'm sorry, I encountered an error. Please try again."

# Example usage
async def main():
    response = await generate_safe_response(
        prompt="Tell me a story",
        style="noir",
        temperature=0.8
    )
    print(f"Response: {response}")
```

This example demonstrates:
- Proper scorer initialization and error handling
- Efficient guardrail implementation
- Production-ready error handling and logging
