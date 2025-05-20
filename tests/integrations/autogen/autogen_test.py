import pytest

import weave
from weave.integrations.integration_utilities import flatten_calls, op_name_from_ref


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
@pytest.mark.asyncio
async def test_simple_client_create(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    from autogen_core.models import UserMessage
    from autogen_ext.models.openai import OpenAIChatCompletionClient

    model_name = "gpt-4.1-nano-2025-04-14"
    openai_model_client = OpenAIChatCompletionClient(model=model_name)
    _ = await openai_model_client.create(
        [UserMessage(content="Hello, how are you?", source="user")]
    )
    calls = list(client.calls())
    assert len(calls) == 2
    flattened = flatten_calls(calls)
    assert len(flattened) == 3
    got = [(op_name_from_ref(c.op_name), d) for (c, d) in flattened]
    exp = [
        ("autogen_ext.OpenAIChatCompletionClient.create", 0),
        ("openai.chat.completions.create", 1),
        ("openai.chat.completions.create", 0),
    ]
    assert got == exp
    summary = calls[0].summary
    assert "usage" in summary
    assert model_name in summary["usage"]
    assert summary["usage"][model_name]["requests"] == 1
    assert summary["usage"][model_name]["prompt_tokens"] > 0
    assert summary["usage"][model_name]["completion_tokens"] > 0
    assert summary["usage"][model_name]["total_tokens"] > 0


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
@pytest.mark.asyncio
@pytest.mark.disable_logging_error_check(reason="This test is expected to fail")
async def test_simple_client_create_with_exception(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    from autogen_core.models import UserMessage
    from autogen_ext.models.openai import OpenAIChatCompletionClient
    from openai import AuthenticationError

    model_name = "gpt-4.1-nano-2025-04-14"
    openai_model_client = OpenAIChatCompletionClient(
        model=model_name, api_key="DUMMY_API_KEY"
    )
    with pytest.raises(AuthenticationError):
        _ = await openai_model_client.create(
            [UserMessage(content="Hello, how are you?", source="user")]
        )
        calls = list(client.calls())
        assert len(calls) == 3
        flattened = flatten_calls(calls)
        assert len(flattened) == 4
        got = [(op_name_from_ref(c.op_name), d) for (c, d) in flattened]
        exp = [
            ("autogen_ext.OpenAIChatCompletionClient.create", 0),
            ("openai.chat.completions.create", 1),
            ("openai.chat.completions.create", 0),
            ("openai.chat.completions.create", 0),
        ]
        assert got == exp
        summary = calls[0].summary
        assert "status_counts" in summary
        assert summary["status_counts"]["success"] == 0
        assert summary["status_counts"]["error"] == 2
        assert "weave" in summary
        assert summary["weave"]["status"] == "error"
        assert summary["weave"]["trace_name"] == exp[0][0]
        assert summary["weave"]["latency_ms"] > 0


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
@pytest.mark.asyncio
async def test_simple_client_create_stream(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    from autogen_core.models import UserMessage
    from autogen_ext.models.openai import OpenAIChatCompletionClient

    model_name = "gpt-4.1-nano-2025-04-14"
    openai_model_client = OpenAIChatCompletionClient(model=model_name)
    response = openai_model_client.create_stream(
        [UserMessage(content="Hello, how are you?", source="user")]
    )
    async for _ in response:
        _

    calls = list(client.calls())
    assert len(calls) == 2
    flattened = flatten_calls(calls)
    assert len(flattened) == 3
    got = [(op_name_from_ref(c.op_name), d) for (c, d) in flattened]
    exp = [
        ("autogen_ext.OpenAIChatCompletionClient.create_stream", 0),
        ("openai.chat.completions.create", 1),
        ("openai.chat.completions.create", 0),
    ]
    assert got == exp
    summary = calls[0].summary
    assert "usage" in summary
    assert model_name in summary["usage"]
    assert summary["usage"][model_name]["requests"] == 1
    assert summary["usage"][model_name]["prompt_tokens"] > 0
    assert summary["usage"][model_name]["completion_tokens"] > 0
    assert summary["usage"][model_name]["total_tokens"] > 0


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
@pytest.mark.asyncio
async def test_simple_cached_client_create(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    from autogen_core._cache_store import InMemoryStore
    from autogen_core.models import UserMessage
    from autogen_ext.models.cache import CHAT_CACHE_VALUE_TYPE, ChatCompletionCache
    from autogen_ext.models.openai import OpenAIChatCompletionClient

    model_name = "gpt-4.1-nano-2025-04-14"
    # Initialize the original client
    openai_model_client = OpenAIChatCompletionClient(model=model_name)

    cache_store = InMemoryStore[CHAT_CACHE_VALUE_TYPE]()
    cache_client = ChatCompletionCache(openai_model_client, cache_store)

    await cache_client.create(
        [UserMessage(content="Hello, how are you?", source="user")]
    )
    await cache_client.create(
        [UserMessage(content="Hello, how are you?", source="user")]
    )
    calls = list(client.calls())
    assert len(calls) == 9
    flattened = flatten_calls(calls)
    print(len(flattened))
    assert len(flattened) == 19
    got = [(op_name_from_ref(c.op_name), d) for (c, d) in flattened]
    exp = [
        ("autogen_ext.ChatCompletionCache.create", 0),
        ("autogen_ext.ChatCompletionCache-check_cache", 1),
        ("autogen_core.InMemoryStore.get", 2),
        ("autogen_ext.OpenAIChatCompletionClient.create", 1),
        ("openai.chat.completions.create", 2),
        ("autogen_core.InMemoryStore.set", 1),
        ("autogen_ext.ChatCompletionCache-check_cache", 0),
        ("autogen_core.InMemoryStore.get", 1),
        ("autogen_core.InMemoryStore.get", 0),
        ("autogen_ext.OpenAIChatCompletionClient.create", 0),
        ("openai.chat.completions.create", 1),
        ("openai.chat.completions.create", 0),
        ("autogen_core.InMemoryStore.set", 0),
        ("autogen_ext.ChatCompletionCache.create", 0),
        ("autogen_ext.ChatCompletionCache-check_cache", 1),
        ("autogen_core.InMemoryStore.get", 2),
        ("autogen_ext.ChatCompletionCache-check_cache", 0),
        ("autogen_core.InMemoryStore.get", 1),
        ("autogen_core.InMemoryStore.get", 0),
    ]
    assert got == exp


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
@pytest.mark.asyncio
async def test_simple_cached_client_create_stream(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    from autogen_core._cache_store import InMemoryStore
    from autogen_core.models import UserMessage
    from autogen_ext.models.cache import CHAT_CACHE_VALUE_TYPE, ChatCompletionCache
    from autogen_ext.models.openai import OpenAIChatCompletionClient

    model_name = "gpt-4.1-nano-2025-04-14"
    # Initialize the original client
    openai_model_client = OpenAIChatCompletionClient(model=model_name)

    cache_store = InMemoryStore[CHAT_CACHE_VALUE_TYPE]()
    cache_client = ChatCompletionCache(openai_model_client, cache_store)

    async for _ in cache_client.create_stream(
        [UserMessage(content="Hello, how are you?", source="user")]
    ):
        _
    async for _ in cache_client.create_stream(
        [UserMessage(content="Hello, how are you?", source="user")]
    ):
        _
    calls = list(client.calls())
    assert len(calls) == 9
    flattened = flatten_calls(calls)
    print(len(flattened))
    assert len(flattened) == 12
    got = [(op_name_from_ref(c.op_name), d) for (c, d) in flattened]
    exp = [
        ("autogen_ext.ChatCompletionCache.create_stream", 0),
        ("autogen_ext.ChatCompletionCache-check_cache", 0),
        ("autogen_core.InMemoryStore.get", 1),
        ("autogen_core.InMemoryStore.get", 0),
        ("autogen_core.InMemoryStore.set", 0),
        ("autogen_ext.OpenAIChatCompletionClient.create_stream", 0),
        ("openai.chat.completions.create", 1),
        ("openai.chat.completions.create", 0),
        ("autogen_ext.ChatCompletionCache.create_stream", 0),
        ("autogen_ext.ChatCompletionCache-check_cache", 0),
        ("autogen_core.InMemoryStore.get", 1),
        ("autogen_core.InMemoryStore.get", 0),
    ]
    assert got == exp


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
@pytest.mark.asyncio
async def test_agentchat_run_with_tool(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    from autogen_agentchat.agents import AssistantAgent
    from autogen_ext.models.openai import OpenAIChatCompletionClient

    def get_weather(city: str) -> str:
        return f"The weather in {city} is 73 degrees and Sunny."

    model_name = "gpt-4.1-nano-2025-04-14"
    model_client = OpenAIChatCompletionClient(model=model_name)
    agent = AssistantAgent(
        name="weather_agent",
        model_client=model_client,
        tools=[get_weather],
        system_message="You are a helpful assistant.",
        reflect_on_tool_use=True,
        model_client_stream=False,
    )
    # Simulate a chat task
    result = await agent.run(task="What is the weather in New York?")
    calls = list(client.calls())
    assert len(calls) == 8
    call = calls[0]
    assert call.exception is None and call.ended_at is not None
    output = call.output
    assert len(output.messages) == len(result.messages)
    flattened = flatten_calls(calls)
    assert len(flattened) == 28
    got = [(op_name_from_ref(c.op_name), d) for (c, d) in flattened]
    exp = [
        ("autogen_agentchat.AssistantAgent.run", 0),
        ("autogen_agentchat.AssistantAgent.on_messages", 1),
        ("autogen_agentchat.AssistantAgent.on_messages_stream", 2),
        ("autogen_ext.OpenAIChatCompletionClient.create", 3),
        ("openai.chat.completions.create", 4),
        ("autogen_core.FunctionTool.run", 3),
        ("autogen_ext.OpenAIChatCompletionClient.create", 3),
        ("openai.chat.completions.create", 4),
        ("autogen_agentchat.AssistantAgent.on_messages", 0),
        ("autogen_agentchat.AssistantAgent.on_messages_stream", 1),
        ("autogen_ext.OpenAIChatCompletionClient.create", 2),
        ("openai.chat.completions.create", 3),
        ("autogen_core.FunctionTool.run", 2),
        ("autogen_ext.OpenAIChatCompletionClient.create", 2),
        ("openai.chat.completions.create", 3),
        ("autogen_agentchat.AssistantAgent.on_messages_stream", 0),
        ("autogen_ext.OpenAIChatCompletionClient.create", 1),
        ("openai.chat.completions.create", 2),
        ("autogen_core.FunctionTool.run", 1),
        ("autogen_ext.OpenAIChatCompletionClient.create", 1),
        ("openai.chat.completions.create", 2),
        ("autogen_ext.OpenAIChatCompletionClient.create", 0),
        ("openai.chat.completions.create", 1),
        ("openai.chat.completions.create", 0),
        ("autogen_core.FunctionTool.run", 0),
        ("autogen_ext.OpenAIChatCompletionClient.create", 0),
        ("openai.chat.completions.create", 1),
        ("openai.chat.completions.create", 0),
    ]
    expected_trace_name = exp[0][0]

    assert got == exp

    # Check the summary
    summary = call.summary
    assert "status_counts" in summary
    assert summary["status_counts"]["success"] == 2
    assert summary["status_counts"]["error"] == 0

    assert "weave" in summary
    assert summary["weave"]["status"] == "success"
    assert summary["weave"]["trace_name"] == expected_trace_name
    assert summary["weave"]["latency_ms"] > 0


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
@pytest.mark.asyncio
async def test_agentchat_run_stream_with_tool(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    from autogen_agentchat.agents import AssistantAgent
    from autogen_ext.models.openai import OpenAIChatCompletionClient

    def get_weather(city: str) -> str:
        return f"The weather in {city} is 73 degrees and Sunny."

    model_name = "gpt-4.1-nano-2025-04-14"
    model_client = OpenAIChatCompletionClient(model=model_name)
    agent = AssistantAgent(
        name="weather_agent",
        model_client=model_client,
        tools=[get_weather],
        system_message="You are a helpful assistant.",
        reflect_on_tool_use=True,
        model_client_stream=True,
    )
    # Simulate a chat task
    async for _ in agent.run_stream(task="What is the weather in New York?"):
        _
    calls = list(client.calls())
    assert len(calls) == 7
    call = calls[0]
    assert call.exception is None and call.ended_at is not None
    flattened = flatten_calls(calls)
    assert len(flattened) == 20
    got = [(op_name_from_ref(c.op_name), d) for (c, d) in flattened]
    exp = [
        ("autogen_agentchat.AssistantAgent.run_stream", 0),
        ("autogen_agentchat.AssistantAgent.on_messages_stream", 1),
        ("autogen_ext.OpenAIChatCompletionClient.create_stream", 2),
        ("openai.chat.completions.create", 3),
        ("autogen_core.FunctionTool.run", 2),
        ("autogen_ext.OpenAIChatCompletionClient.create_stream", 2),
        ("openai.chat.completions.create", 3),
        ("autogen_agentchat.AssistantAgent.on_messages_stream", 0),
        ("autogen_ext.OpenAIChatCompletionClient.create_stream", 1),
        ("openai.chat.completions.create", 2),
        ("autogen_core.FunctionTool.run", 1),
        ("autogen_ext.OpenAIChatCompletionClient.create_stream", 1),
        ("openai.chat.completions.create", 2),
        ("autogen_ext.OpenAIChatCompletionClient.create_stream", 0),
        ("openai.chat.completions.create", 1),
        ("openai.chat.completions.create", 0),
        ("autogen_core.FunctionTool.run", 0),
        ("autogen_ext.OpenAIChatCompletionClient.create_stream", 0),
        ("openai.chat.completions.create", 1),
        ("openai.chat.completions.create", 0),
    ]
    expected_trace_name = exp[0][0]

    assert exp == got

    # Check the summary
    summary = call.summary
    assert "status_counts" in summary
    assert summary["status_counts"]["success"] == 7
    assert summary["status_counts"]["error"] == 0

    assert "weave" in summary
    assert summary["weave"]["status"] == "success"
    assert summary["weave"]["trace_name"] == expected_trace_name
    assert summary["weave"]["latency_ms"] > 0
