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

### End-to-End Example

Below is a minimal runnable example that mirrors the Quickstart notebook. It
creates a dataset, evaluation, model, and leaderboard all from Python.

```python
import weave
from weave.flow import leaderboard
from weave.trace.ref_util import get_ref

weave.init("leaderboard-demo")

dataset = [
    {"input": "42", "target": "42"},
]

@weave.op
def simple_accuracy(target: str, output: str) -> bool:
    return target == output

evaluation = weave.Evaluation(
    name="Simple Numbers",
    dataset=dataset,
    scorers=[simple_accuracy],
)

@weave.op
def echo_model(input: str) -> str:
    return input

await evaluation.evaluate(echo_model)

spec = leaderboard.Leaderboard(
    name="Accuracy Example",
    description="Compare models on a simple dataset",
    columns=[
        leaderboard.LeaderboardColumn(
            evaluation_object_ref=get_ref(evaluation).uri(),
            scorer_name="simple_accuracy",
            summary_metric_path="true_fraction",
        )
    ],
)

weave.publish(spec)

client = weave.WeaveClient(entity="my-entity", project="leaderboard-demo")
results = leaderboard.get_leaderboard_results(spec, client)
print(results)
```

Calling `weave.publish` prints a link to the new leaderboard so you can open it
in the browser. The implementation uses `leaderboard_path` whenever the object
being published is a `Leaderboard`.

### Python API

Leaderboards are defined in `weave.flow.leaderboard`.

```python
leaderboard.Leaderboard(
    name: str,
    description: str | None = None,
    columns: list[leaderboard.LeaderboardColumn],
)

leaderboard.LeaderboardColumn(
    evaluation_object_ref: str,
    scorer_name: str,
    summary_metric_path: str,
    should_minimize: bool | None = None,
)
```

Retrieve aggregate scores with:

```python
results = leaderboard.get_leaderboard_results(my_leaderboard, client)
```

`get_leaderboard_results` returns a list of `LeaderboardModelResult` objects,
each containing the aggregated metric values for a single model.


### View a Leaderboard in the UI

Your leaderboard is now visible in the Weave UI:

Navigate to **"Leaderboards"** in the sidebar to:

- View and sort by metric values
- Inspect individual model evaluations
- Edit leaderboard structure via the UI or code
  (add/remove columns, choose models, and filter datasets)


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

Each cell shows the result of a specific model on a specific evaluation metric.


###  Example interpretation

The Quickstart notebook constructs a leaderboard with three metrics. One metric sets `should_minimize=True` so lower values rank higher. Here is a simplified definition:

```python
spec = leaderboard.Leaderboard(
    name="Zip Code World Knowledge",
    description="...",
    columns=[
        leaderboard.LeaderboardColumn(
            evaluation_object_ref=get_ref(evaluations[0]).uri(),
            scorer_name="check_concrete_fields",
            summary_metric_path="state_match.true_fraction",
        ),
        leaderboard.LeaderboardColumn(
            evaluation_object_ref=get_ref(evaluations[1]).uri(),
            scorer_name="check_value_fields",
            should_minimize=True,
            summary_metric_path="avg_temp_f_err.mean",
        ),
        leaderboard.LeaderboardColumn(
            evaluation_object_ref=get_ref(evaluations[2]).uri(),
            scorer_name="check_subjective_fields",
            summary_metric_path="correct_known_for.true_fraction",
        ),
    ],
)
```

In the UI each row corresponds to a model and cells are color coded based on the metric value. Selecting a cell opens the evaluation run that produced it.
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

-  [Leaderboard Quickstart Notebook](https://weave-docs.wandb.ai/reference/gen_notebooks/leaderboard_quickstart)
-  [Evaluation API Reference](https://weave-docs.wandb.ai/guides/evaluation/)
-  [Built-in Scorers](https://weave-docs.wandb.ai/guides/evaluation/builtin_scorers)
