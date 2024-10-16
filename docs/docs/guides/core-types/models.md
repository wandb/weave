# Models

A `Model` is a combination of data (which can include configuration, trained model weights, or other information) and code that defines how the model operates. By structuring your code to be compatible with this API, you benefit from a structured way to version your application so you can more systematically keep track of your experiments.

To create a model in Weave, you need the following:

- a class that inherits from `weave.Model`
- type definitions on all attributes
- a typed `predict` function with `@weave.op()` decorator

```python
from weave import Model
import weave

class YourModel(Model):
    attribute1: str
    attribute2: int

    @weave.op()
    def predict(self, input_data: str) -> dict:
        # Model logic goes here
        prediction = self.attribute1 + ' ' + input_data
        return {'pred': prediction}
```

You can call the model as usual with:

```python
import weave
weave.init('intro-example')

model = YourModel(attribute1='hello', attribute2=5)
model.predict('world')
```

This will track the model settings along with the inputs and outputs anytime you call `predict`.

## Automatic versioning of models

When you change the attributes or the code that defines your model, these changes will be logged and the version will be updated.
This ensures that you can compare the predictions across different versions of your model. Use this to iterate on prompts or to try the latest LLM and compare predictions across different settings.

For example, here we create a new model:

```python
import weave
weave.init('intro-example')

model = YourModel(attribute1='howdy', attribute2=10)
model.predict('world')
```

After calling this, you will see that you now have two versions of this Model in the UI, each with different tracked calls.

## Serve models

To serve a model, you can easily spin up a FastAPI server by calling:

```bash
weave serve <your model ref>
```

For additional instructions, see [serve](/guides/tools/serve).

## Track production calls

To separate production calls, you can add an additional attribute to the predictions for easy filtering in the UI or API.

```python
with weave.attributes({'env': 'production'}):
    model.predict('world')
```
