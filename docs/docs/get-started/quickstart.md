---
sidebar_position: 1
hide_table_of_contents: true
---

# Quickstart

Weave is a flexible toolkit to evaluate and iterate on complex LLM-applications. 
Use simple APIs to capture the entire evaluation-driven development workflow. 

- build evaluation datasets
- evaluate model performance
- inspect LLM behaviour

In this quickstart, you will learn how to use tracing to debug inputs & outputs of each function.

## Installation

`pip install weave`

## Track inputs & outputs of functions

- Import weave
- Call `weave.init('project-name')` to start logging
- Add the `@weave.op()` decorator to the functions you want to track

```python
# highlight-next-line
import weave
from openai import OpenAI

# highlight-next-line
@weave.op()
def correct_grammar(sentence: str) -> str:
    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "system",
                "content": "You will be provided with statements, and your task is to convert them to standard English."
            },
            {
            "role": "user",
            "content": sentence
            }
        ],
        temperature=0.7,
        max_tokens=64,
    )
    return response.choices[0].message.content

# highlight-next-line
weave.init('intro-example')
correct_grammar('she no went to the market')
```

Now, every time you call this function, weave will automatically capture the input & output data and log any changes to the code. 
Run this application and your console will output a link to view it within W&B.

:::note
OpenAI calls are automatically tracked with weave but you can add other LLMs easily by wrapping them with `@weave.op()`
:::

## What's next?

Checkout out the tutorial to build a tracked evaluations pipeline so you can iteratively improve your applications.
