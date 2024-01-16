---
sidebar_position: 1
---

# Quickstart

You will learn:
- How to using tracing to debug inputs & outputs of each function
- How to log models & datasets and see when they're used
- How to use the Weave UI to gain insights

## Installation

`pip install weave`

## Start logging

```python
import weave

weave.init('my-first-project')
```

## Add tracing

```python
import weave
from openai import OpenAI

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
        top_p=1
    )
    return response.choices[0].message.content


```

# Continue Learning!

You have just learned the **basics of Weave**.

## What's next?

Checkout out the tutorial to put them in action and build a production-ready LLM app.