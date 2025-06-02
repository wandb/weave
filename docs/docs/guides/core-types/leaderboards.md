# Leaderboards

Weave Leaderboards make it easy to evaluate and compare multiple models against multiple criteria, whether you're testing raw accuracy, numerical prediction quality, or subjective reasoning. They’re ideal for:

- Prompt engineering comparisons
- RAG and fine-tuned model evaluation
- Tracking performance over time
- Aligning team-wide benchmarks

:::tip
Looking for a runnable example? See the [Leaderboard Quickstart Notebook](https://weave-docs.wandb.ai/reference/gen_notebooks/leaderboard_quickstart).
:::

## Build a Leaderboard

### Set up

1. First, create a test dataset. You can either [use the built-in Weave `Dataset`](./datasets.md), or create a list of objects:

    ```python
    dataset = [
        {"input": "some_input", "target": "expected_output"},
        # Add your data rows here
    ]
    ```

2. Create an [`Evaluation`](../core-types/evaluations.md) that uses the dataset:

    ```python
    evaluation = Evaluation(
        name="My Evaluation",
        dataset=dataset,
        scorers=[...],  # Define below
    )
    ```

3. Define the [scoring function(s)](../evaluation/scorers.md) for your Evaluation: 

    ```python
    @weave.op
    def simple_accuracy(target, output):
        return target == output
    ```

4. Define any number of models and run them against the evaluation:

    ```python
    @weave.op
    def my_model(input):
        return some_output_based_on(input)

    await evaluation.evaluate(my_model)
    ```

All evaluations are logged and tracked in Weave automatically.

### Create the Leaderboard

Once you have evaluations, define a leaderboard that compares them across one or more metrics.

```python
from weave.flow import leaderboard
from weave.trace.ref_util import get_ref

my_leaderboard = leaderboard.Leaderboard(
    name="My Model Comparison",
    description="This leaderboard compares several models on key tasks.",
    columns=[
        leaderboard.LeaderboardColumn(
            evaluation_object_ref=get_ref(evaluation).uri(),
            scorer_name="simple_accuracy",
            summary_metric_path="true_fraction",  # Adjust based on your scorer's output
        )
    ]
)

weave.publish(my_leaderboard)
```


### View a Leaderboard in the UI

Your leaderboard is now visible in the Weave UI:

Navigate to **"Leaderboards"** in the sidebar to:

- View and sort by metric values
- Inspect individual model evaluations
- Edit leaderboard structure via the UI or code


## Interpret the Leaderboard

Once your leaderboard is defined and published, the Weave UI presents a side-by-side comparison of models, datasets, and evaluation metrics — all in one table.

### Rows: Models

Each row represents a model you’ve evaluated. The model names are pulled from the `@weave.op` function names you used during evaluation.

:::tip
Use meaningful model names like `gpt_4_tuned_v1` or `no_rag_baseline` to make results easier to scan.
:::

### Columns: Metrics

Each column represents a specific combination of:

- ✅ **Evaluation** (e.g., a dataset or task)
- ✅ **Scorer** (a function that computes correctness/error)
- ✅ **Summary Metric** (a field path like `"true_fraction"` or `"mean"`)

You configure these using `LeaderboardColumn`.

### Metric values

Each cell shows the result of a specific model on a specific evaluation metric.

#### UI features:

* **Color-coded performance**: Green = better performance (e.g., higher accuracy or lower error).
* **Sort arrows**: Click column headers to sort models by metric value.
* **Hover/Click**: See the underlying evaluation run and raw outputs.

###  Minimize vs Maximize

Metrics are ranked based on what you specify:

* `should_minimize=True` → Lower is better (e.g., loss, error)
* Default (`False`) → Higher is better (e.g., accuracy, BLEU, recall)

This affects how rows are ranked and color-highlighted.

###  Descriptions & Metadata

* Add markdown-formatted descriptions to your leaderboard and column definitions for clarity.
* Evaluation names and scorer versions are shown inline — helpful for version tracking.

###  Example Interpretation

Imagine this simplified leaderboard:

| Model     | Accuracy (↑) | Latency (↓) |
| --------- | ------------ | ----------- |
| `model_a` | 92%         | 150ms     |
| `model_b` | 88%        | 75ms       |

* `model_a` performs better on accuracy but is slower.
* `model_b` is faster but less accurate — a trade-off.
* Color-coding and arrows quickly show what’s better and why.

---

###  Best practices

| Practice                         | Why It Helps                                |
| -------------------------------- | ------------------------------------------- |
| Use descriptive scorer names     | Clarifies what each metric is measuring     |
| Normalize your metric outputs    | Keeps values interpretable across columns   |
| Use `should_minimize` for errors | Ensures correct ranking behavior            |
| Include markdown descriptions    | Improves readability in the UI              |
| Click into cell results          | Inspect underlying model outputs and traces |

---

##  Learn more

*  [Leaderboard Quickstart Notebook](https://weave-docs.wandb.ai/reference/gen_notebooks/leaderboard_quickstart)
*  [Evaluation API Reference](https://weave-docs.wandb.ai/guides/evaluation/)
*  [Built-in Scorers](https://weave-docs.wandb.ai/guides/evaluation/builtin_scorers)
