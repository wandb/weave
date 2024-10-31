# Prompts

Creating, evaluating, and refining prompts is a core activity for AI engineers.
Small changes to a prompt can have big impacts on your application's behavior.
Weave lets you create prompts, save and retrieve them, and evolve them over time.
Some of the benefits of Weave's prompt management system are:

- Unopinionated core, with a batteries-included option for rapid development
- Versioning that shows you how a prompt has evolved over time
- The ability to update a prompt in production without redeploying your application
- The ability to evaluate a prompt against many inputs to evaluate performance

## Getting started

If you want complete control over how a Prompt is constructed, you can subclass the base class, `weave.Prompt`, `weave.StringPrompt`, or `weave.MessagesPrompt` and implement the corresponding `format` method. When you publish one of these objects with `weave.publish`, it will appear in your Weave project on the "Prompts" page.

```
class Prompt(Object):
    def format(self, **kwargs: Any) -> Any:
        ...

class StringPrompt(Prompt):
    def format(self, **kwargs: Any) -> str:
        ...

class MessagesPrompt(Prompt):
    def format(self, **kwargs: Any) -> list:
        ...
```

Weave also includes a "batteries-included" class called `EasyPrompt` that can be simpler to start with, especially if you are working with APIs that are similar to OpenAI. This document highlights the features you get with EasyPrompt.

## Constructing prompts

You can think of the EasyPrompt object as a list of messages with associated roles, optional
placeholder variables, and an optional model configuration.
But constructing a prompt can be as simple as providing a single string:

```python
import weave

prompt = weave.EasyPrompt("What's 23 * 42?")
assert prompt[0] == {"role": "user", "content": "What's 23 * 42?"}
```

For terseness, the weave library aliases the `EasyPrompt` class to `P`.

```python
from weave import P
p = P("What's 23 * 42?")
```

It is common for a prompt to consist of multiple messages. Each message has an associated `role`.
If the role is omitted, it defaults to `"user"`.

**Some common roles**

| Role      | Description                                                                                                          |
| --------- | -------------------------------------------------------------------------------------------------------------------- |
| system    | System prompts provide high level instructions and can be used to set the behavior, knowledge, or persona of the AI. |
| user      | Represents input from a human user. (This is the default role.)                                                      |
| assistant | Represents the AI's generated replies. Can be used for historical completions or to show examples.                   |

For convenience, you can prefix a message string with one of these known roles:

```python
import weave

prompt = weave.EasyPrompt("system: Talk like a pirate")
assert prompt[0] == {"role": "system", "content": "Talk like a pirate"}

# An explicit role parameter takes precedence
prompt = weave.EasyPrompt("system: Talk like a pirate", role="user")
assert prompt[0] == {"role": "user", "content": "system: Talk like a pirate"}

```

Messages can be appended to a prompt one-by-one:

```python
import weave

prompt = weave.EasyPrompt()
prompt.append("You are an expert travel consultant.", role="system")
prompt.append("Give me five ideas for top kid-friendly attractions in New Zealand.")
```

Or you can append multiple messages at once, either with the `append` method or with the `Prompt`
constructor, which is convenient for constructing a prompt from existing messages.

```python
import weave

prompt = weave.EasyPrompt()
prompt.append([
    {"role": "system", "content": "You are an expert travel consultant."},
    "Give me five ideas for top kid-friendly attractions in New Zealand."
])

# Same
prompt = weave.EasyPrompt([
    {"role": "system", "content": "You are an expert travel consultant."},
    "Give me five ideas for top kid-friendly attractions in New Zealand."
])
```

The Prompt class is designed to be easily inserted into existing code.
For example, you can quickly wrap it around all of the arguments to the
OpenAI chat completion `create` call including its messages and model
configuration. If you don't wrap the inputs, Weave's integration would still
track all of the call's inputs, but it would not extract them as a separate
versioned object. Having a separate Prompt object allows you to version
the prompt, easily filter calls by that version, etc.

