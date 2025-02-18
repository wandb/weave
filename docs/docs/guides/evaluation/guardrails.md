# Guardrails

:::note Prerequisites
Before implementing guardrails, make sure you understand:
- [Scorer basics and implementation](./scorers.md)
- [Real-time evaluation concepts](./guardrails_and_monitors.md)
:::

Guardrails act as safety checks that run before allowing LLM output to reach users. They provide active intervention to prevent issues in real-time, ensuring your application maintains quality and safety standards.

## Using Scorers as Guardrails

Here's a practical example of implementing a guardrail:

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
When applying guardrails:
- The main operation (`generate_text`) completes first
- Guardrail checks run immediately after
- The response is only returned if it passes all checks
- Failed checks can trigger alternative responses or error messages
:::

## Guardrail Best Practices

### 1. Performance Optimization
Since guardrails run in real-time and block the response, performance is critical:

```python
# Initialize guards at module level for better performance
toxicity_guard = ToxicityScorer()
quality_guard = QualityScorer()

async def generate_safe_response(prompt: str) -> str:
    result, call = generate_text.call(prompt)
    
    # Use pre-initialized guards
    safety = await call.apply_scorer(toxicity_guard)
    if safety.result["flagged"]:
        return f"I cannot generate that content: {safety.result['reason']}"
    
    return result
```

### 2. Error Handling
Implement robust error handling to ensure your application remains functional even if a guardrail check fails:

```python
class SafetyScorer(Scorer):
    @weave.op
    async def score(self, output: str) -> dict:
        try:
            result = await self.evaluate_safety(output)
            return {
                "flagged": result.is_unsafe,
                "reason": result.explanation
            }
        except Exception as e:
            # Log error and default to conservative behavior
            print(f"Safety check failed: {e}")
            return {
                "flagged": True,
                "reason": "Safety check unavailable - defaulting to conservative behavior"
            }
```

### 3. Cascading Guardrails
Apply multiple guardrails in a logical sequence, from fastest to most comprehensive:

```python
async def generate_safe_response(prompt: str) -> str:
    result, call = generate_text.call(prompt)
    
    # Quick checks first
    length = await call.apply_scorer(LengthScorer())
    if length.result["too_long"]:
        return "Response exceeds maximum length"
    
    # More intensive checks next
    safety = await call.apply_scorer(toxicity_guard)
    if safety.result["flagged"]:
        return f"Content flagged: {safety.result['reason']}"
    
    # Most comprehensive checks last
    quality = await call.apply_scorer(quality_guard)
    if quality.result["score"] < 0.5:
        return "Response does not meet quality standards"
    
    return result
```

:::caution Performance Tips
For optimal guardrail performance:
- Keep logic simple and fast
- Initialize expensive resources (like ML models) once
- Consider caching common results
- Avoid unnecessary network calls
- Run checks in parallel when order doesn't matter
:::

## Complete Guardrail Example

Here's a comprehensive example showing a production-ready guardrail implementation:

```python
import weave
from weave import Scorer
import asyncio
from typing import Optional

class ContentGuard:
    def __init__(self):
        # Initialize all guardrails once
        self.toxicity_guard = ToxicityScorer()
        self.quality_guard = QualityScorer()
        self.length_guard = LengthScorer()
    
    async def check_content(self, call) -> tuple[bool, Optional[str]]:
        """Run all guardrail checks in parallel."""
        try:
            # Run all checks in parallel
            safety, quality, length = await asyncio.gather(
                call.apply_scorer(self.toxicity_guard),
                call.apply_scorer(self.quality_guard),
                call.apply_scorer(self.length_guard)
            )
            
            # Check results in order of importance
            if safety.result["flagged"]:
                return False, f"Content safety: {safety.result['reason']}"
            
            if length.result["too_long"]:
                return False, "Content length exceeds limits"
            
            if quality.result["score"] < 0.5:
                return False, "Content quality below threshold"
            
            return True, None
            
        except Exception as e:
            print(f"Guard check failed: {e}")
            return False, "Guard check failed - defaulting to conservative behavior"

@weave.op
def generate_text(prompt: str) -> str:
    """Generate text using an LLM."""
    return "Generated response..."

# Initialize guard system once
content_guard = ContentGuard()

async def generate_safe_response(prompt: str) -> str:
    """Generate a response with comprehensive guardrails."""
    try:
        # Generate initial response
        result, call = generate_text.call(prompt)
        
        # Apply guardrails
        is_safe, reason = await content_guard.check_content(call)
        if not is_safe:
            return f"Cannot provide response: {reason}"
        
        return result
        
    except Exception as e:
        print(f"Generation failed: {e}")
        return "An error occurred during content generation"
```

This example demonstrates:
- Efficient guard initialization
- Parallel guard execution
- Comprehensive error handling
- Clear failure messaging
- Production-ready implementation

For more information about the core concepts of scorers and evaluation in Weave, see our [Guardrails and Monitors Overview](./guardrails_and_monitors.md). 

:::tip See Also
- [Monitors Guide](./monitors.md) - Learn about passive quality monitoring
- [Builtin Scorers](./builtin_scorers.mdx) - Ready-to-use guardrail scorers
- [Batch Evaluation](../core-types/evaluations.md) - For offline evaluation needs
::: 