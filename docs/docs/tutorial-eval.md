---
sidebar_position: 2
hide_table_of_contents: true
---

# Tutorial: Build an Evaluation pipeline

To iterate on an application, we need a way to evaluate if it's improving. To do so, a common practice is to test it against the same dataset when there is a change. Weave has a first-class way to track evaluations with `Dataset`, `Model` & `Evaluation` classes. We have the built the APIs to make minimal assumptions to allow for the flexibility to support a wide array of use-cases.

### Upload a `Dataset`

`Dataset`s enable you to store examples for evaluation. Weave automatically captures when it is used and updates the version when there are changes. `Dataset`s are created with lists of examples, where each example row is a dict.

```python
import weave
from weave import weaveflow

weave.init('intro-example')
dataset = weaveflow.Dataset([
    {'id': '0', 'sentence': "He no like ice cream."},
    {'id': '1', 'sentence': "She goed to the store."},
    {'id': '2', 'sentence': "They plays video games all day."}
])
weave.publish(dataset, 'grammar')
```

In a new script, run this code to publish a `Dataset` and follow the link to view it in the UI.
If you make edits to the `Dataset` in the UI, you can pull the latest version in code using:

```python
dataset = weave.ref('grammar').get()
```

:::note
Checkout the Datasets guide to learn more.
:::

### Build a `Model`

`Model`s store and version information about your system, such as prompts, temperatures, and more.
Like `Dataset`s, Weave automatically captures when it is used and update the version when there are changes.

`Model`s are declared by subclassing `Model` and decorating them with `@weave.type()`. `Model` classes also need a `predict` function definition, which take one example and return the response.

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
model = GrammarModel('you fix grammar')
model.predict('she go to the park')
```

### Evaluate a `Model` on a `Dataset`

`Evaluation`s assess a `Model`s performance on a `Dataset` using specified scoring functions.
The scoring functions take an example row and the resulting prediction and return a dictionary of scores for that example.
`example_to_model_input` tells `evaluate` how to use an input from a given example row of the `Dataset`.

```python
@weave.op()
def score(example, prediction):
    return {'correct': example == prediction['correction']}

@weave.op()
def example_to_model_input(example):
    return example["sentence"]

evaluation = evaluate.Evaluation(
    dataset, scores=[score], example_to_model_input=example_to_model_input
)
evaluation.evaluate(model)
```

## Pulling it all together

```python
import weave
import asyncio
from weave.weaveflow import Model, evaluate

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
            max_tokens=64,
            top_p=1
        )
        return response.choices[0].message.content

@weave.op()
def score(example, prediction):
    return {'correct': example == prediction['correction']}

if __name__ == '__main__':
    weave.init('intro-example')
    model = GrammarModel("You will be provided with statements, and your task is to convert them to standard English.")
    dataset = weave.ref('grammar').get()
    @weave.op()
    def example_to_model_input(example):
        return example["sentence"]

    evaluation = evaluate.Evaluation(
        dataset, scores=[score], example_to_model_input=example_to_model_input
    )
    print(asyncio.run(evaluation.evaluate(model)))
```

## Continue Learning!

You have just built a **production-ready LLM app**.

## What's next?
