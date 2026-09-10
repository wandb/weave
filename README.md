# **Weave by Weights & Biases**

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](http://wandb.me/weave_colab)
[![Stable Version](https://img.shields.io/pypi/v/weave?color=green)](https://pypi.org/project/weave)
[![Download Stats](https://img.shields.io/pypi/dm/weave)](https://pypistats.org/packages/weave)
[![Github Checks](https://img.shields.io/github/check-runs/wandb/weave/master
)](https://github.com/wandb/weave)
[![codecov](https://codecov.io/gh/wandb/weave/graph/badge.svg?token=YOUR_TOKEN)](https://codecov.io/gh/wandb/weave)

Weave is a toolkit for tracing and evaluating AI agents, built by [Weights & Biases](https://wandb.ai/).

You can use Weave to:

- **Trace agents.** Conversations, turns, LLM calls, and tool calls show up in the Agents tab.
- **Evaluate** agents and LLM applications.
- **Trace functions** with `@weave.op` when you want the Calls tab, not the Agents tab.

## Documentation

Our documentation site can be found [here](https://wandb.me/weave).

Start here for agents:

- [Choose an agent integration](https://docs.wandb.ai/weave/agent-integration-quickstart) — OpenAI Agents SDK, Claude Agent SDK, and Google ADK. `weave.init()` is enough for those SDKs.
- [Custom agents](https://docs.wandb.ai/weave/custom-agents-quickstart) — wrap your own loop with `start_conversation`, `start_turn`, `start_llm`, and `start_tool`.

## Prerequisites

- Python 3.10 or higher
- A [Weights & Biases account](https://wandb.ai/signup) (free tier available)
- A W&B API key from [https://wandb.ai/authorize](https://wandb.ai/authorize). Set `WANDB_API_KEY`, or run `wandb login`.
- An [OpenAI API key](https://platform.openai.com/api-keys) in `OPENAI_API_KEY`, for the example below.

## Quick start: trace an agent

This example uses the [OpenAI Agents SDK](https://docs.wandb.ai/weave/guides/integrations/agents/openai-agents-sdk). The Python import is `agents`; the package name is `openai-agents`. Weave autopatches it after `weave.init()`. Traces land in the **Agents** tab, not the Calls tab.

```bash
pip install weave openai-agents requests
```

```python
import asyncio
import requests
import weave
from agents import Agent, Runner, function_tool

weave.init("<your-team>/<your-project-name>")


@function_tool
def wikipedia_search(query: str) -> str:
    """Search Wikipedia for a topic and return its title and intro paragraph."""
    r = requests.get(
        "https://en.wikipedia.org/w/api.php",
        params={
            "action": "query",
            "generator": "search",
            "gsrsearch": query,
            "gsrlimit": 1,
            "prop": "extracts",
            "exintro": True,
            "explaintext": True,
            "format": "json",
        },
        headers={"User-Agent": "weave-demo"},
    ).json()
    page = next(iter(r["query"]["pages"].values()))
    return f"{page['title']}: {page['extract']}"


agent = Agent(
    name="Research assistant",
    instructions=(
        "You are a research assistant. Use the wikipedia_search tool to look up "
        "topics when needed, and cite the article titles you used."
    ),
    tools=[wikipedia_search],
)


async def main():
    history = []
    for question in [
        "Who founded Anthropic?",
        "What is Claude (the AI assistant)?",
        "Summarize what we discussed in one sentence.",
    ]:
        history.append({"role": "user", "content": question})
        print(f"USER: {question}")
        result = await Runner.run(agent, input=history)
        print(f"AGENT: {result.final_output}\n")
        history = result.to_input_list()


asyncio.run(main())
```

`weave.init()` prints a project URL. Open the **Agents** tab.

Claude Agent SDK works the same way: install the framework, call `weave.init()`, run the agent. For Google ADK, import `google.adk` before `weave.init()`. See [Choose an agent integration](https://docs.wandb.ai/weave/agent-integration-quickstart).

## Custom agents

If you are not using a supported agent SDK, wrap your own loop. This is the Conversation SDK, not the `@weave.op` path.

Use `start_conversation`, `start_turn`, and `start_llm`. In Python they are context managers and close on exceptions. `start_session` and `Session` still exist; they emit a `DeprecationWarning`. Do not use them in new code.

```python
import weave

weave.init("<your-team>/<your-project-name>")

with weave.start_conversation(agent_name="research-bot"):
    with weave.start_turn(user_message="Who founded Anthropic?"):
        with weave.start_llm(model="gpt-4o-mini", provider_name="openai") as llm:
            llm.output("Anthropic was founded by former OpenAI researchers.")
            llm.record(
                usage=weave.Usage(input_tokens=12, output_tokens=9),
                response_model="gpt-4o-mini",
            )
```

Always pass `provider_name`. Weave does not infer it from the model name.

For a multi-turn loop with tools, see the [custom agents quickstart](https://docs.wandb.ai/weave/custom-agents-quickstart).

## Function tracing

`@weave.op` traces a function. Those traces land in the **Calls** tab, not the Agents tab. Use it for evaluations, scorers, and LLM calls that are not an agent loop.

Plain `openai` is also auto-traced into the Calls tab after `weave.init()`. `@weave.op` wraps the call in a parent function, so the OpenAI request sits under `extract_fruit`.

```bash
pip install weave openai
```

```python
import json
import weave
from openai import OpenAI

weave.init("<your-team>/<your-project-name>")


@weave.op
def extract_fruit(sentence: str) -> dict:
    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You will be provided with unstructured data, and your task is to parse "
                    "it into one JSON object with fruit, color and flavor as keys."
                ),
            },
            {"role": "user", "content": sentence},
        ],
        temperature=0.7,
        response_format={"type": "json_object"},
    )
    extracted = response.choices[0].message.content
    return json.loads(extracted)


extract_fruit(
    "There are many fruits that were found on the recently discovered planet Goocrux. "
    "There are neoskizzles that grow there, which are purple and taste like candy."
)
```

## Contributing

Interested in pulling back the hood or contributing? Awesome, before you dive in, here's what you need to know.

We're in the process of 🧹 cleaning up 🧹. This codebase contains a large amount code for the "Weave engine" and "Weave boards", which we've put on pause as we focus on Tracing and Evaluations.

The Weave Tracing code is mostly in: `weave/trace` and `weave/trace_server`.

The Weave Evaluations code is mostly in `weave/flow`.
