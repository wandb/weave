import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Guardrails and Monitors

![Feedback](./../../../static/img/guardrails_scorers.png)

Weave provides a robust framework for implementing safety controls and monitoring systems in LLM applications through a unified scoring system. This guide explains how to leverage scorers as both guardrails for active intervention and monitors for passive evaluation in production environments.

## Core Concepts

The foundation of Weave's evaluation system is the `Scorer` class. This abstract base class defines a scoring interface through its `score` method, which concrete implementations use to provide specific evaluation metrics. For a comprehensive overview of available metrics and custom scorer implementation, see [Evaluation Metrics](./scorers.md).

Here's a basic example of a custom scorer:

```python
class MyScorer(Scorer):
    def score(self, output: str) -> float:
        """
        Evaluate the given result and return a score between 0 and 1.
        
        Args:
            result: The LLM-generated content to evaluate
            
        Returns:
            float: Score indicating quality/safety (0 = fail, 1 = pass)
        """
        return 0.8  # Example score
```

### Applying Scorers

Scorers are applied to operations using the `apply_scorer` method, which returns an `ApplyScorerResult`:

```python
@dataclass
class ApplyScorerSuccess:
    result: Any  # The original operation result
    score_call: Call  # The scoring operation call object
```

Basic scorer application:

```python
# Get both operation result and Call object
result, call = op.call(user_input)

# Apply scorer and get evaluation results
evaluation = await call.apply_scorer(scorer)
```

:::important
Always use `op.call(user_input)` rather than direct invocation (`op(user_input)`) when working with scorers. This method returns both the operation result and a `Call` object required for scorer application.
:::

## Guardrails

Guardrails provide active safety mechanisms by evaluating LLM outputs in real-time and intervening based on scorer results. They are essential for preventing inappropriate or harmful content generation in production systems.

### Implementation

```python
async def process_with_guardrail(user_input: str) -> str:
    """
    Process user input with safety guardrails.
    
    Args:
        user_input: The user's input to process
        
    Returns:
        str: Processed result if guardrail passes, fallback response if it fails
    """
    result, call = op.call(user_input)
    evaluation = await call.apply_scorer(guardrail)
    
    if evaluation.score < 0.5:
        return handle_failed_guardrail(result)
    return result
```

## Monitors

While guardrails provide active intervention, monitors offer passive evaluation and tracking of LLM operations. They are crucial for long-term quality assurance and system improvement.

### Implementation

```python
async def monitored_operation(user_input: str, sampling_rate: float = 0.25) -> str:
    """
    Execute operation with monitoring.
    
    Args:
        user_input: The input to process
        sampling_rate: Percentage of operations to monitor (0.0 to 1.0)
        
    Returns:
        str: Operation result
    """
    result, call = op.call(user_input)
    
    # Apply monitoring based on sampling rate
    if random.random() < sampling_rate:
        await call.apply_scorer(scorer)
    
    return result
```

:::caution Performance Considerations
Scorer evaluations execute synchronously on the same machine as the operation. For high-throughput production environments, consider adjusting sampling rates based on load. Weave will soon support server-side scoring for high-throughput applications.
:::

## Analysis and Observability

### Accessing Scorer Results

All scorer results are automatically logged as Feedback records in Weave, accessible through multiple interfaces:

1. **UI Dashboard**: Access detailed scoring history in the Call details page
2. **Call Tables**: Filter and analyze scores across operations
3. **Programmatic Access**: Query results through API endpoints

![Feedback](./../../../static/img/guardrails_scorers.png)

### Data Access Examples

#### HTTP API
```python
calls = client.server.calls_query_stream({
    # ... your filters
    "include_feedback": True,  # Include all scorer results
})
```

#### Python SDK
```python
# Retrieve comprehensive feedback data for a specific call
call = client.get_call(call_id)
feedback_data = call.feedback
```

## Next Steps

- Deep dive into [Evaluation Metrics](./scorers.md)
