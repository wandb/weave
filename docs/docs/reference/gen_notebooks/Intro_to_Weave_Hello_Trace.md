

:::tip[This is a notebook]

<a href="https://colab.research.google.com/github/wandb/weave/blob/master/docs/./notebooks/Intro_to_Weave_Hello_Trace.ipynb" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/archive/d/d0/20221103151430%21Google_Colaboratory_SVG_Logo.svg" alt="Open In Colab" height="20px" /><div>Open in Colab</div></div></a>

<a href="https://github.com/wandb/weave/blob/master/docs/./notebooks/Intro_to_Weave_Hello_Trace.ipynb" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/9/91/Octicons-mark-github.svg" alt="View in Github" height="15px" /><div>View in Github</div></div></a>

:::


<img src="http://wandb.me/logo-im-png" width="400" alt="Weights & Biases" />

Weave is a toolkit for developing AI-powered applications.

You can use Weave to:
- Log and debug language model inputs, outputs, and traces.
- Build rigorous, apples-to-apples evaluations for language model use cases.
- Organize all the information generated across the LLM workflow, from experimentation to evaluations to production.

Weave traces let you automatically capture the inputs, outputs, and internal structure of your Python functions—especially useful when working with LLMs. By decorating a function with `@weave.op`, Weave records a rich trace of how your function runs, including any nested operations or external API calls. This makes it easy to debug, understand, and visualize how your code is interacting with language models, all from within your notebook.

To get started, complete the prerequisites. Then, define a Weave model with a predict method, create a labeled dataset and scoring function, and run an evaluation using weave.Evaluation.evaluate().

## 🔑 Prerequisites

Before you can begin tracing in Weave, complete the following prerequisites.

1. Install the W&B Weave SDK and log in with your [API key](https://wandb.ai/settings#api).
2. Install the OpenAI SDK and log in with your [API key](https://platform.openai.com/api-keys).
3. Initialize your W&B project.



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

The following code sample shows how to capture and visualize a trace in Weave using the `@weave.op` decorator. It defines a function called `extract_fruit` that sends a prompt to OpenAI's GPT-4o to extract structured data (fruit, color, and flavor) from a sentence. By decorating the function with `@weave.op`, Weave automatically tracks the function execution, including inputs, outputs, and intermediate steps. When the function is called with a sample sentence, the full trace is saved and viewable in the Weave UI.


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
- Check out the [Quickstart guide](https://weave-docs.wandb.ai/quickstart).
- Learn more about [advanced tracing topics](https://weave-docs.wandb.ai/tutorial-tracing_2).
- Learn more about [tracing in Weave](https://weave-docs.wandb.ai/guides/tracking/tracing)

