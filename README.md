# **Weave by Weights & Biases**

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](http://wandb.me/weave_colab)
[![Stable Version](https://img.shields.io/pypi/v/weave?color=green)](https://pypi.org/project/weave)
[![Download Stats](https://img.shields.io/pypi/dm/weave)](https://pypistats.org/packages/weave)
[![Github Checks](https://img.shields.io/github/check-runs/wandb/weave/master
)](https://github.com/wandb/weave)

Weave is a toolkit for developing Generative AI applications, built by [Weights & Biases](https://wandb.ai/).

---

You can use Weave to:

- Log and debug language model inputs, outputs, and traces
- Build rigorous, apples-to-apples evaluations for language model use cases
- Organize all the information generated across the LLM workflow, from experimentation to evaluations to production

Our goal is to bring rigor, best-practices, and composability to the inherently experimental process of developing Generative AI software, without introducing cognitive overhead.

<div align="center">
  <img src="https://raw.githubusercontent.com/wandb/weave/master/docs/static/weave-ui-example.jpg" width="100%">
</div>

## Documentation

Our documentation site can be found [here](https://wandb.me/weave).

## Installation
```
pip install weave
```

## Usage

### Tracing
You can trace any function using `weave.op()` - from api calls to OpenAI, Anthropic, Google AI Studio etc to generation calls from Hugging Face and other open source models to any other validation functions or data transformations in your code you'd like to keep track of.

Decorate all the functions you want to trace, this will generate a trace tree of the inputs and outputs of all your functions:

```python
import weave
weave.init("weave-example")

@weave.op()
def sum_nine(value_one: int):
    return value_one + 9

@weave.op()
def multiply_two(value_two: int):
    return value_two * 2

@weave.op()
def main():
    output = sum_nine(3)
    final_output = multiply_two(output)
    return final_output

main()
```

### Fuller Example 

```python
import weave
import json
from openai import OpenAI

@weave.op()
def extract_fruit(sentence: str) -> dict:
    client = OpenAI()

    response = client.chat.completions.create(
    model="gpt-3.5-turbo-1106",
    messages=[
        {
            "role": "system",
            "content": "You will be provided with unstructured data, and your task is to parse it one JSON dictionary with fruit, color and flavor as keys."
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

weave.init('intro-example')

sentence = "There are many fruits that were found on the recently discovered planet Goocrux. There are neoskizzles that grow there, which are purple and taste like candy."

extract_fruit(sentence)
```

## Contributing

Interested in pulling back the hood or contributing? Awesome, before you dive in, here's what you need to know.

We're in the process of 🧹 cleaning up 🧹. This codebase contains a large amount code for the "Weave engine" and "Weave boards", which we've put on pause as we focus on Tracing and Evaluations.

The Weave Tracing code is mostly in: `weave/trace` and `weave/trace_server`.

The Weave Evaluations code is mostly in `weave/flow`.

