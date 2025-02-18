# Monitors

:::note Prerequisites
Before implementing monitors, make sure you understand:
- [Scorer basics and implementation](./scorers.md)
- [Real-time evaluation concepts](./guardrails_and_monitors.md)
:::

Monitors help track quality metrics over time without blocking operations. They provide passive observation for analysis, helping you identify trends, detect model drift, and gather data for improvements.

## Using Scorers as Monitors

Here's a practical example of implementing monitoring:

```python
import weave
from weave import Scorer
import random

@weave.op
def generate_text(prompt: str) -> str:
    """Generate text using an LLM."""
    return "Generated response..."

class QualityScorer(Scorer):
    @weave.op
    def score(self, output: str, prompt: str) -> dict:
        """Evaluate response quality."""
        return {
            "coherence": evaluate_coherence(output),
            "relevance": evaluate_relevance(output, prompt),
            "grammar": evaluate_grammar(output)
        }

async def generate_with_monitoring(prompt: str) -> str:
    # Get both the result and tracking information
    result, call = generate_text.call(prompt)
    
    # Sample monitoring (only monitor 10% of calls)
    if random.random() < 0.1:
        # Monitor multiple aspects asynchronously
        await call.apply_scorer(QualityScorer())
    
    return result
```

:::note Scorer Timing
When using monitors:
- The main operation completes and returns results immediately
- Monitors run asynchronously in the background
- Monitor results are stored for later analysis
- No impact on response time or application flow
:::

## Monitor Best Practices

### 1. Sampling Strategies
Since monitors don't block responses, you can be more flexible with sampling:

```python
class AdaptiveSampling:
    def __init__(self, base_rate: float = 0.1):
        self.base_rate = base_rate
        self.recent_scores = []
    
    def should_sample(self, prompt: str) -> bool:
        # Sample more if recent scores are concerning
        if len(self.recent_scores) > 0:
            avg_score = sum(self.recent_scores) / len(self.recent_scores)
            return random.random() < (self.base_rate * (2.0 - avg_score))
        return random.random() < self.base_rate
    
    def update(self, score: float):
        self.recent_scores = (self.recent_scores[-9:] + [score])

# Initialize sampling strategy
sampler = AdaptiveSampling()

async def generate_with_adaptive_monitoring(prompt: str) -> str:
    result, call = generate_text.call(prompt)
    
    if sampler.should_sample(prompt):
        score = await call.apply_scorer(QualityScorer())
        sampler.update(score.result["quality"])
    
    return result
```

### 2. Comprehensive Monitoring
Monitor multiple aspects of your system's performance:

```python
async def monitor_comprehensively(call):
    """Monitor various aspects of the response."""
    await asyncio.gather(
        call.apply_scorer(QualityScorer()),
        call.apply_scorer(LatencyScorer()),
        call.apply_scorer(TokenUsageScorer()),
        call.apply_scorer(PromptRelevanceScorer())
    )
```

### 3. Trend Analysis
Implement systems to analyze monitoring data over time:

```python
class TrendingTopicsMonitor(Scorer):
    def __init__(self):
        self.topic_counts = defaultdict(int)
        self.total_calls = 0
    
    @weave.op
    def score(self, output: str) -> dict:
        topics = self._extract_topics(output)
        self.total_calls += 1
        
        for topic in topics:
            self.topic_counts[topic] += 1
        
        return {
            "topics": topics,
            "trending_topics": self._get_trending(),
            "topic_distribution": {
                topic: count/self.total_calls 
                for topic, count in self.topic_counts.items()
            }
        }
```

:::caution Performance Tips
For optimal monitoring:
- Use appropriate sampling rates
- Run intensive checks asynchronously
- Batch operations when possible
- Consider storage and analysis requirements
- Monitor resource usage of the monitors themselves
:::

## Complete Monitor Example

Here's a comprehensive example showing a production-ready monitoring implementation:

```python
import weave
from weave import Scorer
import asyncio
from typing import Optional
from datetime import datetime

class MonitoringSystem:
    def __init__(self, base_sample_rate: float = 0.1):
        # Initialize monitors
        self.quality_monitor = QualityScorer()
        self.latency_monitor = LatencyScorer()
        self.usage_monitor = TokenUsageScorer()
        
        # Initialize sampling
        self.sampler = AdaptiveSampling(base_rate=base_sample_rate)
        
        # Track monitoring stats
        self.total_calls = 0
        self.monitored_calls = 0
    
    async def monitor_call(self, call, force_monitor: bool = False) -> None:
        """Apply monitoring to a call if sampled or forced."""
        self.total_calls += 1
        
        try:
            if force_monitor or self.sampler.should_sample():
                self.monitored_calls += 1
                
                # Run all monitors in parallel
                results = await asyncio.gather(
                    call.apply_scorer(self.quality_monitor),
                    call.apply_scorer(self.latency_monitor),
                    call.apply_scorer(self.usage_monitor),
                    return_exceptions=True
                )
                
                # Update sampling strategy based on quality score
                if not isinstance(results[0], Exception):
                    self.sampler.update(results[0].result["quality"])
                
                # Log any monitoring errors
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        print(f"Monitor {i} failed: {result}")
                        
        except Exception as e:
            print(f"Monitoring failed: {e}")
    
    def get_stats(self) -> dict:
        """Get current monitoring statistics."""
        return {
            "total_calls": self.total_calls,
            "monitored_calls": self.monitored_calls,
            "monitoring_rate": self.monitored_calls / max(1, self.total_calls),
            "current_sample_rate": self.sampler.get_current_rate()
        }

# Initialize monitoring system
monitor = MonitoringSystem()

@weave.op
def generate_text(prompt: str) -> str:
    """Generate text using an LLM."""
    return "Generated response..."

async def generate_with_monitoring(
    prompt: str,
    force_monitor: bool = False
) -> str:
    """Generate a response with comprehensive monitoring."""
    try:
        # Generate response
        result, call = generate_text.call(prompt)
        
        # Apply monitoring asynchronously
        asyncio.create_task(monitor.monitor_call(call, force_monitor))
        
        return result
        
    except Exception as e:
        print(f"Generation failed: {e}")
        return "An error occurred during content generation"

# Example usage
async def main():
    # Generate with normal sampling
    response = await generate_with_monitoring("Tell me a story")
    
    # Generate with forced monitoring
    response = await generate_with_monitoring(
        "Tell me another story",
        force_monitor=True
    )
    
    # Check monitoring stats
    print(monitor.get_stats())
```

This example demonstrates:
- Adaptive sampling strategy
- Parallel monitor execution
- Error handling and logging
- Monitoring statistics tracking
- Production-ready implementation

For more information about the core concepts of scorers and evaluation in Weave, see our [Guardrails and Monitors Overview](./guardrails_and_monitors.md). 

:::tip See Also
- [Guardrails Guide](./guardrails.md) - Learn about active safety controls
- [Builtin Scorers](./builtin_scorers.mdx) - Ready-to-use monitoring scorers
- [Batch Evaluation](../core-types/evaluations.md) - For offline evaluation needs
:::

:::info Relationship with Guardrails
Remember that every scorer result is automatically stored in Weave's database. This means your guardrails automatically double as monitors! You can analyze historical scorer results from both guardrails and monitors in the same way.
::: 