```python
from weave import init, P
from openai import OpenAI
client = OpenAI()

# Must specify a target project, otherwise the Weave code is a no-op
# highlight-next-line
init("intro-example")

# highlight-next-line
response = client.chat.completions.create(P(
  model="gpt-4o-mini",
  messages=[
    {"role": "user", "content": "What's 23 * 42?"}
  ],
  temperature=0.7,
  max_tokens=64,
  top_p=1
# highlight-next-line
))
```

:::note
Why this works: Weave's OpenAI integration wraps the OpenAI `create` method to make it a Weave Op.
When the Op is executed, the Prompt object in the input will get saved and associated with the Call.
However, it will be replaced with the structure the `create` method expects for the execution of the
underlying function.
:::

## Parameterizing prompts

When specifying a prompt, you can include placeholders for values you want to fill in later. These placeholders are called "Parameters".
Parameters are indicated with curly braces. Here's a simple example:

```python
import weave

prompt = weave.EasyPrompt("What's {A} + {B}?")
```

You will specify values for all of the parameters or "bind" them, when you [use the prompt](#using-prompts).

The `require` method of Prompt allows you to associate parameters with restrictions that will be checked at bind time to detect programming errors.

```python
import weave

prompt = weave.EasyPrompt("What's {A} + 42?")
prompt.require("A", type="int", min=0, max=100)

prompt = weave.EasyPrompt("system: You are a {profession}")
prompt.require("profession", oneof=('pirate', 'cartoon mouse', 'hungry dragon'), default='pirate')
```

## Using prompts

You use a Prompt by converting it into a list of messages where all template placeholders have been filled in. You can bind a prompt to parameter values with the `bind` method or by simply calling it as a function. Here's an example where the prompt has zero parameters.

```python
import weave
prompt = weave.EasyPrompt("What's 23 * 42?")
assert prompt() == prompt.bind() == [
    {"role": "user", "content": "What's 23 * 42?"}
]
```

If a prompt has parameters, you would specify values for them when you use the prompt.
Parameter values can be passed in as a dictionary or as keyword arguments.

```python
import weave
prompt = weave.EasyPrompt("What's {A} + {B}?")
assert prompt(A=5, B="10") == prompt({"A": 5, "B": "10"})
```

If any parameters are missing, they will be left unsubstituted in the output.

Here's a complete example of using a prompt with OpenAI. This example also uses [Weave's OpenAI integration](../integrations/openai.md) to automatically log the prompt and response.

```python
import weave
from openai import OpenAI
client = OpenAI()

weave.init("intro-example")
prompt = weave.EasyPrompt()
prompt.append("You will be provided with a tweet, and your task is to classify its sentiment as positive, neutral, or negative.", role="system")
prompt.append("I love {this_thing}!")

response = client.chat.completions.create(
  model="gpt-4o-mini",
  messages=prompt(this_thing="Weave"),
  temperature=0.7,
  max_tokens=64,
  top_p=1
)
```

## Publishing to server

Prompt are a type of [Weave object](../tracking/objects.md), and use the same methods for publishing to the Weave server.
You must specify a destination project name with `weave.init` before you can publish a prompt.

```python
import weave

prompt = weave.EasyPrompt()
prompt.append("What's 23 * 42?")

weave.init("intro-example") # Use entity/project format if not targeting your default entity
weave.publish(prompt, name="calculation-prompt")
```

Weave will automatically determine if the object has changed and only publish a new version if it has.
You can also specify a name or description for the Prompt as part of its constructor.

```python
import weave

prompt = weave.EasyPrompt(
    "What's 23 * 42?",
    name="calculation-prompt",
    description="A prompt for calculating the product of two numbers.",
)

weave.init("intro-example")
weave.publish(prompt)
```

## Retrieving from server

