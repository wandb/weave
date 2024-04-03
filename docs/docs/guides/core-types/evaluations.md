---
sidebar_position: 4
hide_table_of_contents: true
---

# Evaluation

Evaluation-driven development helps you reliably iterate on an application. The `Evaluation` class is designed to assess the performance of a `Model` on a given `Dataset` or set of examples using specified scoring functions.

```python
from weave import Evaluation

evaluation = Evaluation(
    dataset=dataset, scorers=[score]
)
evaluation.evaluate(model)
```

## Create an Evaluation

To systematically improve your application, it's very helpful to test your changes against a consistent dataset of potential inputs so that you catch regressions. Using the `Evaluation` class, you can be sure you're comparing apples-to-apples by keeping track of the model and dataset versions used.

### Define an evaluation dataset

First, define a [Dataset](/guides/core-types/datasets) or list of examples with a collection of examples to be evaluated. These examples are often failure cases that you want to test for, these are similar to unit tests in Test-Driven Development (TDD).

### Define a scoring function

Then, define a list of scoring functions. Each function should take an example and a prediction, returning a dictionary with the scores. 

```
def match(answer: dict, model_output: dict ) -> dict:
    return {'match': answer['expected_text'] == model_output['generated_text']}
```

### Evaluate

Finally, create a model and pass this to `evaluation.evaluate`, which will run `predict` on each example and score the output with each scoring functions.

To see this in action, follow the '[Build an Evaluation pipeline](/tutorial-eval)' tutorial.
