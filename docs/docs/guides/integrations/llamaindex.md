# LlamaIndex

Weave provides seamless integration with [LlamaIndex](https://docs.llamaindex.ai/en/stable/), a powerful framework for building LLM-powered applications such as retrieval-augmented generation (RAG), chatbots, and autonomous agents. The integration automatically captures detailed traces of all LlamaIndex operations, making it easy to monitor, debug, and optimize your LLM workflows.

When working with LLMs, debugging is inevitable. Whether a model call fails, an output is misformatted, or nested model calls create confusion, pinpointing issues can be challenging. LlamaIndex applications often consist of multiple steps and LLM call invocations, making it crucial to understand the inner workings of your chains and agents.

Weave simplifies this process by automatically capturing traces for your LlamaIndex applications through LlamaIndex's built-in instrumentation system. This enables you to monitor and analyze your application's performance, making it easier to debug and optimize your LLM workflows.

## Getting Started

To get started, simply call `weave.init()` at the beginning of your script. The integration will automatically start tracing all LlamaIndex operations.

```python
import weave
from llama_index.llms.openai import OpenAI

# Initialize Weave with your project name
# highlight-next-line
weave.init("llamaindex-demo")

# All LlamaIndex operations are now automatically traced
llm = OpenAI(model="gpt-4o-mini")
response = llm.complete("William Shakespeare is ")
print(response)
```

That's it! The integration leverages [LlamaIndex's instrumentation system](https://docs.llamaindex.ai/en/stable/module_guides/observability/instrumentation/) to automatically capture traces for all operations including LLM calls, embeddings, retrievals, and agent steps.

![LlamaIndex Demo](imgs/llamaindex/simple_trace.png)

## Core LlamaIndex Components

The Weave integration supports [all major LlamaIndex components](https://docs.llamaindex.ai/en/stable/module_guides/) with automatic tracing:

### LLM Operations

Weave automatically traces all LlamaIndex LLM operations including completions, streaming, chat, and tool calling.

#### Synchronous and Asynchronous Completions

```python
import weave
from llama_index.llms.openai import OpenAI

# highlight-next-line
weave.init("llamaindex-demo")

llm = OpenAI(model="gpt-4o-mini")

# Synchronous completion
response = llm.complete("William Shakespeare is ")
print(response)

# Asynchronous completion
response = await llm.acomplete("William Shakespeare is ")
print(response)
```

#### Streaming Operations

```python
import weave
from llama_index.llms.openai import OpenAI

# highlight-next-line
weave.init("llamaindex-demo")

llm = OpenAI(model="gpt-4o-mini")

# Synchronous streaming
handle = llm.stream_complete("William Shakespeare is ")
for token in handle:
    print(token.delta, end="", flush=True)

# Asynchronous streaming
handle = await llm.astream_complete("William Shakespeare is ")
async for token in handle:
    print(token.delta, end="", flush=True)
```

### Chat Interface

The LLM class also implements a chat method, which allows you to have more sophisticated interactions.

```python
import weave
from llama_index.llms.openai import OpenAI
from llama_index.core.llms import ChatMessage

# highlight-next-line
weave.init("llamaindex-demo")

llm = OpenAI(model="gpt-4o-mini")
messages = [
    ChatMessage(role="system", content="You are a helpful assistant."),
    ChatMessage(role="user", content="Tell me a joke."),
]

# Synchronous chat
response = llm.chat(messages)
print(response)

# Asynchronous chat
response = await llm.achat(messages)
print(response)

# Streaming chat
handle = llm.stream_chat(messages)
for token in handle:
    print(token.delta, end="", flush=True)
```

### Tool Calling

Tool calling is a central piece for building agents and workflows. Weave automatically traces all tool calls, including synchronous and asynchronous calls.

```python
import weave
from pydantic import BaseModel
from llama_index.core.tools import FunctionTool
from llama_index.llms.openai import OpenAI

# highlight-next-line
weave.init("llamaindex-demo")

class Song(BaseModel):
    name: str
    artist: str

def generate_song(name: str, artist: str) -> Song:
    """Generates a song with provided name and artist."""
    return Song(name=name, artist=artist)

tool = FunctionTool.from_defaults(fn=generate_song)
llm = OpenAI(model="gpt-4o-mini")

response = llm.predict_and_call([tool], "Pick a random song for me")
print(response)
```

![LlamaIndex Tool Calling](imgs/llamaindex/tool_call_trace.png)

### Agents

In LlamaIndex, an agent is powered by an LLM to solve a task by executing a series of steps. It is given a set of tools, which can be anything from arbitrary functions up to full LlamaIndex query engines.

```python
import asyncio
import weave
from llama_index.core.agent.workflow import FunctionAgent
from llama_index.llms.openai import OpenAI
from llama_index.core.memory import ChatMemoryBuffer

# highlight-next-line
weave.init("llamaindex-demo")

def multiply(a: float, b: float) -> float:
    """Useful for multiplying two numbers."""
    return a * b

agent = FunctionAgent(
    tools=[multiply],
    llm=OpenAI(model="gpt-4o-mini"),
    system_prompt="You are a helpful assistant that can multiply two numbers.",
)

memory = ChatMemoryBuffer.from_defaults(token_limit=40000)

# highlight-next-line
@weave.op()
async def main():
    response = await agent.run("What is 1234 * 4567?", memory=memory)
    print(response)

if __name__ == "__main__":
    asyncio.run(main())
```

### Workflows

A workflow is an event-driven, step-based way to control the execution flow of an application. This paradigm allows you to create arbitrarily complex flows that encapsulate logic and make your application more maintainable and easier to understand.

```python
import weave
from llama_index.core.workflow import (
    StartEvent,
    StopEvent,
    Workflow,
    step,
    Event,
)

# highlight-next-line
weave.init("llamaindex-demo")

class FirstEvent(Event):
    payload: str

class SecondEvent(Event):
    payload: str

class SimpleWorkflow(Workflow):
    @step
    async def step_one(self, ev: StartEvent) -> FirstEvent:
        return FirstEvent(payload="First step complete")

    @step
    async def step_two(self, ev: FirstEvent) -> SecondEvent:
        return SecondEvent(payload="Second step complete")

    @step
    async def step_three(self, ev: SecondEvent) -> StopEvent:
        return StopEvent(result="Workflow complete")

workflow = SimpleWorkflow(timeout=10, verbose=False)
result = await workflow.run(first_input="Start the workflow")
print(result)
```

### RAG Pipelines

```python
import weave
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
from llama_index.core.node_parser import SentenceSplitter
from llama_index.llms.openai import OpenAI

# highlight-next-line
weave.init("llamaindex-demo")

# Load and process documents
documents = SimpleDirectoryReader("data").load_data()
parser = SentenceSplitter()
nodes = parser.get_nodes_from_documents(documents)

# Create index and query engine
index = VectorStoreIndex(nodes)
query_engine = index.as_query_engine()

# Query the documents
response = query_engine.query("What did the author do growing up?")
print(response)
```

## Comprehensive Agent Example

Here's a complete example combining multiple components:

```python
import weave
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
from llama_index.core.agent.workflow import FunctionAgent
from llama_index.llms.openai import OpenAI

# highlight-next-line
weave.init("llamaindex-demo")

# Create a RAG tool
documents = SimpleDirectoryReader("data").load_data()
index = VectorStoreIndex.from_documents(documents)
query_engine = index.as_query_engine()

# highlight-next-line
def multiply(a: float, b: float) -> float:
    """Useful for multiplying two numbers."""
    return a * b

# highlight-next-line
async def search_documents(query: str) -> str:
    """Useful for answering questions about documents."""
    response = await query_engine.aquery(query)
    return str(response)

# highlight-next-line
# Create an agent with both tools
agent = FunctionAgent(
    tools=[multiply, search_documents],
    llm=OpenAI(model="gpt-4o-mini"),
    system_prompt="""You are a helpful assistant that can perform calculations
    and search through documents to answer questions.""",
)

# highlight-next-line
response = await agent.run(
    "What did the author do in college? Also, what's 7 * 8?"
)
print(response)
```

## Automatic Tracing Features

The Weave integration automatically captures:

- **Execution Time**: Duration of each operation
- **Token Usage**: Input and output token counts
- **Cost Tracking**: Estimated costs for API calls
- **Inputs and Outputs**: Full request and response data
- **Error Handling**: Detailed error traces and stack traces
- **Nested Operations**: Complete trace hierarchy showing parent-child relationships
- **Streaming Data**: Accumulated streaming responses

All trace data is viewable in the Weave web interface, making it easy to debug and optimize your LlamaIndex applications.

By integrating Weave with LlamaIndex, you get comprehensive observability into your LLM applications with zero additional configuration, making it easier to debug, optimize, and evaluate your workflows.
