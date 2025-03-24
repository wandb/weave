
# OpenAI Agents SDK

The [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) is a lightweight yet powerful framework for building multi-agent workflows.

## Installation

```bash
pip install weave openai-agents
```

## Getting Started

To use the OpenAI Agents SDK with Weave, you'll need to:
- Initialize Weave with your project name
- Add the Weave tracing processor to your agents
- Create and run your agents as usual

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

## View your traces

To see what happened during your agent execution, follow the link to your Weave dashboard and see your agent traces. 
