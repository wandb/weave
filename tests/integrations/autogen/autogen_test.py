from collections.abc import Generator

import pytest

import weave
from weave.integrations.autogen import get_autogen_patcher
from weave.integrations.integration_utilities import flatten_calls, op_name_from_ref
from weave.integrations.openai.openai_sdk import get_openai_patcher


@pytest.fixture(autouse=True)
def patch_autogen() -> Generator[None, None, None]:
    """Patch AutoGen and OpenAI for all tests in this file."""
    autogen_patcher = get_autogen_patcher()
    openai_patcher = get_openai_patcher()

    autogen_patcher.attempt_patch()
    openai_patcher.attempt_patch()

    yield

    autogen_patcher.undo_patch()
    openai_patcher.undo_patch()


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
    calls = list(client.get_calls())
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
        calls = list(client.get_calls())
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
        pass

    calls = list(client.get_calls())
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
    calls = list(client.get_calls())
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
        pass
    async for _ in cache_client.create_stream(
        [UserMessage(content="Hello, how are you?", source="user")]
    ):
        pass
    calls = list(client.get_calls())
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
        ("autogen_ext.OpenAIChatCompletionClient.create_stream", 0),
        ("openai.chat.completions.create", 1),
        ("openai.chat.completions.create", 0),
        ("autogen_core.InMemoryStore.set", 0),
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
    calls = list(client.get_calls())
    assert len(calls) == 8
    call = calls[0]
    assert call.exception is None
    assert call.ended_at is not None
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
        pass
    calls = list(client.get_calls())
    assert len(calls) == 7
    call = calls[0]
    assert call.exception is None
    assert call.ended_at is not None
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


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
@pytest.mark.asyncio
async def test_agentchat_group_chat(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    from autogen_agentchat.agents import AssistantAgent
    from autogen_agentchat.conditions import TextMessageTermination
    from autogen_agentchat.teams import RoundRobinGroupChat
    from autogen_ext.models.openai import OpenAIChatCompletionClient

    model = "gpt-4.1-nano-2025-04-14"
    model_client = OpenAIChatCompletionClient(
        model=model,
        parallel_tool_calls=False,
    )

    # Create a tool for incrementing a number.
    def increment_number(number: int) -> int:
        """Increment a number by 1."""
        return number + 1

    # Create a tool agent that uses the increment_number function.
    looped_assistant = AssistantAgent(
        "looped_assistant",
        model_client=model_client,
        tools=[increment_number],  # Register the tool.
        system_message="You are a helpful AI assistant, use the tool to increment the number.",
    )

    # Termination condition that stops the task if the agent responds with a text message.
    termination_condition = TextMessageTermination("looped_assistant")

    # Create a team with the looped assistant agent and the termination condition.
    team = RoundRobinGroupChat(
        [looped_assistant],
        termination_condition=termination_condition,
    )

    # Run the team with a task and print the messages to the console.
    async for _ in team.run_stream(task="Increment the number 1 to 3."):
        pass
    await model_client.close()
    calls = list(client.get_calls())
    call = calls[0]
    assert call.exception is None
    assert call.ended_at is not None

    assert len(calls) == 60
    flattened = flatten_calls(calls)
    assert len(flattened) == 203
    got = [(op_name_from_ref(c.op_name), d) for (c, d) in flattened]
    exp = [
        ("autogen_agentchat.RoundRobinGroupChat.run_stream", 0),
        ("autogen_core.SingleThreadedAgentRuntime.send_message", 1),
        ("autogen_agentchat.RoundRobinGroupChatManager.on_message", 1),
        ("autogen_agentchat.RoundRobinGroupChatManager.publish_message", 2),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 3),
        ("autogen_agentchat.RoundRobinGroupChatManager.publish_message", 2),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 3),
        ("autogen_agentchat.RoundRobinGroupChatManager.publish_message", 2),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 3),
        ("autogen_agentchat.ChatAgentContainer.on_message", 1),
        ("autogen_agentchat.ChatAgentContainer.on_message", 1),
        ("autogen_agentchat.AssistantAgent.on_messages_stream", 2),
        ("autogen_ext.OpenAIChatCompletionClient.create", 3),
        ("openai.chat.completions.create", 4),
        ("autogen_agentchat.ChatAgentContainer.publish_message", 3),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 4),
        ("autogen_core.FunctionTool.run", 3),
        ("autogen_agentchat.ChatAgentContainer.publish_message", 3),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 4),
        ("autogen_agentchat.ChatAgentContainer.publish_message", 3),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 4),
        ("autogen_agentchat.ChatAgentContainer.publish_message", 2),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 3),
        ("autogen_agentchat.RoundRobinGroupChatManager.on_message", 1),
        ("autogen_agentchat.RoundRobinGroupChatManager.on_message", 1),
        ("autogen_agentchat.RoundRobinGroupChatManager.on_message", 1),
        ("autogen_agentchat.RoundRobinGroupChatManager.on_message", 1),
        ("autogen_agentchat.RoundRobinGroupChatManager.publish_message", 2),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 3),
        ("autogen_agentchat.ChatAgentContainer.on_message", 1),
        ("autogen_agentchat.AssistantAgent.on_messages_stream", 2),
        ("autogen_ext.OpenAIChatCompletionClient.create", 3),
        ("openai.chat.completions.create", 4),
        ("autogen_agentchat.ChatAgentContainer.publish_message", 3),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 4),
        ("autogen_core.FunctionTool.run", 3),
        ("autogen_agentchat.ChatAgentContainer.publish_message", 3),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 4),
        ("autogen_agentchat.ChatAgentContainer.publish_message", 3),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 4),
        ("autogen_agentchat.ChatAgentContainer.publish_message", 2),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 3),
        ("autogen_agentchat.RoundRobinGroupChatManager.on_message", 1),
        ("autogen_agentchat.RoundRobinGroupChatManager.on_message", 1),
        ("autogen_agentchat.RoundRobinGroupChatManager.on_message", 1),
        ("autogen_agentchat.RoundRobinGroupChatManager.on_message", 1),
        ("autogen_agentchat.RoundRobinGroupChatManager.publish_message", 2),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 3),
        ("autogen_agentchat.ChatAgentContainer.on_message", 1),
        ("autogen_agentchat.AssistantAgent.on_messages_stream", 2),
        ("autogen_ext.OpenAIChatCompletionClient.create", 3),
        ("openai.chat.completions.create", 4),
        ("autogen_agentchat.ChatAgentContainer.publish_message", 3),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 4),
        ("autogen_agentchat.ChatAgentContainer.publish_message", 2),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 3),
        ("autogen_agentchat.RoundRobinGroupChatManager.on_message", 1),
        ("autogen_agentchat.RoundRobinGroupChatManager.on_message", 1),
        ("autogen_agentchat.RoundRobinGroupChatManager.publish_message", 2),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 3),
        ("autogen_core.SingleThreadedAgentRuntime.send_message", 0),
        ("autogen_agentchat.RoundRobinGroupChatManager.on_message", 0),
        ("autogen_agentchat.RoundRobinGroupChatManager.publish_message", 1),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 2),
        ("autogen_agentchat.RoundRobinGroupChatManager.publish_message", 1),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 2),
        ("autogen_agentchat.RoundRobinGroupChatManager.publish_message", 1),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 2),
        ("autogen_agentchat.RoundRobinGroupChatManager.publish_message", 0),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 1),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 0),
        ("autogen_agentchat.RoundRobinGroupChatManager.publish_message", 0),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 1),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 0),
        ("autogen_agentchat.RoundRobinGroupChatManager.publish_message", 0),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 1),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 0),
        ("autogen_agentchat.ChatAgentContainer.on_message", 0),
        ("autogen_agentchat.ChatAgentContainer.on_message", 0),
        ("autogen_agentchat.AssistantAgent.on_messages_stream", 1),
        ("autogen_ext.OpenAIChatCompletionClient.create", 2),
        ("openai.chat.completions.create", 3),
        ("autogen_agentchat.ChatAgentContainer.publish_message", 2),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 3),
        ("autogen_core.FunctionTool.run", 2),
        ("autogen_agentchat.ChatAgentContainer.publish_message", 2),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 3),
        ("autogen_agentchat.ChatAgentContainer.publish_message", 2),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 3),
        ("autogen_agentchat.ChatAgentContainer.publish_message", 1),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 2),
        ("autogen_agentchat.AssistantAgent.on_messages_stream", 0),
        ("autogen_ext.OpenAIChatCompletionClient.create", 1),
        ("openai.chat.completions.create", 2),
        ("autogen_agentchat.ChatAgentContainer.publish_message", 1),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 2),
        ("autogen_core.FunctionTool.run", 1),
        ("autogen_agentchat.ChatAgentContainer.publish_message", 1),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 2),
        ("autogen_agentchat.ChatAgentContainer.publish_message", 1),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 2),
        ("autogen_ext.OpenAIChatCompletionClient.create", 0),
        ("openai.chat.completions.create", 1),
        ("openai.chat.completions.create", 0),
        ("autogen_agentchat.ChatAgentContainer.publish_message", 0),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 1),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 0),
        ("autogen_agentchat.RoundRobinGroupChatManager.on_message", 0),
        ("autogen_core.FunctionTool.run", 0),
        ("autogen_agentchat.ChatAgentContainer.publish_message", 0),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 1),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 0),
        ("autogen_agentchat.ChatAgentContainer.publish_message", 0),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 1),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 0),
        ("autogen_agentchat.ChatAgentContainer.publish_message", 0),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 1),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 0),
        ("autogen_agentchat.RoundRobinGroupChatManager.on_message", 0),
        ("autogen_agentchat.RoundRobinGroupChatManager.on_message", 0),
        ("autogen_agentchat.RoundRobinGroupChatManager.on_message", 0),
        ("autogen_agentchat.RoundRobinGroupChatManager.publish_message", 1),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 2),
        ("autogen_agentchat.RoundRobinGroupChatManager.publish_message", 0),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 1),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 0),
        ("autogen_agentchat.ChatAgentContainer.on_message", 0),
        ("autogen_agentchat.AssistantAgent.on_messages_stream", 1),
        ("autogen_ext.OpenAIChatCompletionClient.create", 2),
        ("openai.chat.completions.create", 3),
        ("autogen_agentchat.ChatAgentContainer.publish_message", 2),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 3),
        ("autogen_core.FunctionTool.run", 2),
        ("autogen_agentchat.ChatAgentContainer.publish_message", 2),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 3),
        ("autogen_agentchat.ChatAgentContainer.publish_message", 2),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 3),
        ("autogen_agentchat.ChatAgentContainer.publish_message", 1),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 2),
        ("autogen_agentchat.AssistantAgent.on_messages_stream", 0),
        ("autogen_ext.OpenAIChatCompletionClient.create", 1),
        ("openai.chat.completions.create", 2),
        ("autogen_agentchat.ChatAgentContainer.publish_message", 1),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 2),
        ("autogen_core.FunctionTool.run", 1),
        ("autogen_agentchat.ChatAgentContainer.publish_message", 1),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 2),
        ("autogen_agentchat.ChatAgentContainer.publish_message", 1),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 2),
        ("autogen_ext.OpenAIChatCompletionClient.create", 0),
        ("openai.chat.completions.create", 1),
        ("openai.chat.completions.create", 0),
        ("autogen_agentchat.ChatAgentContainer.publish_message", 0),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 1),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 0),
        ("autogen_agentchat.RoundRobinGroupChatManager.on_message", 0),
        ("autogen_core.FunctionTool.run", 0),
        ("autogen_agentchat.ChatAgentContainer.publish_message", 0),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 1),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 0),
        ("autogen_agentchat.ChatAgentContainer.publish_message", 0),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 1),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 0),
        ("autogen_agentchat.ChatAgentContainer.publish_message", 0),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 1),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 0),
        ("autogen_agentchat.RoundRobinGroupChatManager.on_message", 0),
        ("autogen_agentchat.RoundRobinGroupChatManager.on_message", 0),
        ("autogen_agentchat.RoundRobinGroupChatManager.on_message", 0),
        ("autogen_agentchat.RoundRobinGroupChatManager.publish_message", 1),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 2),
        ("autogen_agentchat.RoundRobinGroupChatManager.publish_message", 0),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 1),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 0),
        ("autogen_agentchat.ChatAgentContainer.on_message", 0),
        ("autogen_agentchat.AssistantAgent.on_messages_stream", 1),
        ("autogen_ext.OpenAIChatCompletionClient.create", 2),
        ("openai.chat.completions.create", 3),
        ("autogen_agentchat.ChatAgentContainer.publish_message", 2),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 3),
        ("autogen_agentchat.ChatAgentContainer.publish_message", 1),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 2),
        ("autogen_agentchat.AssistantAgent.on_messages_stream", 0),
        ("autogen_ext.OpenAIChatCompletionClient.create", 1),
        ("openai.chat.completions.create", 2),
        ("autogen_agentchat.ChatAgentContainer.publish_message", 1),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 2),
        ("autogen_ext.OpenAIChatCompletionClient.create", 0),
        ("openai.chat.completions.create", 1),
        ("openai.chat.completions.create", 0),
        ("autogen_agentchat.ChatAgentContainer.publish_message", 0),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 1),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 0),
        ("autogen_agentchat.ChatAgentContainer.publish_message", 0),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 1),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 0),
        ("autogen_agentchat.RoundRobinGroupChatManager.on_message", 0),
        ("autogen_agentchat.RoundRobinGroupChatManager.on_message", 0),
        ("autogen_agentchat.RoundRobinGroupChatManager.publish_message", 1),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 2),
        ("autogen_agentchat.RoundRobinGroupChatManager.publish_message", 0),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 1),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 0),
    ]
    expected_trace_name = exp[0][0]
    assert got == exp
    summary = call.summary
    assert "usage" in summary
    assert model in summary["usage"]
    assert summary["usage"][model]["requests"] == 3
    assert summary["usage"][model]["prompt_tokens"] > 0
    assert summary["usage"][model]["completion_tokens"] > 0
    assert summary["usage"][model]["total_tokens"] > 0

    assert "status_counts" in summary
    assert summary["status_counts"]["success"] == 60
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
async def test_agent_with_memory(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    from autogen_agentchat.agents import AssistantAgent
    from autogen_core.memory import ListMemory, MemoryContent, MemoryMimeType
    from autogen_ext.models.openai import OpenAIChatCompletionClient

    model_name = "gpt-4.1-nano-2025-04-14"

    @weave.op
    async def _run_agent():
        user_memory = ListMemory()

        # Add user preferences to memory
        await user_memory.add(
            MemoryContent(
                content="The weather should be in metric units",
                mime_type=MemoryMimeType.TEXT,
            )
        )

        await user_memory.add(
            MemoryContent(
                content="Meal recipe must be vegan", mime_type=MemoryMimeType.TEXT
            )
        )

        async def get_weather(city: str, units: str = "imperial") -> str:
            if units == "imperial":
                return f"The weather in {city} is 73 °F and Sunny."
            elif units == "metric":
                return f"The weather in {city} is 23 °C and Sunny."
            else:
                return f"Sorry, I don't know the weather in {city}."

        model_client = OpenAIChatCompletionClient(
            model=model_name,
        )
        assistant_agent = AssistantAgent(
            name="assistant_agent",
            model_client=model_client,
            tools=[get_weather],
            memory=[user_memory],
        )

        async for _ in assistant_agent.run_stream(
            task="What is the weather in New York?"
        ):
            pass

        await model_client.close()

    await _run_agent()
    calls = list(client.get_calls())
    call = calls[0]
    assert call.exception is None
    assert call.ended_at is not None
    assert len(calls) == 10
    flattened = flatten_calls(calls)
    assert len(flattened) == 31

    got = [(op_name_from_ref(c.op_name), d) for (c, d) in flattened]
    exp = [
        ("run_agent", 0),
        ("autogen_core.ListMemory.add", 1),
        ("autogen_core.ListMemory.add", 1),
        ("autogen_agentchat.AssistantAgent.run_stream", 1),
        ("autogen_agentchat.AssistantAgent.on_messages_stream", 2),
        ("autogen_core.ListMemory.update_context", 3),
        ("autogen_ext.OpenAIChatCompletionClient.create", 3),
        ("openai.chat.completions.create", 4),
        ("autogen_core.FunctionTool.run", 3),
        ("autogen_core.FunctionTool.run", 3),
        ("autogen_core.ListMemory.add", 0),
        ("autogen_core.ListMemory.add", 0),
        ("autogen_agentchat.AssistantAgent.run_stream", 0),
        ("autogen_agentchat.AssistantAgent.on_messages_stream", 1),
        ("autogen_core.ListMemory.update_context", 2),
        ("autogen_ext.OpenAIChatCompletionClient.create", 2),
        ("openai.chat.completions.create", 3),
        ("autogen_core.FunctionTool.run", 2),
        ("autogen_core.FunctionTool.run", 2),
        ("autogen_agentchat.AssistantAgent.on_messages_stream", 0),
        ("autogen_core.ListMemory.update_context", 1),
        ("autogen_ext.OpenAIChatCompletionClient.create", 1),
        ("openai.chat.completions.create", 2),
        ("autogen_core.FunctionTool.run", 1),
        ("autogen_core.FunctionTool.run", 1),
        ("autogen_core.ListMemory.update_context", 0),
        ("autogen_ext.OpenAIChatCompletionClient.create", 0),
        ("openai.chat.completions.create", 1),
        ("openai.chat.completions.create", 0),
        ("autogen_core.FunctionTool.run", 0),
        ("autogen_core.FunctionTool.run", 0),
    ]

    expected_trace_name = exp[0][0]
    assert got == exp
    summary = call.summary
    assert "usage" in summary
    assert model_name in summary["usage"]
    assert summary["usage"][model_name]["requests"] == 1
    assert summary["usage"][model_name]["prompt_tokens"] > 0
    assert summary["usage"][model_name]["completion_tokens"] > 0
    assert summary["usage"][model_name]["total_tokens"] > 0

    assert "status_counts" in summary
    assert summary["status_counts"]["success"] == 10
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
async def test_workflows_singlethreaded_runtime(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    from collections.abc import Callable
    from dataclasses import dataclass

    from autogen_core import (
        AgentId,
        DefaultTopicId,
        MessageContext,
        RoutedAgent,
        SingleThreadedAgentRuntime,
        default_subscription,
        message_handler,
    )

    @dataclass
    class Message:
        content: int

    @default_subscription
    class Modifier(RoutedAgent):
        def __init__(self, modify_val: Callable[[int], int]) -> None:
            super().__init__("A modifier agent.")
            self._modify_val = modify_val

        @message_handler
        async def handle_message(self, message: Message, ctx: MessageContext) -> None:
            val = self._modify_val(message.content)
            await self.publish_message(Message(content=val), DefaultTopicId())  # type: ignore

    @default_subscription
    class Checker(RoutedAgent):
        def __init__(self, run_until: Callable[[int], bool]) -> None:
            super().__init__("A checker agent.")
            self._run_until = run_until

        @message_handler
        async def handle_message(self, message: Message, ctx: MessageContext) -> None:
            if not self._run_until(message.content):
                await self.publish_message(
                    Message(content=message.content), DefaultTopicId()
                )

    # NOTE: this is a special case where you need to use the weave decorator
    # if you want the messages in the pubsub to be captured under a single trace
    @weave.op
    async def run_workflow() -> None:
        # Create a local embedded runtime.
        runtime = SingleThreadedAgentRuntime()

        await Modifier.register(
            runtime,
            "modifier",
            lambda: Modifier(modify_val=lambda x: x - 1),
        )

        await Checker.register(
            runtime,
            "checker",
            lambda: Checker(run_until=lambda x: x <= 1),
        )

        # Start the runtime and send a direct message to the checker.
        runtime.start()
        await runtime.send_message(Message(3), AgentId("checker", "default"))
        await runtime.stop_when_idle()

    await run_workflow()

    calls = list(client.get_calls())
    call = calls[0]
    assert call.exception is None
    assert call.ended_at is not None
    assert len(calls) == 15
    flattened = flatten_calls(calls)
    assert len(flattened) == 41
    got = [(op_name_from_ref(c.op_name), d) for (c, d) in flattened]
    exp = [
        ("run_workflow", 0),
        ("autogen_core.SingleThreadedAgentRuntime.send_message", 1),
        ("autogen_test.Checker.on_message", 1),
        ("autogen_test.Checker.publish_message", 2),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 3),
        ("autogen_test.Modifier.on_message", 1),
        ("autogen_test.Modifier.publish_message", 2),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 3),
        ("autogen_test.Checker.on_message", 1),
        ("autogen_test.Checker.publish_message", 2),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 3),
        ("autogen_test.Modifier.on_message", 1),
        ("autogen_test.Modifier.publish_message", 2),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 3),
        ("autogen_test.Checker.on_message", 1),
        ("autogen_core.SingleThreadedAgentRuntime.send_message", 0),
        ("autogen_test.Checker.on_message", 0),
        ("autogen_test.Checker.publish_message", 1),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 2),
        ("autogen_test.Checker.publish_message", 0),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 1),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 0),
        ("autogen_test.Modifier.on_message", 0),
        ("autogen_test.Modifier.publish_message", 1),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 2),
        ("autogen_test.Modifier.publish_message", 0),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 1),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 0),
        ("autogen_test.Checker.on_message", 0),
        ("autogen_test.Checker.publish_message", 1),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 2),
        ("autogen_test.Checker.publish_message", 0),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 1),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 0),
        ("autogen_test.Modifier.on_message", 0),
        ("autogen_test.Modifier.publish_message", 1),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 2),
        ("autogen_test.Modifier.publish_message", 0),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 1),
        ("autogen_core.SingleThreadedAgentRuntime.publish_message", 0),
        ("autogen_test.Checker.on_message", 0),
    ]
    expected_trace_name = exp[0][0]
    assert got == exp
    summary = call.summary
    assert "status_counts" in summary
    assert summary["status_counts"]["success"] == 15
    assert summary["status_counts"]["error"] == 0

    assert "weave" in summary
    assert summary["weave"]["status"] == "success"
    assert summary["weave"]["trace_name"] == expected_trace_name
    assert summary["weave"]["latency_ms"] > 0
