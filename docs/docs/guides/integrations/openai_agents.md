
# OpenAI Agents SDK

The [OpenAI Agents Python SDK](https://github.com/openai/openai-agents-python) is a lightweight and powerful framework for building multi-agent workflows. You can use W&B Weave with the OpenAI Agents SDK to track and monitor your agentic applications.

## Installation

Install the required dependencies using `pip`: 

```bash
pip install weave openai-agents
```

## Get started

To use the OpenAI Agents SDK with Weave, you'll need to:

- Initialize Weave with your project name
- Add the Weave tracing processor to your agents
- Create and run your agents as usual

In the following codes sample, an OpenAI Agent is created and integrated with Weave for traceability. First, a Weave project is initialized and the `WeaveTracingProcessor` is set up to capture execution traces. A `Weather` data model is created to represent weather information. The `get_weather` function is decorated as a tool the agent can use and returns a sample weather report. An agent named `Hello world` is configured with basic instructions and access to the weather tool. The main function asynchronously runs the agent with a sample input (`What's the weather in Tokyo?`) and outputs the final response.

```python
from pydantic import BaseModel
from agents import Agent, Runner, function_tool, set_trace_processors
import agents
import weave
from weave.integrations.openai_agents.openai_agents import WeaveTracingProcessor
import asyncio

weave.init("openai-agents")
set_trace_processors([WeaveTracingProcessor()])

class Weather(BaseModel):
    city: str
    temperature_range: str
    conditions: str

@function_tool
def get_weather(city: str) -> Weather:
    return Weather(city=city, temperature_range="14-20C", conditions="Sunny with wind.")

agent = Agent(
    name="Hello world",
    instructions="You are a helpful agent.",
    tools=[get_weather]
)

async def main():
    result = await Runner.run(agent, input="What's the weather in Tokyo?")    
    print(result.final_output)

if __name__ == "__main__":
    asyncio.run(main())
```

## View traces

When the above code sample is run, a link to the Weave dashboard is generated. To see what happened during your agent execution, follow the link to see your agent traces. 
