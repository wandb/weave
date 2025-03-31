# Smolagents

:::important
All code samples shown on this page are in Python.
:::

This page explains how to integrate [Smolagents](https://huggingface.co/docs/smolagents/en/index) with W&B Weave to track and analyze your agentic applications. You'll learn how to log model inferences, monitor function calls, and organize experiments using Weave's tracing and versioning capabilities. By following the examples provided, you can capture valuable insights, debug your applications efficiently, and compare different model configurations—all within the Weave web interface.

## Overview

Smolagents is a simple framework that offer simple and minimal abstractions to build powerful agentic applications supporting multiple LLM providers such as OpenAI, `transformers`, Anthropic, etc.

Weave will automatically capture traces for [Smolagents](https://huggingface.co/docs/smolagents/en/index). To start tracking, calling `weave.init()` and use the library as normal.

## Prerequisites

1. Before you can use Smolagents with Weave, you must install the necessary libraries, or upgrade to the latest versions. The following command installs or upgrades `huggingface_hub` and `weave` to the latest version if it's already installed, and reduces installation output.

    ```python
    pip install -U smolagents openai weave -qqq
    ```

2. Smolagents support multiple LLM providers such as OpenAI, `transformers`, Anthropic, etc. You need to set the API key of the LLM provider that you chose to use by setting the corresponding environment variable:

    ```python
    import os
    import getpass

    os.environ["OPENAI_API_KEY"] = getpass.getpass("Enter your OpenAI API key: ")
    ```

## Basic tracing

Storing traces of language model applications in a central location is essential during development and production. These traces help with debugging and serve as valuable datasets for improving your application.

Weave automatically captures traces for the [Smolagents](https://huggingface.co/docs/smolagents/en/index). To start tracking, initialize Weave by calling `weave.init()`, then use the library as usual.

The following example demonstrates how to log inference calls to the Hugging Face Hub using Weave:

```python
import weave
from smolagents import DuckDuckGoSearchTool, OpenAIServerModel, ToolCallingAgent

# Initialize Weave
weave.init(project_name="smolagents")

# Define your LLM provider supported by smolagents
model = OpenAIServerModel(model_id="gpt-4o")

# Define a duckduckgo web search tool based on your query
search_tool = DuckDuckGoSearchTool()

# Define and tool calling agent
agent = ToolCallingAgent(tools=[search_tool], model=model)
answer = agent.run(
    "Get me just the title of the page at url 'https://wandb.ai/geekyrakshit/story-illustration/reports/Building-a-GenAI-assisted-automatic-story-illustrator--Vmlldzo5MTYxNTkw'?"
)
```

![Weave logs each inference call, providing details about inputs, outputs, and metadata.](./imgs/huggingface/smolagents-trace.png)

## Tracing custom tools

You can declare custom tools for your agentic workflows either by decorating a function with `@tool` from `smolagents` or by inheriting from `smolagents.Tool` class.

Weave automatically tracks custom tool calls for your `smolagents` workflows.

```python
from typing import Optional

import weave
from smolagents import OpenAIServerModel, ToolCallingAgent, tool

weave.init(project_name="smolagents")

@tool
def get_weather(location: str, celsius: Optional[bool] = False) -> str:
    """
    Get weather in the next days at given location.
    Args:
        location: the location
        celsius: whether to use Celsius for temperature
    """
    return f"The weather in {location} is sunny with temperatures around 7°C."

model = OpenAIServerModel(model_id="gpt-4o")
agent = ToolCallingAgent(tools=[get_weather], model=model)
answer = agent.run("What is the weather in Tokyo?")
```

![Weave logs each custom tool call.](./imgs/huggingface/smolagents-custom-tool.png)
