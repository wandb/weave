import os
from typing import Optional

import pytest

from weave.integrations.integration_utilities import op_name_from_ref


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_hf_api_model(client):
    from smolagents import HfApiModel

    engine = HfApiModel(
        model_id="Qwen/Qwen2.5-Coder-32B-Instruct",
        token=os.environ.get("HUGGINGFACE_API_KEY", "DUMMY_API_KEY"),
    )
    messages = [{"role": "user", "content": "What is the capital of France?"}]
    response = engine(messages, stop_sequences=["END"])
    assert "paris" in response.content.lower()

    calls = list(client.calls())
    assert len(calls) == 2

    call = calls[0]
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "smolagents.HfApiModel"
    assert "paris" in call.output.content.lower()

    call = calls[1]
    assert call.started_at < call.ended_at
    assert (
        op_name_from_ref(call.op_name)
        == "huggingface_hub.InferenceClient.chat_completion"
    )
    assert "paris" in call.output.choices[0].message.content.lower()


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_openai_server_model(client):
    from smolagents import OpenAIServerModel

    engine = OpenAIServerModel(
        model_id="gpt-4o-mini",
        api_key=os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY"),
    )
    messages = [{"role": "user", "content": "What is the capital of France?"}]
    response = engine(messages, stop_sequences=["END"])
    assert "paris" in response.content.lower()

    calls = list(client.calls())
    assert len(calls) == 2

    call = calls[0]
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "smolagents.OpenAIServerModel"
    assert "paris" in call.output.content.lower()

    call = calls[1]
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "openai.chat.completions.create"
    assert "paris" in call.output["choices"][0]["message"]["content"].lower()


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_tool_calling_agent_ddgsearch(client):
    from smolagents import DuckDuckGoSearchTool, OpenAIServerModel, ToolCallingAgent

    model = OpenAIServerModel(model_id="gpt-4o")
    agent = ToolCallingAgent(tools=[DuckDuckGoSearchTool()], model=model)
    answer = agent.run(
        "Get me just the title of the page at url 'https://wandb.ai/geekyrakshit/story-illustration/reports/Building-a-GenAI-assisted-automatic-story-illustrator--Vmlldzo5MTYxNTkw'?"
    )

    calls = list(client.calls())
    assert len(calls) == 11

    call = calls[0]
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "smolagents.ToolCallingAgent.run"
    assert str(call.output) == answer


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_tool_calling_agent_weather(client):
    from smolagents import OpenAIServerModel, ToolCallingAgent, tool

    model = OpenAIServerModel(model_id="gpt-4o")

    @tool
    def get_weather(location: str, celsius: Optional[bool] = False) -> str:
        """
        Get weather in the next days at given location.
        Args:
            location: the location
            celsius: whether to use Celsius for temperature
        """
        return f"The weather in {location} is sunny with temperatures around 7°C."

    agent = ToolCallingAgent(tools=[get_weather], model=model)
    answer = agent.run("What is the weather in Tokyo?")

    assert answer == "The weather in Tokyo is sunny with temperatures around 7°C."
    calls = list(client.calls())
    assert len(calls) == 11

    call = calls[0]
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "smolagents.ToolCallingAgent.run"


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_code_agent_ddgsearch(client):
    from smolagents import DuckDuckGoSearchTool, OpenAIServerModel, CodeAgent

    model = OpenAIServerModel(model_id="gpt-4o")
    agent = CodeAgent(tools=[DuckDuckGoSearchTool()], model=model)
    answer = agent.run(
        "Get me just the title of the page at url 'https://wandb.ai/geekyrakshit/story-illustration/reports/Building-a-GenAI-assisted-automatic-story-illustrator--Vmlldzo5MTYxNTkw'?"
    )

    calls = list(client.calls())
    assert len(calls) == 10

    call = calls[0]
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "smolagents.CodeAgent.run"
    assert str(call.output) == answer


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_code_agent_weather(client):
    from smolagents import OpenAIServerModel, CodeAgent, tool

    model = OpenAIServerModel(model_id="gpt-4o")

    @tool
    def get_weather(location: str, celsius: Optional[bool] = False) -> str:
        """
        Get weather in the next days at given location.
        Args:
            location: the location
            celsius: whether to use Celsius for temperature
        """
        return f"The weather in {location} is sunny with temperatures around 7°C."

    agent = CodeAgent(tools=[get_weather], model=model)
    answer = agent.run("What is the weather in Tokyo?")

    assert answer == "The weather in Tokyo is sunny with temperatures around 7°C."
    calls = list(client.calls())
    assert len(calls) == 10

    call = calls[0]
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "smolagents.CodeAgent.run"
