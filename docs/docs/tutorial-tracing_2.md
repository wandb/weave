# Track data flows and app metadata

In the [Track LLM inputs & outputs](/quickstart) tutorial, the basics of tracking the inputs and outputs of your LLMs was covered.

In this tutorial you will learn how to:
- **Track data** as it flows though your application
- **Track metadata** at call time

## Tracking nested function calls

LLM-powered applications can contain multiple LLMs calls and additional data processing and validation logic that is important to monitor. Even deep nested call structures common in many apps, Weave will keep track of the parent-child relationships in nested functions as long as `weave.op()` is added to every function you'd like to track. 

Building on our [basic tracing example](/quickstart), we will now add additional logic to count the returned items from our LLM and wrap them all in a higher level function. We'll then add `weave.op()` to trace every function, its call order and its parent-child relationship:

```python
import weave
import json
from openai import OpenAI

client = OpenAI(api_key="...")

# highlight-next-line
@weave.op()
def extract_dinos(sentence: str) -> dict:
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": """Extract any dinorsaur `name`, their `common_name`, \
  names and whether its `diet` is a herbivore or carnivore, in JSON format."""
            },
            {
                "role": "user",
                "content": sentence
            }
            ],
            response_format={ "type": "json_object" }
        )
    return response.choices[0].message.content

# highlight-next-line
@weave.op()
def count_dinos(dino_data: dict) -> int:
    # count the number of items in the returned list
    k = list(dino_data.keys())[0]
    return len(dino_data[k])

# highlight-next-line
@weave.op()
def dino_tracker(sentence: str) -> dict:
    # extract dinosaurs using a LLM
    dino_data = extract_dinos(sentence)
    
    # count the number of dinosaurs returned
    dino_data = json.loads(dino_data)
    n_dinos = count_dinos(dino_data)
    return {"n_dinosaurs": n_dinos, "dinosaurs": dino_data}

# highlight-next-line
weave.init('jurassic-park')

sentence = """I watched as a Tyrannosaurus rex (T. rex) chased after a Triceratops (Trike), \
both carnivore and herbivore locked in an ancient dance. Meanwhile, a gentle giant \
Brachiosaurus (Brachi) calmly munched on treetops, blissfully unaware of the chaos below."""

result = dino_tracker(sentence)
print(result)
```

**Nested functions**

When you run the above code you will see the the inputs and outputs from the two nested functions (`extract_dinos` and `count_dinos`), as well as the automatically-logged OpenAI trace.

![Nested Weave Trace](../static/img/tutorial_tracing_2_nested_dinos.png)


## Tracking metadata

Tracking metadata can be done easily by using the `weave.attributes` context manger and passing it a dictionary of the metadata to track at call time.

Continuing our example from above:

```python
import weave 

weave.init('jurassic-park')

sentence = """I watched as a Tyrannosaurus rex (T. rex) chased after a Triceratops (Trike), \
both carnivore and herbivore locked in an ancient dance. Meanwhile, a gentle giant \
Brachiosaurus (Brachi) calmly munched on treetops, blissfully unaware of the chaos below."""

# track metadata alongside our previously defined function
# highlight-next-line
with weave.attributes({'user_id': 'lukas', 'env': 'production'}):
    result = dino_tracker(sentence)
```

:::note
It's recommended to use metadata tracking to track metadata at run time, e.g. user ids or whether or not the call is part of the development process or is in production etc.

To track system attributes, such as a System Prompt, we recommend using [weave Models](guides/core-types/models)
:::

## What's next?

- Follow the [App Versioning tutorial](/tutorial-weave_models) to capture, version and organize ad-hoc prompt, model, and application changes.
