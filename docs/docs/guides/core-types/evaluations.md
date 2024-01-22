---
sidebar_position: 4
hide_table_of_contents: true
---

# Evaluation

Evaluation-driven development helps you reliably iterate on an application. The `Evaluation` class is designed to assess the performance of a `Model` on a given `Dataset` using specified scoring functions.

```python
evaluation = evaluate.Evaluation(
    dataset, scores=[score], example_to_model_input=example_to_model_input
)
print(asyncio.run(evaluation.evaluate(model)))
```

## Parameters
`dataset`: A `Dataset` with a collection of examples to be evaluated
`scores`: A list of scoring functions. Each function should take an example and a prediction, returning a dictionary with the scores. 
`example_to_model_input`: A function that formats each example into a format that the model can process.
`model`: pass this to `evaluation.evaluate` to run `predict` on each example and score the output with each scoring function.

