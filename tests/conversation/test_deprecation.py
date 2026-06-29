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
