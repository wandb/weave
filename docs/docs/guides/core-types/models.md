---
sidebar_position: 3
hide_table_of_contents: true
---

# Models

A `Model` is a combination of data (which can include configuration, trained model weights, or other information) and code that defines how the model operates. By structuring your code to be compatible with this API, you benefit from a structured way to version your application so you can more systematically keep track of your experiments.

To create a model in Weave, you need the following:
- `@weave.type` decorator on a class that inherits from `weaveflow.Model`
- type definitions on all attributes
- a typed `predict` function with `@weave.op()` decorator

```python
@weave.type()
class YourModel(weaveflow.Model):
    attribute1: str
    attribute2: int

    @weave.op()
    def predict(self, input_data: str) -> str:
        # Model logic goes here
        return prediction
```

Now, any time this model is used within a function that has a `@weave.op()` decorator, it'll be tracked so you can evaluate how it's performing and inspect model outputs.
