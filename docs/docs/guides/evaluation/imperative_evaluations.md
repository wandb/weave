# Imperative Evaluations

The `EvaluationLogger` provides a flexible way to log evaluation data directly from your Python code. You don't need deep knowledge of Weave's internal data types; simply instantiate a logger and use its methods (`log_prediction`, `log_score`, `log_summary`) to record evaluation steps.

This approach is particularly helpful in complex workflows where the entire dataset or all scorers might not be defined upfront.

In contrast to the standard `Evaluation` object, which requires a predefined `Dataset` and list of `Scorer` objects, the imperative logger allows you to log individual predictions and their associated scores incrementally as they become available.

:::info Looking for a more opinionated approach?

If you prefer a more structured evaluation framework with predefined datasets and scorers, check out Weave's standard [Evaluation framework](../core-types/evaluations.md). The standard approach provides a more declarative way to define and run evaluations, with built-in support for datasets, scorers, and comprehensive reporting.

The imperative approach described on this page offers more flexibility for complex workflows, while the standard evaluation framework provides more structure and guidance.

:::

## Basic usage

1.  **Initialize the logger:** Create an instance of `EvaluationLogger`. You can optionally provide strings or dictionaries as metadata for the `Model` and `Dataset` being evaluated. If omitted, default placeholders are used.
2.  **Log Predictions:** For each input/output pair from your model or system, call `log_prediction`. This method returns an `ScoreLogger` object tied to that specific prediction event.
3.  **Log Scores:** Use the `ScoreLogger` object obtained in the previous step to log scores via the `log_score` method. You can log multiple scores from different conceptual scorers (identified by string names or `Scorer` objects) for the same prediction. Call `finish()` on the score logger when you're done logging scores for that prediction to finalize it. _Note: After calling `finish()`, the `ScoreLogger` instance cannot be used to log additional scores._
4.  **Log Summary:** After processing all your examples and logging their predictions and scores, call `log_summary` on the main `EvaluationLogger` instance. This action finalizes the overall evaluation. Weave automatically calculates summaries for common score types (like counts and fractions for boolean scores) and merges these with any custom summary dictionary you provide. You can include metrics not logged as row-level scores, such as total elapsed time or other aggregate measures, in this summary dictionary.

## Example

The following example shows how to use `EvaluationLogger` to log predictions and scores inline with your existing Python code.

The `user_model` model function is defined and applied to a list of inputs. For each example:

- The input and output are logged using `log_prediction`.
- A simple correctness score (`correctness_score`) is logged via `log_score`.
- `finish()` finalizes logging for that prediction.

Finally, `log_summary` records any aggregate metrics and triggers automatic score summarization in Weave.

```python
import weave
from openai import OpenAI
from weave.flow.eval_imperative import EvaluationLogger

# Initialize the logger (model/dataset names are optional metadata)
eval_logger = EvaluationLogger(
    model="my-model",
    dataset="my-dataset"
)

# Example input data (this can be any data structure you want)
eval_samples = [
    {'inputs': {'a': 1, 'b': 2}, 'expected': 3},
    {'inputs': {'a': 2, 'b': 3}, 'expected': 5},
    {'inputs': {'a': 3, 'b': 4}, 'expected': 7},
]

# Example model logic.  This does not have to be decorated with @weave.op,
# but if you do, it will be traced and logged.
@weave.op
def user_model(a: int, b: int) -> int:
    oai = OpenAI()
    _ = oai.chat.completions.create(messages=[{"role": "user", "content": f"What is {a}+{b}?"}], model="gpt-4o-mini")
    return a + b

# Iterate through examples, predict, and log
for sample in eval_samples:
    inputs = sample["inputs"]
    model_output = user_model(**inputs) # Pass inputs as kwargs

    # Log the prediction input and output
    pred_logger = eval_logger.log_prediction(
        inputs=inputs,
        output=model_output
    )

    # Calculate and log a score for this prediction
    expected = sample["expected"]
    correctness_score = model_output == expected
    pred_logger.log_score(
        scorer="correctness", # Simple string name for the scorer
        score=correctness_score
    )

    # Finish logging for this specific prediction
    pred_logger.finish()

# Log a final summary for the entire evaluation.
# Weave auto-aggregates the 'correctness' scores logged above.
summary_stats = {"subjective_overall_score": 0.8}
eval_logger.log_summary(summary_stats)

print("Evaluation logging complete. View results in the Weave UI.")

```

This imperative approach allows for logging traces and evaluation data step-by-step, integrating easily into existing Python loops or workflows without requiring pre-collection of all data points.