Prompt are a type of [Weave object](../tracking/objects.md), and use the same methods for retrieval from the Weave server.
You must specify a source project name with `weave.init` before you can retrieve a prompt.

```python
import weave

weave.init("intro-example")
prompt = weave.ref("calculation-prompt").get()
```

By default, the latest version of the prompt is returned. You can make this explicit or select a specific version by providing its version id.

```python
import weave

weave.init("intro-example")
prompt = weave.ref("calculation-prompt:latest").get()
# "<prompt_name>:<version_digest>", for example:
prompt = weave.ref("calculation-prompt:QSLzr96CTzFwLWgFFi3EuawCI4oODz4Uax98SxIY79E").get()
```

It is also possible to retrieve a Prompt without calling `init` if you pass a fully qualified URI to `weave.ref`.

## Loading and saving from files

Prompts can be saved to files and loaded from files. This can be convenient if you want your Prompt to be versioned through
a mechanism other than Weave such as git, or as a fallback if Weave is not available.

To save a prompt to a file, you can use the `dump_file` method.

```python
import weave

prompt = weave.EasyPrompt("What's 23 * 42?")
prompt.dump_file("~/prompt.json")
```

and load it again later with `Prompt.load_file`.

```python
import weave

prompt = weave.EasyPrompt.load_file("~/prompt.json")
```

You can also use the lower level `dump` and `Prompt.load` methods for custom (de)serialization.

## Evaluating prompts

The [Parameter feature of prompts](#parameterizing-prompts) can be used to execute or evaluate variations of a prompt.

You can bind each row of a [Dataset](./datasets.md) to generate N variations of a prompt.

```python
import weave

# Create a dataset
dataset = weave.Dataset(name='countries', rows=[
    {'id': '0', 'country': "Argentina"},
    {'id': '1', 'country': "Belize"},
    {'id': '2', 'country': "Canada"},
    {'id': '3', 'country': "New Zealand"},
])

prompt = weave.EasyPrompt(name='travel_agent')
prompt.append("You are an expert travel consultant.", role="system")
prompt.append("Tell me the capital of {country} and about five kid-friendly attractions there.")


prompts = prompt.bind_rows(dataset)
assert prompts[2][1]["content"] == "Tell me the capital of Canada and about five kid-friendly attractions there."
```

You can extend this into an [Evaluation](./evaluations.md):

```python
import asyncio

import openai
import weave

weave.init("intro-example")

# Create a dataset
dataset = weave.Dataset(name='countries', rows=[
    {'id': '0', 'country': "Argentina", 'capital': "Buenos Aires"},
    {'id': '1', 'country': "Belize", 'capital': "Belmopan"},
    {'id': '2', 'country': "Canada", 'capital': "Ottawa"},
    {'id': '3', 'country': "New Zealand", 'capital': "Wellington"},
])

# Create a prompt
prompt = weave.EasyPrompt(name='travel_agent')
prompt.append("You are an expert travel consultant.", role="system")
prompt.append("Tell me the capital of {country} and about five kid-friendly attractions there.")

# Create a model, combining a prompt with model configuration
class TravelAgentModel(weave.Model):

    model_name: str
    prompt: weave.EasyPrompt

    @weave.op
    async def predict(self, country: str) -> dict:
        client = openai.AsyncClient()

        response = await client.chat.completions.create(
            model=self.model_name,
            messages=self.prompt(country=country),
        )
        result = response.choices[0].message.content
        if result is None:
            raise ValueError("No response from model")
        return result

# Define and run the evaluation
@weave.op
def mentions_capital_scorer(capital: str, model_output: str) -> dict:
    return {'correct': capital in model_output}

model = TravelAgentModel(model_name="gpt-4o-mini", prompt=prompt)
evaluation = weave.Evaluation(
    dataset=dataset,
    scorers=[mentions_capital_scorer],
)
asyncio.run(evaluation.evaluate(model))

```
