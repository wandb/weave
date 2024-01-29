---
sidebar_position: 2
hide_table_of_contents: true
---

# Tutorial: Build an Evaluation pipeline

To iterate on an application, we need a way to evaluate if it's improving. To do so, a common practice is to test it against the same dataset when there is a change. Weave has a first-class way to track evaluations with `Dataset`, `Model` & `Evaluation` classes. We have built the APIs to make minimal assumptions to allow for the flexibility to support a wide array of use-cases.

### Upload a `Dataset`

`Dataset`s enable you to store examples for evaluation. Weave automatically captures when they are used and updates the `Dataset` version when there are changes. `Dataset`s are created with lists of examples, where each example row is a dict.

```python
import weave
from weave import weaveflow

sentences = ["There are many fruits that were found on the recently discovered planet Goocrux. There are neoskizzles that grow there, which are purple and taste like candy.", 
"Pounits are a bright green color and are more savory than sweet.", 
"Finally, there are fruits called glowls, which have a very sour and bitter taste which is acidic and caustic, and a pale orange tinge to them."]
labels = [
    {'fruit': 'neoskizzles', 'color': 'purple', 'flavor': 'candy'},
    {'fruit': 'pounits', 'color': 'bright green', 'flavor': 'savory'},
    {'fruit': 'glowls', 'color': 'pale orange', 'flavor': 'sour and bitter'}
]

weave.init('intro-example')
dataset = weaveflow.Dataset([
    {'id': '0', 'sentence': sentences[0], 'extracted': labels[0]},
    {'id': '1', 'sentence': sentences[1], 'extracted': labels[1]},
    {'id': '2', 'sentence': sentences[2], 'extracted': labels[2]}
])
dataset_ref = weave.publish(dataset, 'example_labels')
```

In a new script, run this code to publish a `Dataset` and follow the link to view it in the UI.
If you make edits to the `Dataset` in the UI, you can pull the latest version in code using:

```python
dataset = weave.ref('example_labels').get()
```

:::note
Checkout the [Datasets](/guides/core-types/datasets) guide to learn more.
:::

### Build a `Model`

`Model`s store and version information about your system, such as prompts, temperatures, and more.
Like `Dataset`s, Weave automatically captures when they are used and update the version when there are changes.

`Model`s are declared by subclassing `Model` and decorating them with `@weave.type()`. `Model` classes also need a `predict` function definition, which takes one example and returns the response.

:::warning

**Known Issue**: If you are using Google Colab, remove `async` from the following examples.

:::

```python
from weave.weaveflow import Model

@weave.type()
class GrammarModel(Model):
    system_message: str
    model_name: str = "gpt-3.5-turbo"

    @weave.op()
    async def predict(self, sentence: str) -> str:
        from openai import OpenAI
        client = OpenAI()
        response = client.chat.completions.create(
            model=self.model_name,
            messages=[
                {
                    "role": "system",
                    "content": self.system_message
                },
                {
                "role": "user",
                "content": sentence
                }
            ],
            temperature=0.7,
            max_tokens=64
        )
        return response.choices[0].message.content
```

You can instantiate `@weave.type()` objects like this.

```python
model = ExtractFruitsModel("You will be provided with unstructured data, and your task is to parse it one JSON dictionary with fruit, color and flavor as keys.")
sentence = "There are many fruits that were found on the recently discovered planet Goocrux. There are neoskizzles that grow there, which are purple and taste like candy."
await model.predict(sentence)
```

:::note
Checkout the [Models](/guides/core-types/models) guide to learn more.
:::

### Evaluate a `Model` on a `Dataset`

`Evaluation`s assess a `Model`s performance on a `Dataset` using a list of specified scoring functions.
Each scoring function takes an example row and the resulting prediction and return a dictionary of scores for that example.
`example_to_model_input` tells `evaluate` how to use an input from a given example row of the `Dataset`.

Here, we'll add two scoring functions to test the extracted data matches our labels:

