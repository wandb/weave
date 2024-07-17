---
sidebar_position: 1
hide_table_of_contents: true
---

# App versioning

Tracking the [inputs, outputs, metadata](/tutorial-tracing_1) as well as [data flowing through your app](/tutorial-tracing_2) is critical to understanding the performance of your system. However **versioning your app over time** is also critial to understand how modifications to your code or app attributes change your outputs. Weave's `Model` class is how these changes can be tracked in Weave. 

In this tutorial you'll learn:

- How to use Weave `Model` to track and version your app and its attributes.
- How to export, modify and re-use a Weave `Model` already logged.

## Using `weave.Model`

Using Weave `Model`s means that attributes such as model vendor ids, prompts, temperature, and more are stored and versioned when they change.

To create a `Model` in Weave, you need the following:

- a class that inherits from `weave.Model`
- type definitions on all class attributes
- a typed `invoke` function with the `@weave.op()` decorator

When you change the class attributes or the code that defines your model, **these changes will be logged and the version will be updated**. This ensures that you can compare the generations across different versions of your app.

In the example below, the **model name, temperature and system prompt will be tracked and versioned**:

```python
import json
from openai import OpenAI

import weave
from weave import Model as WeaveModel

@weave.op()
def extract_dinos(wmodel: WeaveModel, sentence: str) -> dict:
    response = client.chat.completions.create(
        model=wmodel.model_name,
        temperature=wmodel.temperature,
        messages=[
            {
                "role": "system",
                "content": wmodel.system_prompt
            },
            {
                "role": "user",
                "content": sentence
            }
            ],
            response_format={ "type": "json_object" }
        )
    return response.choices[0].message.content

# Sub-class with a weave.Model
# highlight-next-line
class ExtractDinos(WeaveModel):
    model_name: str
    temperature: float
    system_prompt: str
    
    # Ensure your function is called `invoke` or `predict`
    # highlight-next-line
    @weave.op()
    # highlight-next-line
    def invoke(self, sentence: str) -> dict:
        dino_data  = extract_dinos(self, sentence)
        return json.loads(dino_data)
```

**A note on using `weave.Model`:**
- You can use `predict` instead of `invoke` for the name of the function in your Weave `Model` if you prefer.
- If you want other class methods to be tracked by weave they need to be wrapped in `weave.op()`
- Attributes starting with an underscore are ignored by weave and won't be logged


Now you can instantiate and call the model with `invoke`:

```python
weave.init('jurassic-park')
client = OpenAI(api_key="...")

system_prompt = """Extract any dinorsaur `name`, their `common_name`, \
names and whether its `diet` is a herbivore or carnivore, in JSON format."""

# highlight-next-line
dinos = ExtractDinos(
    model_name='gpt-4o',
    temperature=0.4,
    system_prompt=system_prompt
)

sentence = """I watched as a Tyrannosaurus rex (T. rex) chased after a Triceratops (Trike), \
both carnivore and herbivore locked in an ancient dance. Meanwhile, a gentle giant \
Brachiosaurus (Brachi) calmly munched on treetops, blissfully unaware of the chaos below."""

# highlight-next-line
result = dinos.invoke(sentence)
print(result)
```

## Exporting and re-using a logged `weave.Model`

info

Some undocumented Model things:
custom init - pydantic doesn’t like you changing attributes in a custom init, there’s a workaround where you have to call super.init after
Underscore attributes are ignored by weave (more of a gotcha)
predict can be invoke and something else I can’t remember
you have to wrap additional methods in weave.op
You can “get” them - this is only mentioned in the Objects page
