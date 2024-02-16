---
sidebar_position: 1
hide_table_of_contents: true
---

# Quickstart

## Installation

`pip install weave`

## Track inputs & outputs of functions

- Import weave
- Call `weave.init('project-name')` to start logging
- Add the `@weave.op()` decorator to the functions you want to track

In this example, we're using openai so you will need to [add an openai API key](https://platform.openai.com/docs/quickstart/step-2-setup-your-api-key).

```python
# highlight-next-line
import weave
import json
from openai import OpenAI

# highlight-next-line
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

# highlight-next-line
weave.init('intro-example')
sentence = "There are many fruits that were found on the recently discovered planet Goocrux. There are neoskizzles that grow there, which are purple and taste like candy."
extract_fruit(sentence)
```

Now, every time you call this function, weave will automatically capture the input & output data and log any changes to the code. 
Run this application and your console will output a link to view it within W&B.

:::note
Calls made with the openai library are automatically tracked with weave but you can add other LLMs easily by wrapping them with `@weave.op()`
:::

## What's next?

- Follow the [Build an Evaluation pipeline tutorial](/tutorial-eval) to start iteratively improving your applications.
