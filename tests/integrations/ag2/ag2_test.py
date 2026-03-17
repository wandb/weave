"""Tests for AG2 (formerly AutoGen) Weave integration."""

import pytest

import weave
from weave.integrations.ag2.ag2_sdk import get_ag2_patcher
from weave.integrations.integration_utilities import (
    flatten_calls,
    op_name_from_ref,
)

PATCHER = None


@pytest.fixture(autouse=True)
def patch_ag2():
    """Apply AG2 patches for each test."""
    global PATCHER  # noqa: PLW0603
    from weave.integrations.ag2.ag2_sdk import (
        get_ag2_patcher,
    )

    PATCHER = get_ag2_patcher()
    PATCHER.attempt_patch()
    yield
    PATCHER.undo_patch()


@pytest.mark.asyncio
@pytest.mark.vcr
async def test_two_agent_with_tool(client):
    """Two-agent conversation with a tool call."""
    from typing import Annotated

    from autogen import ConversableAgent, LLMConfig

    llm_config = LLMConfig(
        {
            "model": "gpt-4o-mini",
            "api_key": "test-key",
        }
    )

    def get_weather(
        city: Annotated[str, "City name"],
    ) -> str:
        """Get the weather for a city."""
        return f"Sunny, 72\u00b0F in {city}"

    assistant = ConversableAgent(
        name="assistant",
        system_message="Help the user. Use tools when needed.",
        llm_config=llm_config,
        functions=[get_weather],
    )

    user = ConversableAgent(
        name="user", human_input_mode="NEVER"
    )

    result = user.initiate_chat(
        assistant,
        message="What's the weather in Paris?",
        max_turns=2,
    )

    # Verify trace structure
    calls = client.calls()
    flat = flatten_calls(calls)
    op_names = [op_name_from_ref(c.op_name) for c in flat]

    assert "ag2.ConversableAgent.initiate_chat" in op_names
    assert "ag2.OpenAIWrapper.create" in op_names


@pytest.mark.asyncio
@pytest.mark.vcr
async def test_three_agent_group_chat(client):
    """Three-agent group chat with GroupChatManager."""
    from autogen import ConversableAgent, LLMConfig
    from autogen.agentchat import initiate_group_chat
    from autogen.agentchat.group.patterns import AutoPattern

    llm_config = LLMConfig(
        {
            "model": "gpt-4o-mini",
            "api_key": "test-key",
        }
    )

    researcher = ConversableAgent(
        name="researcher",
        system_message="Research the topic briefly.",
        llm_config=llm_config,
    )

    writer = ConversableAgent(
        name="writer",
        system_message="Write a one-sentence summary.",
        llm_config=llm_config,
    )

    critic = ConversableAgent(
        name="critic",
        system_message="Say OK if good. End with TERMINATE.",
        llm_config=llm_config,
    )

    user = ConversableAgent(
        name="user", human_input_mode="NEVER"
    )

    pattern = AutoPattern(
        initial_agent=researcher,
        agents=[researcher, writer, critic],
        user_agent=user,
        group_manager_args={"llm_config": llm_config},
    )

    result, ctx, last = initiate_group_chat(
        pattern=pattern,
        messages="Explain quantum computing in one line.",
        max_rounds=5,
    )

    # Verify trace structure
    calls = client.calls()
    flat = flatten_calls(calls)
    op_names = [op_name_from_ref(c.op_name) for c in flat]

    assert "ag2.initiate_group_chat" in op_names
    assert "ag2.OpenAIWrapper.create" in op_names
    # Should have multiple LLM calls (one per agent turn)
    llm_calls = [
        n
        for n in op_names
        if n == "ag2.OpenAIWrapper.create"
    ]
    assert len(llm_calls) >= 2
