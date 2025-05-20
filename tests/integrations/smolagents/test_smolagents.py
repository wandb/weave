import os
from typing import Optional

import pytest

from weave.integrations.integration_utilities import op_name_from_ref


def mask_api_key_and_skip(request):
    from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

    # Skip requests to the specific URL
    if "raw.githubusercontent.com/BerriAI/litellm" in request.uri:
        return None

    # Mask api_key in query params
    url = urlparse(request.uri)
    query = parse_qs(url.query)
    if "api_key" in query:
        query["api_key"] = ["DUMMY_API_KEY"]
        new_query = urlencode(query, doseq=True)
        new_url = url._replace(query=new_query)
        request = request._replace(uri=urlunparse(new_url))
    return request


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai", "huggingface.co"],
    match_on=["method", "scheme", "host", "port", "path"],
    before_record_request=mask_api_key_and_skip,
)
def test_hf_api_model(client):
    from smolagents import HfApiModel

    os.environ["HUGGINGFACE_API_KEY"] = os.environ.get(
        "HUGGINGFACE_API_KEY", "DUMMY_API_KEY"
    )
    engine = HfApiModel(
        model_id="Qwen/Qwen2.5-Coder-32B-Instruct",
        token=os.getenv("HUGGINGFACE_API_KEY", "DUMMY_API_KEY"),
    )
    messages = [{"role": "user", "content": "What is the capital of France?"}]
    response = engine(messages, stop_sequences=["END"])
    assert "paris" in response.content.lower()

    calls = client.calls()
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
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai", "huggingface.co"],
    match_on=["method", "scheme", "host", "port", "path"],
    before_record_request=mask_api_key_and_skip,
)
def test_openai_server_model(client):
    from smolagents import OpenAIServerModel

    os.environ["OPENAI_API_KEY"] = os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY")

    engine = OpenAIServerModel(
        model_id="gpt-4o-mini",
        api_key=os.getenv("OPENAI_API_KEY", "DUMMY_API_KEY"),
    )
    messages = [{"role": "user", "content": "What is the capital of France?"}]
    response = engine(messages, stop_sequences=["END"])
    assert "paris" in response.content.lower()

    calls = client.calls()
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
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai", "huggingface.co"],
    match_on=["method", "scheme", "host", "port", "path"],
    before_record_request=mask_api_key_and_skip,
)
def test_tool_calling_agent_search(client):
    from smolagents import GoogleSearchTool, OpenAIServerModel, ToolCallingAgent

    os.environ["OPENAI_API_KEY"] = os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY")
    os.environ["HUGGINGFACE_API_KEY"] = os.environ.get(
        "HUGGINGFACE_API_KEY", "DUMMY_API_KEY"
    )
    os.environ["SERPAPI_API_KEY"] = os.environ.get("SERPAPI_API_KEY", "DUMMY_API_KEY")
    model = OpenAIServerModel(model_id="gpt-4.1-mini")
    agent = ToolCallingAgent(tools=[GoogleSearchTool()], model=model)
    answer = agent.run(
        "Use the provided tool to answer this question. Get the following page - 'https://weave-docs.wandb.ai/'?"
    )

    calls = client.calls()
    assert len(calls) == 19

    call = calls[0]
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "smolagents.ToolCallingAgent.run"
    assert str(call.output) == answer


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai", "huggingface.co"],
    match_on=["method", "scheme", "host", "port", "path"],
    before_record_request=mask_api_key_and_skip,
)
def test_tool_calling_agent_weather(client):
    from smolagents import OpenAIServerModel, ToolCallingAgent, tool

    os.environ["OPENAI_API_KEY"] = os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY")
    os.environ["HUGGINGFACE_API_KEY"] = os.environ.get(
        "HUGGINGFACE_API_KEY", "DUMMY_API_KEY"
    )

    model = OpenAIServerModel(model_id="gpt-4.1-mini")

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
    calls = client.calls()
    assert len(calls) == 10

    call = calls[0]
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "smolagents.ToolCallingAgent.run"


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai", "huggingface.co"],
    match_on=["method", "scheme", "host", "port", "path"],
    before_record_request=mask_api_key_and_skip,
)
def test_code_agent_search(client):
    from smolagents import CodeAgent, GoogleSearchTool, OpenAIServerModel

    os.environ["OPENAI_API_KEY"] = os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY")
    os.environ["HUGGINGFACE_API_KEY"] = os.environ.get(
        "HUGGINGFACE_API_KEY", "DUMMY_API_KEY"
    )
    os.environ["SERPAPI_API_KEY"] = os.environ.get("SERPAPI_API_KEY", "DUMMY_API_KEY")

    model = OpenAIServerModel(model_id="gpt-4.1-mini")
    agent = CodeAgent(tools=[GoogleSearchTool()], model=model)
    answer = agent.run(
        "Use the provided tool to answer this question. Get the following page - 'https://weave-docs.wandb.ai/'?"
    )

    calls = client.calls()
    assert len(calls) == 26

    call = calls[0]
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "smolagents.CodeAgent.run"
    assert str(call.output) == answer


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai", "huggingface.co"],
    match_on=["method", "scheme", "host", "port", "path"],
    before_record_request=mask_api_key_and_skip,
)
def test_code_agent_weather(client):
    from smolagents import CodeAgent, OpenAIServerModel, tool

    os.environ["OPENAI_API_KEY"] = os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY")
    os.environ["HUGGINGFACE_API_KEY"] = os.environ.get(
        "HUGGINGFACE_API_KEY", "DUMMY_API_KEY"
    )
    os.environ["SERPAPI_API_KEY"] = os.environ.get("SERPAPI_API_KEY", "DUMMY_API_KEY")

    model = OpenAIServerModel(model_id="gpt-4.1-mini")

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
    answer = agent.run(
        "Use the provided tool to answer this question. What is the weather in Tokyo?"
    )

    assert answer == "The weather in Tokyo is sunny with temperatures around 7°C."
    calls = client.calls()
    assert len(calls) == 9

    call = calls[0]
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "smolagents.CodeAgent.run"