```python
from weave.weaveflow import evaluate

@weave.op()
def color_score(example: dict, prediction: dict) -> dict:
    # example is a row from the Dataset, prediction is the output of predict function.
    return {'correct': example['extracted']['color'] == prediction['color']}

@weave.op()
def fruit_name_score(example: dict, prediction: dict) -> dict:
    return {'correct': example['extracted']['fruit'] == prediction['fruit']}

@weave.op()
def example_to_model_input(example: dict) -> str:
    # example is a row from the Dataset, the output of this function should be the input to model.predict.
    return example["sentence"]

evaluation = evaluate.Evaluation(
    dataset, scores=[color_score, fruit_name_score], example_to_model_input=example_to_model_input
)
await evaluation.evaluate(model)
```

## Pulling it all together

```python
import weave
import asyncio
from weave.weaveflow import Model, Evaluation, Dataset
import json

# We create a model class with one predict function. 
# All inputs, predictions and parameters are automatically captured for easy inspection.
@weave.type()
class ExtractFruitsModel(Model):
    system_message: str
    model_name: str = "gpt-3.5-turbo-1106"

    @weave.op()
    async def predict(self, sentence: str) -> str:
        from openai import OpenAI
        client = OpenAI()
        response = client.chat.completions.create(
            model=self.model_name,
            messages=[
                {
                    "role": "system",
                    "content": self.system_message
                },
                {
                    "role": "user",
                    "content": sentence
                }
            ],
            temperature=0.7,
            response_format={ "type": "json_object" }
        )
        extracted = response.choices[0].message.content
        return json.loads(extracted)

# We call init to begin capturing data in the project, intro-example.
weave.init('intro-example')

# We create our model with our system prompt.
model = ExtractFruitsModel("You will be provided with unstructured data, and your task is to parse it one JSON dictionary with fruit, color and flavor as keys.")
sentences = ["There are many fruits that were found on the recently discovered planet Goocrux. There are neoskizzles that grow there, which are purple and taste like candy.", 
"Pounits are a bright green color and are more savory than sweet.", 
"Finally, there are fruits called glowls, which have a very sour and bitter taste which is acidic and caustic, and a pale orange tinge to them."]
labels = [
    {'fruit': 'neoskizzles', 'color': 'purple', 'flavor': 'candy'},
    {'fruit': 'pounits', 'color': 'bright green', 'flavor': 'savory'},
    {'fruit': 'glowls', 'color': 'pale orange', 'flavor': 'sour and bitter'}
]
# Here, we track a Dataset in weave. This makes it easy to 
# automatically score a given model and compare outputs from different configurations.
dataset = Dataset([
    {'id': '0', 'sentence': sentences[0], 'extracted': labels[0]},
    {'id': '1', 'sentence': sentences[1], 'extracted': labels[1]},
    {'id': '2', 'sentence': sentences[2], 'extracted': labels[2]}
])
dataset_ref = weave.publish(dataset, 'example_labels')
# If you have already published the Dataset, you can run:
# dataset = weave.ref('example_labels').get()

# We define two scoring functions to compare our model predictions with a ground truth label.
@weave.op()
def color_score(example: dict, prediction: dict) -> dict:
    # example is a row from the Dataset, prediction is the output of predict function
    return {'correct': example['extracted']['color'] == prediction['color']}

@weave.op()
def fruit_name_score(example: dict, prediction: dict) -> dict:
    return {'correct': example['extracted']['fruit'] == prediction['fruit']}

@weave.op()
def example_to_model_input(example: dict) -> str:
    # example is a row from the Dataset, the output of this function should be the input to model.predict.
    return example["sentence"]

# Finally, we run an evaluation of this model. 
# This will generate a prediction for each input example, and then score it with each scoring function.
evaluation = Evaluation(
    dataset, scores=[color_score, fruit_name_score], example_to_model_input=example_to_model_input
)
print(asyncio.run(evaluation.evaluate(model)))
# if you're in a Jupyter Notebook, run:
# await evaluation.evaluate(model)
```
