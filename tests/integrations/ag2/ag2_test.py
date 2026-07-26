"""Tests for AG2 (formerly AutoGen) Weave integration."""

from typing import Annotated

import pytest
from autogen import ConversableAgent, LLMConfig
from autogen.agentchat import initiate_group_chat
from autogen.agentchat.group.patterns import AutoPattern

from weave.integrations.ag2.ag2_sdk import get_ag2_patcher
from weave.integrations.integration_utilities import (
    flatten_calls,
    flattened_calls_to_names,
)
from weave.trace_server.trace_server_interface import CallsFilter


@pytest.fixture(autouse=True)
def patch_ag2():
    """Apply AG2 patches for each test."""
    patcher = get_ag2_patcher()
    patcher.attempt_patch()
    yield
    patcher.undo_patch()


@pytest.mark.vcr
def test_two_agent_with_tool(client):
    """Two-agent conversation with a tool call."""
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
    calls = list(client.get_calls(filter=CallsFilter(trace_roots_only=True)))
    flat = flatten_calls(calls)
    names = flattened_calls_to_names(flat)
    op_names = [name for name, _depth in names]

    assert any("initiate_chat" in n for n in op_names)
    assert any("create" in n for n in op_names)


@pytest.mark.vcr
def test_three_agent_group_chat(client):
    """Three-agent group chat."""
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

    result, _ctx, _last = initiate_group_chat(
        pattern=pattern,
        messages="Explain quantum computing in one line.",
        max_rounds=5,
    )

    # Verify trace structure
    calls = list(client.get_calls(filter=CallsFilter(trace_roots_only=True)))
    flat = flatten_calls(calls)
    names = flattened_calls_to_names(flat)
    op_names = [name for name, _depth in names]

    assert any("initiate_chat" in n for n in op_names)
    assert any("create" in n for n in op_names)
    # Should have multiple LLM calls (one per agent turn)
    llm_calls = [n for n in op_names if "create" in n]
    assert len(llm_calls) >= 2
