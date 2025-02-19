# Guardrails

![Guardrails](./../../../static/img/guardrails_scorers.png)

## Introduction

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

### Guardrails Performance Optimization

For optimal performance with guardrails, since they block the response:

- **Initialize Guards Efficiently**
  - Initialize scorers outside of request handlers
  - Load ML models at module level
  - Set up network connections in advance
  - Particularly important for high-traffic applications

- **Optimize Scoring Logic**
  - Keep logic simple and fast
  - Consider caching common results
  - Avoid heavy external API calls
  - Initialize guards outside of main functions

