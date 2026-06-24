"""Unit tests for the generic agent-name override.

Exercises ``weave.session.agent_name_override`` and the internal
``resolve_agent_name`` resolver that auto-instrumentation integrations call.
"""

from __future__ import annotations

import pytest

from weave.session import agent_name_override
from weave.session.agent_context import resolve_agent_name


def test_resolve_returns_default_when_unset() -> None:
    assert resolve_agent_name("claude_agent_sdk") == "claude_agent_sdk"


def test_override_wins_over_default_and_native_name() -> None:
    with agent_name_override("researcher"):
        # over an integration default...
        assert resolve_agent_name("claude_agent_sdk") == "researcher"
        # ...and over a non-empty SDK-native name.
        assert resolve_agent_name("Assistant") == "researcher"


def test_nested_overrides_restore_outer_then_default() -> None:
    with agent_name_override("outer"):
        assert resolve_agent_name("d") == "outer"
        with agent_name_override("inner"):
            assert resolve_agent_name("d") == "inner"
        assert resolve_agent_name("d") == "outer"
    assert resolve_agent_name("d") == "d"


@pytest.mark.parametrize("bad_name", ["", "   ", "\n\t"])
def test_override_rejects_empty(bad_name: str) -> None:
    with pytest.raises(ValueError, match="non-empty"):
        with agent_name_override(bad_name):
            pass
