

:::tip[This is a notebook]

<a href="https://colab.research.google.com/github/wandb/weave/blob/master/docs/./notebooks/Intro_to_Weave_Hello_Trace.ipynb" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/archive/d/d0/20221103151430%21Google_Colaboratory_SVG_Logo.svg" alt="Open In Colab" height="20px" /><div>Open in Colab</div></div></a>

<a href="https://github.com/wandb/weave/blob/master/docs/./notebooks/Intro_to_Weave_Hello_Trace.ipynb" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/9/91/Octicons-mark-github.svg" alt="View in Github" height="15px" /><div>View in Github</div></div></a>

:::


# Introduction to Traces

<img src="http://wandb.me/logo-im-png" width="400" alt="Weights & Biases" />

Get started using Weave to:
- Log and debug language model inputs, outputs, and traces
- Build rigorous, apples-to-apples evaluations for language model use cases
- Organize all the information generated across the LLM workflow, from experimentation to evaluations to production

See the full Weave documentation [here](https://wandb.me/weave).

## 🔑 Prerequisites

Before you can begin tracing in Weave, complete the following prerequisites.

1. Install the W&B Weave SDK and log in with your [API key](https://wandb.ai/settings#api), and initialize your project.


```python
# Install dependancies and imports
!pip install wandb weave openai -q

import os
import json
import time
import weave
from getpass import getpass
from openai import OpenAI
from pydantic import BaseModel


# 🔑 Setup your Weights and Biases API key
# Running this cell will prompt you for your API key with `getpass` and will not echo to the terminal.
print("---")
print("You can find your Weights and Biases API key here: https://wandb.ai/settings#api")
os.environ["WANDB_API_KEY"] = getpass("Enter your Weights and Biases API key and hit [ENTER]: ")
print("---")

# 🏠 Enter your W&B project name
weave_client = weave.init("MY_PROJECT_NAME")
```

## 🐝 Run your first trace

The following code sample shows how to capture and visualize a trace in Weave using the `@weave.op` decorator. It defines a function called `extract_fruit` that sends a prompt to OpenAI's GPT-4o to extract structured data (fruit, color, and flavor) from a sentence. By decorating the function with `@weave.op`, Weave automatically tracks the function execution, including inputs, outputs, and intermediate steps. When the function is called with a sample sentence, the full trace is saved and viewable in the Weave UI.

### Create your first traces with a `Hello world!` example and a mock LLM request


```python
# 🐝 Any function is trace-able within Weave
@weave.op()
def hello_world():
  return "Hello world!"

# ▶️ Run the example
hello_world()

# 🔌 Mock function: Emulates an OpenAI request
@weave.op(name="openai.chat.completions.create")
def mock_openai_call(
    messages: list,
    model: str,
    response_format: dict,
    temperature: float
) -> dict:
    model_response = {
        "fruit": "neoskizzles",
        "color": "purple",
        "flavor": "candy"
    }
    mock_response = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(model_response, indent=2),
                    "role": "assistant"
                }
            }
        ],
        "model": model,
        "usage": {
            "completion_tokens": 29,
            "prompt_tokens": 60,
            "total_tokens": 89
        }
    }
    return mock_response

# 🐝 Main function: call our mock LLM call, simulate parsing data, and create a trace
@weave.op()
def extract_fruit(sentence: str) -> dict:
    model = "gpt-4o"
    messages = [
        {
            "role": "system",
            "content": "Parse sentences into a JSON dict with keys: fruit, color and flavor."
        },
        {
            "role": "user",
            "content": sentence
        }
    ]
    response_format = {
        "type": "json_object"
    }
    temperature = 0.7
    llm_response = mock_openai_call(
        messages=messages,
        model=model,
        response_format=response_format,
        temperature=temperature
    )
    response_content = llm_response['choices'][0]['message']['content']
    parsed_response = json.loads(response_content)
    time.sleep(1)
    return parsed_response

# ▶️ Run the example
sentence = "There are many fruits that were found on the recently discovered planet Goocrux. There are neoskizzles that grow there, which are purple and taste like candy."
extract_fruit(sentence)
```

### Try tracking a real-life LLM request using OpenAI

Your can find your OpenAI API key in your [OpenAI platform dashboard](https://platform.openai.com/api-keys).


```python
# 🔑 Setup your OpenAI API key
# Running this cell will prompt you for your API key with `getpass` and will not echo to the terminal.
print("---")
print("You can generate your OpenAI API key here: https://platform.openai.com/api-keys")
os.environ["OPENAI_API_KEY"] = getpass("Enter your OpenAI API key and hit [ENTER]: ")
print("---")

# 🐝 Decorator to trace your LLM call
@weave.op()
def extract_fruit(sentence: str) -> dict:
    client = OpenAI()
    system_prompt = (
        "Parse sentences into a JSON dict with keys: fruit, color and flavor."
    )
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": sentence},
        ],
        temperature=0.7,
        response_format={"type": "json_object"},
    )
    extracted = response.choices[0].message.content
    return json.loads(extracted)

# ▶️ Run the example
sentence = "There are many fruits that were found on the recently discovered planet Goocrux. There are neoskizzles that grow there, which are purple and taste like candy."
extract_fruit(sentence)
```

### Try an agentic request using OpenAI and an agent-loop
In this example we'll create a simple deterministic agent to take an input from a user and write a science fiction story based on it.\
The agent will write an outline, review the outline for quality (and retry as needed), and then write a story based on that outline.


```python
class OutlineCheckerOutput(BaseModel):
    good_quality: bool
    is_scifi: bool

# 🐝 Step 1: Generate a story outline
@weave.op()
def generate_story_outline(input_prompt: str) -> str:
    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "Generate a very short story outline based on the user's input."},
            {"role": "user", "content": input_prompt}
        ],
        temperature=0.7,
    )
    return response.choices[0].message.content

# 🐝 Step 2: Review and check story outline
@weave.op()
def check_outline(outline: str) -> OutlineCheckerOutput:
    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "Read the given story outline, and judge the quality. Also, determine if it is a scifi story. Respond with a JSON object with two boolean fields: good_quality and is_scifi."},
            {"role": "user", "content": outline}
        ],
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    result = json.loads(response.choices[0].message.content)
    return OutlineCheckerOutput(good_quality=result["good_quality"], is_scifi=result["is_scifi"])

# 🐝 Step 3: Write a story based on the story outline
@weave.op()
def write_story(outline: str) -> str:
    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "Write a short story based on the given outline."},
            {"role": "user", "content": outline}
        ],
        temperature=0.7,
    )
    return response.choices[0].message.content

# 🐝 Main function: Orchestrating the loop, will retry a maximum of 5 times before throwing an error.
@weave.op()
def story_writer_agent(input_prompt: str, max_retries: int = 5):
    retries = 0
    while retries < max_retries:
        outline = generate_story_outline(input_prompt)
        check_result = check_outline(outline)

        if check_result.good_quality and check_result.is_scifi:
            story = write_story(outline)
            return story

        retries += 1

    raise RuntimeError("Failed to generate a good sci-fi outline after several tries.")

# ▶️ Run the example
input_prompt = "A story about a futuristic city where robots help humans."
story_writer_agent(input_prompt)
```

## 🚀 Looking for more examples?
- Check out the [Quickstart guide](https://weave-docs.wandb.ai/quickstart).
- Learn more about [advanced tracing topics](https://weave-docs.wandb.ai/tutorial-tracing_2).
- Learn more about [tracing in Weave](https://weave-docs.wandb.ai/guides/tracking/tracing)

