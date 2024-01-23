---
sidebar_position: 4
hide_table_of_contents: true
---

# Evaluation

Evaluation-driven development helps you reliably iterate on an application. The `Evaluation` class is designed to assess the performance of a `Model` on a given `Dataset` using specified scoring functions.

```python
from weave.weaveflow import Evaluation

evaluation = Evaluation(
    dataset, scores=[score], example_to_model_input=example_to_model_input
)
evaluation.evaluate(model)
```

## Create an Evaluation

To systematically improve your application, it's very helpful to test your changes against a consistent dataset of potential inputs so that you catch regressions. Using the `Evaluation` class, you can be sure you're comparing apples-to-apples by keeping track of the model and dataset versions used.

### Define an evaluation dataset

First, define a [Dataset](/guides/core-types/datasets) with a collection of examples to be evaluated. These examples are often failure cases that you want to test for, these are similar to unit tests in Test-Driven Development (TDD).

Then, define a list of scoring functions. Each function should take an example and a prediction, returning a dictionary with the scores. `example_to_model_input` is a function that formats each example into a format that the model can process.

Finally, create a model and pass this to `evaluation.evaluate`, which will run `predict` on each example and score the output with each scoring function.

To see this in action, follow the '[Build an Evaluation pipeline](/tutorial-eval)' tutorial.