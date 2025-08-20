---
title: Custom Model Cost
---


:::tip[This is a notebook]

<a href="https://colab.research.google.com/github/wandb/weave/blob/master/docs/./notebooks/custom_model_cost.ipynb" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/archive/d/d0/20221103151430%21Google_Colaboratory_SVG_Logo.svg" alt="Open In Colab" height="20px" /><div>Open in Colab</div></div></a>

<a href="https://github.com/wandb/weave/blob/master/docs/./notebooks/custom_model_cost.ipynb" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/9/91/Octicons-mark-github.svg" alt="View in Github" height="15px" /><div>View in Github</div></div></a>

:::



<!--- @wandbcode{prompt-optim-notebook} -->

# Setting up a custom cost model

Weave calculates costs based on the number of tokens used and the model used.
Weave grabs this usage and model from the output and associates them with the call.

Let's set up a simple custom model, that calculates its own token usage, and stores that in weave.

## Set up the environment

We install and import all needed packages.
We set `WANDB_API_KEY` in our env so that we may easily login with `wandb.login()` (this should be given to the colab as a secret).

We set the project in W&B we want to log this into in `name_of_wandb_project`.

**_NOTE:_** `name_of_wandb_project` may also be in the format of `{team_name}/{project_name}` to specify a team to log the traces into.

We then fetch a weave client by calling `weave.init()`


```python
%pip install wandb weave datetime --quiet
```


```python
import os

import wandb
from google.colab import userdata

import weave

os.environ["WANDB_API_KEY"] = userdata.get("WANDB_API_KEY")
name_of_wandb_project = "custom-cost-model"

wandb.login()
```


```python
weave_client = weave.init(name_of_wandb_project)
```

## Setting up a model with weave



```python
from weave import Model


class YourModel(Model):
    attribute1: str
    attribute2: int

    def simple_token_count(self, text: str) -> int:
        return len(text) // 3

    # This is a custom op that we are defining
    # It takes in a string, and outputs a dict with the usage counts, model name, and the output
    @weave.op()
    def custom_model_generate(self, input_data: str) -> dict:
        # Model logic goes here
        # Here is where you would have a custom generate function
        prediction = self.attribute1 + " " + input_data

        # Usage counts
        prompt_tokens = self.simple_token_count(input_data)
        completion_tokens = self.simple_token_count(prediction)

        # We return a dictionary with the usage counts, model name, and the output
        # Weave will automatically associate this with the trace
        # This object {usage, model, output} matches the output of a OpenAI Call
        return {
            "usage": {
                "input_tokens": prompt_tokens,
                "output_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
            "model": "your_model_name",
            "output": prediction,
        }

    # In our predict function we call our custom generate function, and return the output.
    @weave.op()
    def predict(self, input_data: str) -> dict:
        # Here is where you would do any post processing of the data
        outputs = self.custom_model_generate(input_data)
        return outputs["output"]
```

## Add a custom cost

Here we add a custom cost, and now that we have a custom cost, and our calls have usage, we can fetch the calls with `include_cost` and our calls with have costs under `summary.weave.costs`.


```python
model = YourModel(attribute1="Hello", attribute2=1)
model.predict("world")

# We then add a custom cost to our project
weave_client.add_cost(
    llm_id="your_model_name", prompt_token_cost=0.1, completion_token_cost=0.2
)

# We can then query for the calls, and with include_costs=True
# we receive the costs back attached to the calls
calls = weave_client.get_calls(filter={"trace_roots_only": True}, include_costs=True)

list(calls)
```
