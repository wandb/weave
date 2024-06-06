---
sidebar_position: 2
hide_table_of_contents: true
---

# LangChain

Weave is designed to make tracking and logging all calls made through the [LangChain Python library](https://github.com/langchain-ai/langchain) effortless.

When working with LLMs, debugging is inevitable. Whether a model call fails, an output is misformatted, or nested model calls create confusion, pinpointing issues can be challenging. LangChain applications often consist of multiple steps and LLM call invocations, making it crucial to understand the inner workings of your chains and agents.

Weave simplifies this process by automatically capturing traces for your [LangChain](https://python.langchain.com/v0.2/docs/introduction/) applications. This enables you to monitor and analyze your application's performance, making it easier to debug and optimize your LLM workflows.


## Getting Started

To get started, simply call `weave.init()` at the beginning of your script. The argument in weave.init() is a project name that will help you organize your traces.

```python
import weave
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

# Initialize Weave with your project name
# highlight-next-line
weave.init("langchain_demo")

llm = ChatOpenAI()
prompt = PromptTemplate.from_template("1 + {number} = ")

llm_chain = prompt | llm

output = llm_chain.invoke({"number": 2})

print(output)
```

## Traces

Storing traces of LLM applications in a central database is crucial during both development and production. These traces are essential for debugging and improving your application by providing a valuable dataset.

Weave automatically captures traces for your LangChain applications. It will track and log all calls made through the LangChain library, including prompt templates, chains, LLM calls, tools, and agent steps. You can view the traces in the Weave web interface.

[![langchain_trace.png](imgs/langchain_trace.png)](https://wandb.ai/parambharat/langchain_demo/weave/calls)

## Manually Tracing Calls

In addition to automatic tracing, you can manually trace calls using the `WeaveTracer` callback or the `weave_tracing_enabled` context manager. These methods are akin to using request callbacks in individual parts of a LangChain application.

### Using `WeaveTracer`

You can pass the `WeaveTracer` callback to individual LangChain components to trace specific requests.

```python
from weave.integrations.langchain import WeaveTracer
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
import weave

# Initialize Weave with your project name
# highlight-next-line
weave.init("langchain_demo")

weave_tracer = WeaveTracer()

config = {"callbacks": [weave_tracer]}

llm = ChatOpenAI()
prompt = PromptTemplate.from_template("1 + {number} = ")

llm_chain = prompt | llm

output = llm_chain.invoke({"number": 2}, config=config)

print(output)
```

### Using `weave_tracing_enabled` Context Manager

Alternatively, you can use the `weave_tracing_enabled` context manager to enable tracing for specific blocks of code.

```python
from weave.integrations.langchain import weave_tracing_enabled
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
import weave

# Initialize Weave with your project name
# highlight-next-line
weave.init("langchain_demo")

llm = ChatOpenAI()
prompt = PromptTemplate.from_template("1 + {number} = ")

llm_chain = prompt | llm

with weave_tracing_enabled():
    output = llm_chain.invoke({"number": 2})

print(output)
```

## Configuration

Upon calling `weave.init`, tracing is enabled by setting the environment variable `WEAVE_TRACE_LANGCHAIN` to `"true"`. This allows Weave to automatically capture traces for your LangChain applications. If you wish to disable this behavior, set the environment variable to `"false"`.

## Relation to LangChain Callbacks

### Auto Logging

The automatic logging provided by `weave.init()` is similar to passing a constructor callback to every component in a LangChain application. This means that all interactions, including prompt templates, chains, LLM calls, tools, and agent steps, are tracked globally across your entire application.

### Manual Logging

The manual logging methods (`WeaveTracer` and `weave_tracing_enabled`) are similar to using request callbacks in individual parts of a LangChain application. These methods provide finer control over which parts of your application are traced:

- **Constructor Callbacks:** Applied to the entire chain or component, logging all interactions consistently.
- **Request Callbacks:** Applied to specific requests, allowing detailed tracing of particular invocations.

By integrating Weave with LangChain, you can ensure comprehensive logging and monitoring of your LLM applications, facilitating easier debugging and performance optimization.

For more detailed information, refer to the [LangChain documentation](https://python.langchain.com/v0.2/docs/how_to/debugging/#tracing).