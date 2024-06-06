---
sidebar_position: 2
hide_table_of_contents: true
---

# Langchain

Weave seamlessly tracks and logs all LLM calls made through the [Langchain Python library](https://github.com/langchain-ai/langchain).

## Getting Started

Weave allows you to closely monitor and evaluate your application by automatically capturing traces for your [Langchain](https://python.langchain.com/v0.2/docs/introduction/) applications. To get started, simply call `weave.init()` at the beginning of your script. The argument in `weave.init()` is a project name that will help you organize your traces.


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

output = llm_chain.invoke(
    {"number": 2},
)

print(output)
```

## Traces

Storing traces of LLM applications in a central database is crucial during both development and production. These traces are essential for debugging and improving your application by providing a valuable dataset.

Weave allows you to closely monitor and evaluate your application by automatically capturing traces for your Langchain applications.

Weave will now track and log all calls made through the Langchain library, including prompt templates, chains, LLM calls, tools, and agent steps. You can view the traces in the Weave web interface.

[![langchain_trace.png](imgs/langchain_trace.png)](https://wandb.ai/parambharat/langchain_demo/weave/calls)


