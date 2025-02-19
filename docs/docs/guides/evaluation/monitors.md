# Monitors

![Monitors](./../../../static/img/guardrails_scorers.png)

## Introduction

:::note Prerequisites
Before implementing monitors, make sure you understand:
- [Scorer basics and implementation](./scorers.md)
- [Real-time evaluation concepts](./guardrails_and_monitors.md)
:::

## When to Use Monitors

Monitors are ideal for scenarios where you need:

| Requirement | Example Use Case |
|------------|-----------------|
| Quality Tracking | Measuring output coherence and relevance over time |
| Performance Analysis | Tracking latency and resource usage patterns |
| Model Drift Detection | Identifying changes in model behavior |
| A/B Testing | Comparing different model versions or configurations |

:::tip Cost Optimization
Since monitors run asynchronously and can be sampled, they're perfect for comprehensive evaluation without impacting performance. Consider using [guardrails](./guardrails.md) if you need to block unsafe content in real-time.
:::

## Using Scorers as Monitors

Monitors help track quality metrics over time without blocking operations. This is useful for:
- Identifying quality trends
- Detecting model drift
- Gathering data for model improvements

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



### Monitoring Sampling and Performance

Since monitors run in the background and don't block responses:

- **Set Appropriate Sampling Rates**
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

- **Monitor Multiple Aspects**
  ```python
  async def evaluate_comprehensively(call):
      await call.apply_scorer(ToxicityScorer())
      await call.apply_scorer(QualityScorer())
      await call.apply_scorer(LatencyScorer())
  ```

- **Performance Considerations**
  - Use sampling to reduce load
  - Can use more complex logic
  - Can make external API calls