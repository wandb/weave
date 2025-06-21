---
title: Introduction Notebook
---


:::tip[This is a notebook]

<a href="https://colab.research.google.com/github/wandb/weave/blob/master/docs/intro_notebook.ipynb" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/archive/d/d0/20221103151430%21Google_Colaboratory_SVG_Logo.svg" alt="Open In Colab" height="20px" /><div>Open in Colab</div></div></a>

<a href="https://github.com/wandb/weave/blob/master/docs/intro_notebook.ipynb" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/9/91/Octicons-mark-github.svg" alt="View in Github" height="15px" /><div>View in Github</div></div></a>

:::



<!--- @wandbcode{intro-colab} -->

# 🏃‍♀️ Quickstart

You can use Weave to:

- Log and debug language model inputs, outputs, and traces
- Build rigorous, apples-to-apples evaluations for language model use cases
- Organize all the information generated across the LLM workflow, from experimentation to evaluations to production

For more information, see the [Weave documentation](/docs/docs/introduction.md).


## Install `weave` and login

Before you begin, install the required libraries.

For this example, you'll need to [add an OpenAI API key](https://platform.openai.com/docs/quickstart/step-2-setup-your-api-key).



```python
%%capture
!pip install weave openai set-env-colab-kaggle-dotenv
```


```python
# Set your OpenAI API key
from set_env import set_env

# Put your OPENAI_API_KEY in the secrets panel to the left 🗝️
_ = set_env("OPENAI_API_KEY")
# os.environ["OPENAI_API_KEY"] = "sk-..." # alternatively, put your key here

PROJECT = "weave-intro-notebook"
```

# Track inputs & outputs of functions

Weave allows users to track function calls: the code, inputs, outputs, and even LLM tokens & costs! In the following sections we will cover:

* Custom functions
* Vendor integrations
* Nested function Calling
* Error tracking

:::important
In all cases, we will import `weave` and initialize a Weave project.

```python
import weave                    # import the weave library
weave.init('project-name')      # initialize tracking for a specific W&B project
```
:::

## Vendor integrations 

Here, we're automatically tracking all calls to `openai`. We [automatically track a lot of LLM libraries](/docs/docs/guides/integrations/index.md#llm-providers), but it's really easy to add support for whatever LLM you're using, as you'll see below. 


```python
from openai import OpenAI

import weave

weave.init(PROJECT)

client = OpenAI()
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {
            "role": "system",
            "content": "You are a grammar checker, correct the following user input.",
        },
        {"role": "user", "content": "That was so easy, it was a piece of pie!"},
    ],
    temperature=0,
)
generation = response.choices[0].message.content
print(generation)
```

![](../../media/intro/1.png)

## Track custom functions

Add the `@weave.op` decorator to the functions you want to track


```python
import weave

weave.init(PROJECT)


@weave.op()
def strip_user_input(user_input):
    return user_input.strip()


result = strip_user_input("    hello    ")
print(result)
```

![](../../media/intro/2.png)

## Track nested functions

Now that you've seen the basics, let's combine all of the above and track some deeply nested functions alongside LLM calls.



![](../../media/intro/3.png)


```python
from openai import OpenAI

import weave

weave.init(PROJECT)


@weave.op()
def strip_user_input(user_input):
    return user_input.strip()


@weave.op()
def correct_grammar(user_input):
    client = OpenAI()

    stripped = strip_user_input(user_input)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "You are a grammar checker, correct the following user input.",
            },
            {"role": "user", "content": stripped},
        ],
        temperature=0,
    )
    return response.choices[0].message.content


result = correct_grammar("   That was so easy, it was a piece of pie!    ")
print(result)
```

After adding `weave.op` and calling the function, visit the link and see it tracked within your project.

💡 We automatically track your code, have a look at the code tab!

## Track errors

When your code crashes, you can use Weave to pinoint the root cause, making it especially helpful for tracking down issues like JSON parsing errors that can arise when handling LLM responses.

![](../../media/intro/4.png)


```python
import json

from openai import OpenAI

import weave

weave.init(PROJECT)


@weave.op()
def strip_user_input(user_input):
    return user_input.strip()


@weave.op()
def correct_grammar(user_input):
    client = OpenAI()

    stripped = strip_user_input(user_input)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "You are a grammar checker, correct the following user input.",
            },
            {"role": "user", "content": stripped},
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content)


result = correct_grammar("   That was so easy, it was a piece of pie!    ")
print(result)
```

