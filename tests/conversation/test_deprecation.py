"""The deprecated ``session`` aliases forward to the Conversation SDK.

These cover the back-compat surface added when the Session SDK was renamed
to the Conversation SDK: the old ``weave.start_session`` / ``Session`` / etc.
names still work, emit a ``DeprecationWarning``, and translate the old
``session_id`` / ``session_name`` arguments to their ``conversation`` forms.
"""

from __future__ import annotations

import importlib

import pytest

import weave


def test_start_session_forwards_and_warns() -> None:
    with pytest.warns(DeprecationWarning, match="start_session"):
        conv = weave.start_session(
            agent_name="bot", session_id="c1", session_name="demo"
        )
    assert type(conv).__name__ == "Conversation"
    assert conv.conversation_id == "c1"
    assert conv.conversation_name == "demo"
    conv.end()


def test_session_class_maps_old_fields_and_warns() -> None:
    with pytest.warns(DeprecationWarning, match="Session"):
        s = weave.Session(session_id="c2", session_name="d2")
    assert s.conversation_id == "c2"
    assert s.conversation_name == "d2"


def test_session_instance_supports_old_field_read_and_write() -> None:
    """``session_id`` / ``session_name`` work as instance properties.

    The original ``Session`` had these as model fields, so old code that reads
    or assigns them on an instance must keep working; they proxy to the
    ``conversation_*`` fields in both directions.
    """
    with pytest.warns(DeprecationWarning, match="Session"):
        s = weave.Session(session_id="c5", session_name="d5")

    assert s.session_id == "c5"
    assert s.session_name == "d5"

    s.session_id = "c5-updated"
    s.session_name = "d5-updated"

    assert s.session_id == "c5-updated"
    assert s.session_name == "d5-updated"
    assert s.conversation_id == "c5-updated"
    assert s.conversation_name == "d5-updated"


def test_end_and_get_current_session_warn() -> None:
    with pytest.warns(DeprecationWarning, match="start_session"):
        s = weave.start_session(session_id="c3")
    with pytest.warns(DeprecationWarning, match="get_current_session"):
        assert weave.get_current_session() is s
    with pytest.warns(DeprecationWarning, match="end_session"):
        weave.end_session()
    with pytest.warns(DeprecationWarning, match="get_current_session"):
        assert weave.get_current_session() is None


def test_log_session_forwards_and_warns() -> None:
    with pytest.warns(DeprecationWarning, match="log_session"):
        result = weave.log_session(turns=[], session_id="c4")
    assert result.conversation_id == "c4"


def test_turn_span_method_aliases_forward_and_warn() -> None:
    turn = weave.Turn(model="gpt-4o")

    with pytest.warns(DeprecationWarning, match="Turn.llm"):
        llm = turn.llm(provider_name="openai", system_instructions=["be brief"])
    assert isinstance(llm, weave.LLM)
    assert llm.model == "gpt-4o"
    assert llm.provider_name == "openai"
    assert llm.system_instructions == ["be brief"]
    llm.end()

    with pytest.warns(DeprecationWarning, match="Turn.tool"):
        tool = turn.tool(
            name="get_weather", arguments='{"city":"Tokyo"}', tool_call_id="tc_1"
        )
    assert isinstance(tool, weave.Tool)
    assert tool.name == "get_weather"
    assert tool.arguments == '{"city":"Tokyo"}'
    assert tool.tool_call_id == "tc_1"

    with pytest.warns(DeprecationWarning, match="Turn.subagent"):
        subagent = turn.subagent(name="research-bot")
    assert isinstance(subagent, weave.SubAgent)
    assert subagent.name == "research-bot"
    assert subagent.model == "gpt-4o"


def test_subagent_span_method_aliases_forward_and_warn() -> None:
    subagent = weave.SubAgent(name="research-bot", model="gpt-4o-mini")

    with pytest.warns(DeprecationWarning, match="SubAgent.llm"):
        llm = subagent.llm(provider_name="openai", system_instructions=["research"])
    assert isinstance(llm, weave.LLM)
    assert llm.model == "gpt-4o-mini"
    assert llm.provider_name == "openai"
    assert llm.system_instructions == ["research"]
    llm.end()

    with pytest.warns(DeprecationWarning, match="SubAgent.tool"):
        tool = subagent.tool(
            name="web_search", arguments='{"q":"X"}', tool_call_id="tc_2"
        )
    assert isinstance(tool, weave.Tool)
    assert tool.name == "web_search"
    assert tool.arguments == '{"q":"X"}'
    assert tool.tool_call_id == "tc_2"


def test_legacy_import_path_warns_and_reexports() -> None:
    import weave.session as legacy

    # Re-importing the deprecated path emits the module-level warning.
    with pytest.warns(DeprecationWarning, match="weave.session has been renamed"):
        importlib.reload(legacy)

    # Unchanged names are still re-exported from the old path, identical to
    # the canonical objects; the session-named callables forward to weave's.
    from weave.conversation import TextPart

    assert legacy.TextPart is TextPart
    assert legacy.start_session is weave.start_session
    assert legacy.Session is weave.Session
