

:::tip[This is a notebook]

<a href="https://colab.research.google.com/github/wandb/weave/blob/master/docs/./notebooks/Intro_to_W&B_Weave_Hello_Trace.ipynb" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/archive/d/d0/20221103151430%21Google_Colaboratory_SVG_Logo.svg" alt="Open In Colab" height="20px" /><div>Open in Colab</div></div></a>

<a href="https://github.com/wandb/weave/blob/master/docs/./notebooks/Intro_to_W&B_Weave_Hello_Trace.ipynb" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/9/91/Octicons-mark-github.svg" alt="View in Github" height="15px" /><div>View in Github</div></div></a>

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
import json
import weave

from getpass import getpass
from openai import OpenAI

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

## 🐝 Run your first trace

Start tracking inputs and outputs of functions by decorating them with `weave.op`().\
Run this sample code to see the new trace.


```python
@weave.op() # 🐝 Decorator to track requests
def extract_fruit(sentence: str) -> dict:
    client = OpenAI()
    system_prompt = "Parse sentences into a JSON dict with keys: fruit, color and flavor."
    response = client.chat.completions.create(
      model="gpt-4o",
      messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": sentence}
      ],
      temperature=0.7,
      response_format={"type": "json_object"}
    )
    extracted = response.choices[0].message.content
    return json.loads(extracted)

sentence = "There are many fruits that were found on the recently discovered planet Goocrux. There are neoskizzles that grow there, which are purple and taste like candy."
extract_fruit(sentence)
```

## 🚀 Looking for more examples?
Check out our full getting started guide here:\
https://weave-docs.wandb.ai/quickstart
