# **Weave by Weights & Biases**

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](http://wandb.me/weave_colab)
[![Stable Version](https://img.shields.io/pypi/v/weave?color=green)](https://pypi.org/project/weave)
[![Download Stats](https://img.shields.io/pypi/dm/weave)](https://pypistats.org/packages/weave)
[![Github Checks](https://img.shields.io/github/check-runs/wandb/weave/master)](https://github.com/wandb/weave)

Weave is a toolkit for developing Generative AI applications, built by [Weights & Biases](https://wandb.ai/)!

---

## Key Features

Weave empowers you to:

- 🔍 **Log and Debug**: Efficiently track language model inputs, outputs, and traces.
- 📊 **Conduct Rigorous Evaluations**: Implement apples-to-apples comparisons for various language model use cases.
- 🗂️ **Organize Your Workflow**: Manage data across the entire LLM workflow—from experimentation to evaluations to production.

Our goal is to introduce rigor, best practices, and composability into the inherently experimental process of developing Generative AI software, while minimizing cognitive overhead.

<div align="center">
  <img src="https://raw.githubusercontent.com/wandb/weave/master/docs/static/weave-ui-example.jpg" width="100%">
</div>

## Documentation

For detailed documentation, visit our [documentation site](https://wandb.me/weave).

## Installation

You can install Weave using :

```bash
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

### Detailed Example
Here’s a comprehensive example that integrates with OpenAI’s API :

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

We welcome contributions! Here’s how you can get involved:

- 🔧 **Current Focus**: We are currently cleaning up the codebase. Much of the code for the "Weave engine" and "Weave boards" is on pause as we prioritize Tracing and Evaluations.

- 🗂️ **Code Organization**:
  - The Weave Tracing code is mainly in `weave/trace` and `weave/trace_server`.
  - The Weave Evaluations code resides in `weave/flow`.

