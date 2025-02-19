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


## Production Best Practices

### 1. Initialize Guards Efficiently

For optimal performance, especially with locally-run models, initialize your guards outside of the main function. This pattern is particularly important when:
- Your scorers load ML models
- You're using local LLMs where latency is critical
- Your scorers maintain network connections
- You have high-traffic applications

See the Complete Example section below for a demonstration of this pattern.

:::caution Performance Tips
- Keep logic simple and fast
- Consider caching common results
- Avoid heavy external API calls
- Initialize guards outside of your main functions to avoid repeated initialization costs
:::