## Track objects

Experimentation can become challenging when your app has many moving parts. With `weave.Objects`, you can capture and organize key experimental details such as your system prompt, model choice, and more. This makes it easier to manage and compare different iterations of your app.

In this section, we’ll cover:

* General object tracking
* Tracking models
* Tracking datasets

### General object tracking

Just like you version your code, it's often valuable to track and version your data. For example, you can define a `SystemPrompt(weave.Object)` that can be easily shared and reused across your team.

![](../../media/intro/5.png)


```python
import weave

weave.init(PROJECT)


class SystemPrompt(weave.Object):
    prompt: str


system_prompt = SystemPrompt(
    prompt="You are a grammar checker, correct the following user input."
)
weave.publish(system_prompt)
```

## Track models

Models are a common object type in LLM app development. Weave provides a dedicated class for them: `weave.Model`. The only requirement is to define a `predict` method that encapsulates the logic.

![](../../media/intro/6.png)


```python
from openai import OpenAI

import weave

weave.init(PROJECT)


class OpenAIGrammarCorrector(weave.Model):
    # Properties are entirely user-defined
    openai_model_name: str
    system_message: str

    @weave.op()
    def predict(self, user_input):
        client = OpenAI()
        response = client.chat.completions.create(
            model=self.openai_model_name,
            messages=[
                {"role": "system", "content": self.system_message},
                {"role": "user", "content": user_input},
            ],
            temperature=0,
        )
        return response.choices[0].message.content


corrector = OpenAIGrammarCorrector(
    openai_model_name="gpt-4o-mini",
    system_message="You are a grammar checker, correct the following user input.",
)

result = corrector.predict("     That was so easy, it was a piece of pie!       ")
print(result)
```

## Track datasets

Similar to models, a `weave.Dataset` object helps track, organize, and version dataset objects.

![](../../media/intro/7.png)


```python
dataset = weave.Dataset(
    name="grammar-correction",
    rows=[
        {
            "user_input": "   That was so easy, it was a piece of pie!   ",
            "expected": "That was so easy, it was a piece of cake!",
        },
        {"user_input": "  I write good   ", "expected": "I write well"},
        {
            "user_input": "  GPT-4 is smartest AI model.   ",
            "expected": "GPT-4 is the smartest AI model.",
        },
    ],
)

weave.publish(dataset)
```

Notice that we saved a versioned `GrammarCorrector` object that captures the configurations you're experimenting with.

## Retrieve published objects and ops

You can programmatically publish and retrieve objects to Weave. You can even call functions from your retrieved objects!

![](../../media/intro/8.png)


```python
import weave

weave.init(PROJECT)

corrector = OpenAIGrammarCorrector(
    openai_model_name="gpt-4o-mini",
    system_message="You are a grammar checker, correct the following user input.",
)

ref = weave.publish(corrector)
print(ref.uri())
```

![](../../media/intro/9.png)


```python
import weave

weave.init(PROJECT)

# Note: this url is available from the UI after publishing the object!
ref_url = f"weave:///{ref.entity}/{PROJECT}/object/{ref.name}:{ref.digest}"
fetched_collector = weave.ref(ref_url).get()

# Notice: this object was loaded from remote location!
result = fetched_collector.predict("That was so easy, it was a piece of pie!")

print(result)
```

# Evaluations

Evaluation-driven development helps you reliably iterate on an application. The [`Evaluation` class](/docs/docs/guides/core-types/evaluations.md) is designed to assess the performance of a `Model` on a given `Dataset` or set of examples using scoring functions.

![](../../media/intro/10.png)


```python
import weave
from weave import Evaluation


# Define any custom scoring function
@weave.op()
def exact_match(expected: str, output: dict) -> dict:
    # Here is where you'd define the logic to score the model output
    return {"match": expected == output}


# Score your examples using scoring functions
evaluation = Evaluation(
    dataset=dataset,  # can be a list of dictionaries or a weave.Dataset object
    scorers=[exact_match],  # can be a list of scoring functions
)

# Start tracking the evaluation
weave.init(PROJECT)
# Run the evaluation
summary = await evaluation.evaluate(corrector)  # can be a model or simple function
```
