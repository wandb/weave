

:::tip[This is a notebook]

<a href="https://colab.research.google.com/github/wandb/weave/blob/master/docs/./notebooks/Intro_to_Weave_Hello_Eval.ipynb" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/archive/d/d0/20221103151430%21Google_Colaboratory_SVG_Logo.svg" alt="Open In Colab" height="20px" /><div>Open in Colab</div></div></a>

<a href="https://github.com/wandb/weave/blob/master/docs/./notebooks/Intro_to_Weave_Hello_Eval.ipynb" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/9/91/Octicons-mark-github.svg" alt="View in Github" height="15px" /><div>View in Github</div></div></a>

:::


<img src="http://wandb.me/logo-im-png" width="400" alt="Weights & Biases" />

Weave is a toolkit for developing AI-powered applications.

You can use Weave to:
- Log and debug language model inputs, outputs, and traces.
- Build rigorous, apples-to-apples evaluations for language model use cases.
- Organize all the information generated across the LLM workflow, from experimentation to evaluations to production.

This notebook demonstrates how to evaluate a model or function using Weave’s Evaluation API. Evaluation is a core concept in Weave that helps you measure and iterate on your application by running it against a dataset of examples and scoring the outputs using custom-defined functions. You'll define a simple model, create a labeled dataset, track scoring functions with `@weave.op`, and run an evaluation that automatically tracks results in the Weave UI. This forms the foundation for more advanced workflows like LLM fine-tuning, regression testing, or model comparison.

To get started, complete the prerequisites. Then, define a Weave `Model` with a `predict` method, create a labeled dataset and scoring function, and run an evaluation using `weave.Evaluation.evaluate()`.

## 🔑 Prerequisites

Before you can run a Weave evaluation, complete the following prerequisites.

1. Install the W&B Weave SDK and log in with your [API key](https://wandb.ai/settings#api).
2. Install the OpenAI SDK and log in with your [API key](https://platform.openai.com/api-keys).
3. Initialize your W&B project.


```python
# Install dependancies and imports
!pip install wandb weave openai -q

import os
import openai
import json
import weave

from getpass import getpass
from openai import OpenAI
from pydantic import BaseModel

# 🔑 Setup your API keys
# Running this cell will prompt you for your API key with `getpass` and will not echo to the terminal.
#####
print("---")
print("You can find your Weights and Biases API key here: https://wandb.ai/settings#api")
os.environ["WANDB_API_KEY"] = getpass('Enter your Weights and Biases API key: ')
print("---")
print("You can generate your OpenAI API key here: https://platform.openai.com/api-keys")
os.environ["OPENAI_API_KEY"] = getpass('Enter your OpenAI API key: ')
print("---")
#####

# 🏠 Enter your W&B project name
weave_client = weave.init('MY_PROJECT_NAME') # 🐝 Your W&B project name
```

## 🐝 Run your first evaluation

The following code sample shows how to evaluate an LLM using Weave’s `Model` and `Evaluation` APIs. First, define a Weave model by subclassing `weave.Model`, specifying the model name and prompt format, and tracking a `predict` method with `@weave.op`. The `predict` method sends a prompt to OpenAI and parses the response into a structured output using a Pydantic schema (`FruitExtract`). Then, create a small evaluation dataset consisting of input sentences and expected targets. Next, define a custom scoring function (also tracked using `@weave.op`) that compares the model’s output to the target label. Finally,  wrap everything in a `weave.Evaluation`, specifying your dataset and scorers, and call `evaluate()` to run the evaluation pipeline asynchronously.


```python
# 1. Construct a Weave model
class FruitExtract(BaseModel):
    fruit: str
    color: str
    flavor: str

class ExtractFruitsModel(weave.Model):
    model_name: str
    prompt_template: str

    @weave.op()
    def predict(self, sentence: str) -> dict:
        client = OpenAI()

        response = client.beta.chat.completions.parse(
            model=self.model_name,
            messages=[
                {"role": "user", "content": self.prompt_template.format(sentence=sentence)}
            ],
            response_format=FruitExtract
        )
        result = response.choices[0].message.parsed
        return result

model = ExtractFruitsModel(
    name='gpt4o',
    model_name='gpt-4o',
    prompt_template='Extract fields ("fruit": <str>, "color": <str>, "flavor": <str>) as json, from the following text : {sentence}'
)

# 2. Collect some samples
sentences = [
    "There are many fruits that were found on the recently discovered planet Goocrux. There are neoskizzles that grow there, which are purple and taste like candy.",
    "Pounits are a bright green color and are more savory than sweet.",
    "Finally, there are fruits called glowls, which have a very sour and bitter taste which is acidic and caustic, and a pale orange tinge to them."
]
labels = [
    {'fruit': 'neoskizzles', 'color': 'purple', 'flavor': 'candy'},
    {'fruit': 'pounits', 'color': 'green', 'flavor': 'savory'},
    {'fruit': 'glowls', 'color': 'orange', 'flavor': 'sour, bitter'}
]
examples = [
    {'id': '0', 'sentence': sentences[0], 'target': labels[0]},
    {'id': '1', 'sentence': sentences[1], 'target': labels[1]},
    {'id': '2', 'sentence': sentences[2], 'target': labels[2]}
]

# 3. Define a scoring function for your evaluation
@weave.op()
def fruit_name_score(target: dict, output: FruitExtract) -> dict:
    target_flavors = [f.strip().lower() for f in target['flavor'].split(',')]
    output_flavors = [f.strip().lower() for f in output.flavor.split(',')]
    # Check if any target flavor is present in the output flavors
    matches = any(tf in of for tf in target_flavors for of in output_flavors)
    return {'correct': matches}

# 4. Run your evaluation
evaluation = weave.Evaluation(
    name='fruit_eval',
    dataset=examples, scorers=[fruit_name_score],
)
await evaluation.evaluate(model)
```

## 🚀 Looking for more examples?

- Learn how to build an [evlauation pipeline end-to-end](https://weave-docs.wandb.ai/tutorial-eval). 
- Learn how to evaluate a [RAG application by building](https://weave-docs.wandb.ai/tutorial-rag).
