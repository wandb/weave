

:::tip[This is a notebook]

<a href="https://colab.research.google.com/github/wandb/weave/blob/master/docs/./notebooks/Intro_to_W&B_Weave_Hello_Eval.ipynb" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/archive/d/d0/20221103151430%21Google_Colaboratory_SVG_Logo.svg" alt="Open In Colab" height="20px" /><div>Open in Colab</div></div></a>

<a href="https://github.com/wandb/weave/blob/master/docs/./notebooks/Intro_to_W&B_Weave_Hello_Eval.ipynb" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/9/91/Octicons-mark-github.svg" alt="View in Github" height="15px" /><div>View in Github</div></div></a>

:::


<img src="http://wandb.me/logo-im-png" width="400" alt="Weights & Biases" />

Weave is a toolkit for developing AI-powered applications.

You can use Weave to:
- Log and debug language model inputs, outputs, and traces.
- Build rigorous, apples-to-apples evaluations for language model use cases.
- Organize all the information generated across the LLM workflow, from experimentation to evaluations to production.

## 🔑 Prerequisites

Install the W&B Weave SDK, OpenAI SDK, and login with your API keys.\
You can find your Weights and Biases API key here: https://wandb.ai/settings#api \
You can generate your OpenAI API key here: https://platform.openai.com/api-keys



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

To iterate on an application, we need a way to evaluate if it's improving.\
To do so, a common practice is to test it against the same set of examples when there is a change. \
Run this sample code to see your first evaluation.


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
Check out our full getting started guide here:\
https://weave-docs.wandb.ai/tutorial-eval \
and when you're ready check out our guide on building a RAB-based application:\
https://weave-docs.wandb.ai/tutorial-rag
