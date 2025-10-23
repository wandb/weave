# Verdict

import DefaultEntityNote from '../../../src/components/DefaultEntityNote.mdx';

<a target="_blank" href="https://github.com/wandb/examples/blob/master/weave/docs/quickstart_verdict.ipynb">
  <img src="https://colab.research.google.com/assets/colab-badge.svg" alt="Open In Colab"/>
</a>

Weave is designed to make tracking and logging all calls made through the [Verdict Python library](https://verdict.haizelabs.com/docs/) effortless.

When working with AI evaluation pipelines, debugging is crucial. Whether a pipeline step fails, outputs are unexpected, or nested operations create confusion, pinpointing issues can be challenging. Verdict applications often consist of multiple pipeline steps, judges, and transformations, making it essential to understand the inner workings of your evaluation workflows.

Weave simplifies this process by automatically capturing traces for your [Verdict](https://verdict.readthedocs.io/) applications. This enables you to monitor and analyze your pipeline's performance, making it easier to debug and optimize your AI evaluation workflows.

## Getting Started

To get started, call `weave.init(project=...)` at the beginning of your script. Use the `project` argument to log to a specific W&B Team name with `team-name/project-name`.

```python
import weave
from verdict import Pipeline
from verdict.common.judge import JudgeUnit
from verdict.schema import Schema

# Initialize Weave with your project name
# highlight-next-line
weave.init("verdict_demo")

# Create a simple evaluation pipeline
pipeline = Pipeline()
pipeline = pipeline >> JudgeUnit().prompt("Rate the quality of this text: {source.text}")

# Create sample data
data = Schema.of(text="This is a sample text for evaluation.")

# Run the pipeline - this will be automatically traced
output = pipeline.run(data)

print(output)
```

## Tracking Call Metadata

To track metadata from your Verdict pipeline calls, you can use the [`weave.attributes`](https://weave-docs.wandb.ai/reference/python-sdk/weave/#function-attributes) context manager. This context manager allows you to set custom metadata for a specific block of code, such as a pipeline run or evaluation batch.

```python
import weave
from verdict import Pipeline
from verdict.common.judge import JudgeUnit
from verdict.schema import Schema

# Initialize Weave with your project name
# highlight-next-line
weave.init("verdict_demo")

pipeline = Pipeline()
pipeline = pipeline >> JudgeUnit().prompt("Evaluate sentiment: {source.text}")

data = Schema.of(text="I love this product!")

# highlight-next-line
with weave.attributes({"evaluation_type": "sentiment", "batch_id": "batch_001"}):
    output = pipeline.run(data)

print(output)
```

<DefaultEntityNote />

Weave automatically tracks the metadata against the trace of the Verdict pipeline call. You can view the metadata in the Weave web interface.

## Traces

Storing traces of AI evaluation pipelines in a central database is crucial during both development and production. These traces are essential for debugging and improving your evaluation workflows by providing a valuable dataset.

Weave automatically captures traces for your Verdict applications. It will track and log all calls made through the Verdict library, including:

- Pipeline execution steps
- Judge unit evaluations  
- Layer transformations
- Pooling operations
- Custom units and transformations

You can view the traces in the Weave web interface, showing the hierarchical structure of your pipeline execution.

## Pipeline Tracing Example

Here's a more complex example showing how Weave traces nested pipeline operations:

```python
import weave
from verdict import Pipeline, Layer
from verdict.common.judge import JudgeUnit
from verdict.transform import MeanPoolUnit
from verdict.schema import Schema

# Initialize Weave with your project name
# highlight-next-line
weave.init("verdict_demo")

# Create a complex pipeline with multiple steps
pipeline = Pipeline()
pipeline = pipeline >> Layer([
    JudgeUnit().prompt("Rate coherence: {source.text}"),
    JudgeUnit().prompt("Rate relevance: {source.text}"),
    JudgeUnit().prompt("Rate accuracy: {source.text}")
], 3)
pipeline = pipeline >> MeanPoolUnit()

# Sample data
data = Schema.of(text="This is a comprehensive evaluation of text quality across multiple dimensions.")

# Run the pipeline - all operations will be traced
result = pipeline.run(data)

print(f"Average score: {result}")
```

This will create a detailed trace showing:
- The main Pipeline execution
- Each JudgeUnit evaluation within the Layer
- The MeanPoolUnit aggregation step
- Timing information for each operation

## Configuration

Upon calling `weave.init()`, tracing is automatically enabled for Verdict pipelines. The integration works by patching the `Pipeline.__init__` method to inject a `VerdictTracer` that forwards all trace data to Weave.

No additional configuration is needed - Weave will automatically:
- Capture all pipeline operations
- Track execution timing
- Log inputs and outputs
- Maintain trace hierarchy
- Handle concurrent pipeline execution

## Custom Tracers and Weave

If you're using custom Verdict tracers in your application, Weave's `VerdictTracer` can work alongside them:

```python
import weave
from verdict import Pipeline
from verdict.common.judge import JudgeUnit
from verdict.util.tracing import ConsoleTracer
from verdict.schema import Schema

# Initialize Weave with your project name
# highlight-next-line
weave.init("verdict_demo")

# You can still use Verdict's built-in tracers
console_tracer = ConsoleTracer()

# Create pipeline with both Weave (automatic) and Console tracing
pipeline = Pipeline(tracer=[console_tracer])  # Weave tracer is added automatically
pipeline = pipeline >> JudgeUnit().prompt("Evaluate: {source.text}")

data = Schema.of(text="Sample evaluation text")

# This will trace to both Weave and console
result = pipeline.run(data)
```

## Models and Evaluations

Organizing and evaluating AI systems with multiple pipeline components can be challenging. Using the [`weave.Model`](/guides/core-types/models), you can capture and organize experimental details like prompts, pipeline configurations, and evaluation parameters, making it easier to compare different iterations.

The following example demonstrates wrapping a Verdict pipeline in a `WeaveModel`:

```python
import asyncio
import weave
from verdict import Pipeline
from verdict.common.judge import JudgeUnit
from verdict.schema import Schema

# Initialize Weave with your project name
# highlight-next-line
weave.init("verdict_demo")

# highlight-next-line
class TextQualityEvaluator(weave.Model):
    judge_prompt: str
    pipeline_name: str

# highlight-next-line
    @weave.op()
    async def predict(self, text: str) -> dict:
        pipeline = Pipeline(name=self.pipeline_name)
        pipeline = pipeline >> JudgeUnit().prompt(self.judge_prompt)
        
        data = Schema.of(text=text)
        result = pipeline.run(data)
        
        return {
            "text": text,
            "quality_score": result.score if hasattr(result, 'score') else result,
            "evaluation_prompt": self.judge_prompt
        }

model = TextQualityEvaluator(
    judge_prompt="Rate the quality of this text on a scale of 1-10: {source.text}",
    pipeline_name="text_quality_evaluator"
)

text = "This is a well-written and informative piece of content that provides clear value to readers."

prediction = asyncio.run(model.predict(text))

# if you're in a Jupyter Notebook, run:
# prediction = await model.predict(text)

print(prediction)
```

This code creates a model that can be visualized in the Weave UI, showing both the pipeline structure and the evaluation results.

### Evaluations

Evaluations help you measure the performance of your evaluation pipelines themselves. By using the [`weave.Evaluation`](/guides/core-types/evaluations) class, you can capture how well your Verdict pipelines perform on specific tasks or datasets:

```python
import asyncio
import weave
from verdict import Pipeline
from verdict.common.judge import JudgeUnit
from verdict.schema import Schema

# Initialize Weave
# highlight-next-line
weave.init("verdict_demo")

# Create evaluation model
class SentimentEvaluator(weave.Model):
    @weave.op()
    async def predict(self, text: str) -> dict:
        pipeline = Pipeline()
        pipeline = pipeline >> JudgeUnit().prompt(
            "Classify sentiment as positive, negative, or neutral: {source.text}"
        )
        
        data = Schema.of(text=text)
        result = pipeline.run(data)
        
        return {"sentiment": result}

# Test data
texts = [
    "I love this product, it's amazing!",
    "This is terrible, worst purchase ever.",
    "The weather is okay today."
]
labels = ["positive", "negative", "neutral"]

examples = [
    {"id": str(i), "text": texts[i], "target": labels[i]}
    for i in range(len(texts))
]

# Scoring function
@weave.op()
def sentiment_accuracy(target: str, output: dict) -> dict:
    predicted = output.get("sentiment", "").lower()
    return {"correct": target.lower() in predicted}

model = SentimentEvaluator()

evaluation = weave.Evaluation(
    dataset=examples,
    scorers=[sentiment_accuracy],
)

scores = asyncio.run(evaluation.evaluate(model))
# if you're in a Jupyter Notebook, run:
# scores = await evaluation.evaluate(model)

print(scores)
```

This creates an evaluation trace that shows how your Verdict pipeline performs across different test cases.

## Best Practices

### Performance Monitoring
Weave automatically captures timing information for all pipeline operations. You can use this to identify performance bottlenecks:

```python
import weave
from verdict import Pipeline, Layer
from verdict.common.judge import JudgeUnit
from verdict.schema import Schema

# highlight-next-line
weave.init("verdict_demo")

# Create a pipeline that might have performance variations
pipeline = Pipeline()
pipeline = pipeline >> Layer([
    JudgeUnit().prompt("Quick evaluation: {source.text}"),
    JudgeUnit().prompt("Detailed analysis: {source.text}"),  # This might be slower
], 2)

data = Schema.of(text="Sample text for performance testing")

# Run multiple times to see timing patterns
for i in range(3):
    with weave.attributes({"run_number": i}):
        result = pipeline.run(data)
```

### Error Handling
Weave automatically captures exceptions that occur during pipeline execution:

```python
import weave
from verdict import Pipeline
from verdict.common.judge import JudgeUnit
from verdict.schema import Schema

# highlight-next-line
weave.init("verdict_demo")

pipeline = Pipeline()
pipeline = pipeline >> JudgeUnit().prompt("Process: {source.invalid_field}")  # This will cause an error

data = Schema.of(text="Sample text")

try:
    result = pipeline.run(data)
except Exception as e:
    print(f"Pipeline failed: {e}")
    # Error details are captured in Weave trace
```

By integrating Weave with Verdict, you get comprehensive observability into your AI evaluation pipelines, making it easier to debug, optimize, and understand your evaluation workflows.
