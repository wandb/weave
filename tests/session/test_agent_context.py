"""Unit tests for the generic agent-name override.

These exercise the integration-agnostic mechanism only:
``weave.session.agent_name_override`` (the public context manager) and the
internal ``resolve_agent_name_or_default(default)`` that auto-instrumentation integrations
call when naming their ``invoke_agent`` span.

``resolve_agent_name_or_default(default)`` returns the user's active override
when one is set, otherwise the ``default`` name the calling integration would use
on its own (claude uses ``"claude_agent_sdk"``; openai_agents uses the SDK-native
agent name). The agent names below are illustrative — the resolver is
integration-agnostic and doesn't know who is calling.
"""

from __future__ import annotations

import pytest

from weave.session import agent_name_override
from weave.session.agent_context import resolve_agent_name_or_default


def test_no_override_keeps_the_default_name() -> None:
    # No override active: the agent keeps the default name it would otherwise get.
    assert resolve_agent_name_or_default("default_agent_name") == "default_agent_name"


def test_override_replaces_the_default_name() -> None:
    # A user labels their agent; that name is what gets used...
    with agent_name_override("research_agent"):
        assert resolve_agent_name_or_default("default_agent_name") == "research_agent"
        # ...and it wins no matter what default the integration would have used.
        assert (
            resolve_agent_name_or_default("customer_support_agent") == "research_agent"
        )


def test_nested_overrides_restore_outer_then_default() -> None:
    with agent_name_override("research_agent"):
        assert resolve_agent_name_or_default("default_agent_name") == "research_agent"
        with agent_name_override("summarizer_agent"):
            assert (
                resolve_agent_name_or_default("default_agent_name")
                == "summarizer_agent"
            )
        assert resolve_agent_name_or_default("default_agent_name") == "research_agent"
    assert resolve_agent_name_or_default("default_agent_name") == "default_agent_name"


def test_none_default_coalesces_to_empty_string() -> None:
    # An integration that didn't name the agent passes None; the resolver returns
    # "" so callers never have to write `or ""`. An override still wins.
    assert resolve_agent_name_or_default(None) == ""
    with agent_name_override("research_agent"):
        assert resolve_agent_name_or_default(None) == "research_agent"


@pytest.mark.parametrize("bad_name", ["", "   ", "\n\t"])
def test_override_rejects_empty(bad_name: str) -> None:
    with pytest.raises(ValueError, match="non-empty"):
        with agent_name_override(bad_name):
            pass
