"""Tests for ref conversion: external weave:/// URIs to internal refs.

The pipeline is:
1. convert_same_project_ref parses a weave:/// URI via Ref.parse_uri, returns
   an Internal*Ref object (caller uses .uri for the string)
2. convert_cross_project_ref does the same but resolves the foreign project first
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from weave.shared.refs_internal import (
    InternalAgentConversationRef,
    InternalAgentSpanRef,
    InternalAgentTurnRef,
    InternalCallRef,
    InternalObjectRef,
    InternalOpRef,
    InternalTableRef,
)
from weave.trace.ref_conversion import (
    CrossProjectRefError,
    ProjectNotFoundError,
    convert_cross_project_ref,
    convert_same_project_ref,
)

# ---------------------------------------------------------------------------
# convert_same_project_ref -- happy path
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("uri", "expected_type", "expected_uri", "field_name", "field_value"),
    [
        (
            "weave:///entity/proj/object/my_obj:abc123",
            InternalObjectRef,
            "weave-trace-internal:///int-id-1/object/my_obj:abc123",
            "name",
            "my_obj",
        ),
        (
            "weave:///entity/proj/op/my_op:def456",
            InternalOpRef,
            "weave-trace-internal:///int-id-1/op/my_op:def456",
            None,
            None,
        ),
        (
            "weave:///entity/proj/table/abc123",
            InternalTableRef,
            "weave-trace-internal:///int-id-1/table/abc123",
            "digest",
            "abc123",
        ),
        (
            "weave:///entity/proj/call/call-id-123",
            InternalCallRef,
            "weave-trace-internal:///int-id-1/call/call-id-123",
            "id",
            "call-id-123",
        ),
        (
            "weave:///entity/proj/agent_turn/0123456789abcdef0123456789abcdef",
            InternalAgentTurnRef,
            "weave-trace-internal:///int-id-1/agent_turn/0123456789abcdef0123456789abcdef",
            "trace_id",
            "0123456789abcdef0123456789abcdef",
        ),
        (
            "weave:///entity/proj/agent_span/0123456789abcdef",
            InternalAgentSpanRef,
            "weave-trace-internal:///int-id-1/agent_span/0123456789abcdef",
            "span_id",
            "0123456789abcdef",
        ),
        (
            "weave:///entity/proj/agent_conversation/sess-abc-123",
            InternalAgentConversationRef,
            "weave-trace-internal:///int-id-1/agent_conversation/sess-abc-123",
            "conversation_id",
            "sess-abc-123",
        ),
        (
            "weave:///entity/proj/agent_conversation/user%2F42%3Asession",
            InternalAgentConversationRef,
            "weave-trace-internal:///int-id-1/agent_conversation/user%2F42%3Asession",
            "conversation_id",
            "user/42:session",
        ),
    ],
    ids=[
        "object",
        "op",
        "table",
        "call",
        "agent_turn",
        "agent_span",
        "agent_conversation",
        "agent_conversation_encoded",
    ],
)
def test_same_project_happy_path(
    uri: str,
    expected_type: type,
    expected_uri: str,
    field_name: str | None,
    field_value: object,
) -> None:
    """Each ref kind parses to its Internal*Ref with the rewritten internal uri."""
    result = convert_same_project_ref(
        uri,
        ext_project_id="entity/proj",
        internal_project_id="int-id-1",
    )
    assert isinstance(result, expected_type)
    assert result.uri == expected_uri
    if field_name is not None:
        assert getattr(result, field_name) == field_value


@pytest.mark.parametrize(
    ("uri", "expected_extra", "expected_uri"),
    [
        (
            "weave:///entity/proj/object/ds:abc/attr/rows/id/rowdigest",
            ["attr", "rows", "id", "rowdigest"],
            "weave-trace-internal:///int-id-1/object/ds:abc/attr/rows/id/rowdigest",
        ),
        (
            "weave:///entity/proj/object/ds:abc/attr/items/index/3",
            ["attr", "items", "index", "3"],
            "weave-trace-internal:///int-id-1/object/ds:abc/attr/items/index/3",
        ),
    ],
    ids=["rows_id", "items_index"],
)
def test_same_project_preserves_extra_path(
    uri: str, expected_extra: list[str], expected_uri: str
) -> None:
    """Extra path (attr/rows/id/... or .../index/N) is validated and preserved."""
    result = convert_same_project_ref(
        uri,
        ext_project_id="entity/proj",
        internal_project_id="int-id-1",
    )
    assert isinstance(result, InternalObjectRef)
    assert result.extra == expected_extra
    assert result.uri == expected_uri


# ---------------------------------------------------------------------------
# convert_same_project_ref -- error cases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("uri", "exc", "match"),
    [
        (
            "weave:///other/proj/object/thing:xyz",
            CrossProjectRefError,
            "other/proj",
        ),
        ("https://example.com/foo", ValueError, "Invalid URI"),
        ("weave:///onlyonepart", ValueError, "Invalid URI"),
        (
            "weave-trace-internal:///int-id/object/thing:abc",
            ValueError,
            "Invalid URI",
        ),
        ("weave:///entity/proj/unknown/foo:bar", ValueError, "Unknown ref kind"),
    ],
    ids=["cross_project", "non_weave", "malformed", "already_internal", "unknown_kind"],
)
def test_same_project_error_cases(uri: str, exc: type[Exception], match: str) -> None:
    """Cross-project, non-weave, malformed, already-internal, and unknown kinds all raise."""
    with pytest.raises(exc, match=match):
        convert_same_project_ref(
            uri,
            ext_project_id="entity/proj",
            internal_project_id="int-id-1",
        )


# ---------------------------------------------------------------------------
# convert_cross_project_ref
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("uri", "expected_type", "expected_uri"),
    [
        (
            "weave:///other_entity/other_proj/object/thing:xyz",
            InternalObjectRef,
            "weave-trace-internal:///other-int-id/object/thing:xyz",
        ),
        (
            "weave:///other_entity/other_proj/agent_turn/0123456789abcdef0123456789abcdef",
            InternalAgentTurnRef,
            "weave-trace-internal:///other-int-id/agent_turn/0123456789abcdef0123456789abcdef",
        ),
    ],
    ids=["object", "agent_turn"],
)
def test_cross_project_resolves_via_resolver(
    uri: str, expected_type: type, expected_uri: str
) -> None:
    """Foreign project id is resolved and the ref is rewritten to the internal uri."""
    resolver = MagicMock()
    resolver.resolve_external_to_internal_project_id.return_value = "other-int-id"

    result = convert_cross_project_ref(
        uri,
        ext_project_id="entity/proj",
        resolver=resolver,
    )
    assert isinstance(result, expected_type)
    assert result.uri == expected_uri
    resolver.resolve_external_to_internal_project_id.assert_called_once_with(
        "other_entity/other_proj"
    )


def test_cross_project_raises_when_unresolvable() -> None:
    resolver = MagicMock()
    resolver.resolve_external_to_internal_project_id.return_value = None

    with pytest.raises(ProjectNotFoundError, match="other_entity/other_proj"):
        convert_cross_project_ref(
            "weave:///other_entity/other_proj/object/thing:xyz",
            ext_project_id="entity/proj",
            resolver=resolver,
        )


def test_cross_project_raises_for_same_project() -> None:
    resolver = MagicMock()

    with pytest.raises(CrossProjectRefError, match="same project"):
        convert_cross_project_ref(
            "weave:///entity/proj/object/thing:xyz",
            ext_project_id="entity/proj",
            resolver=resolver,
        )
    resolver.resolve_external_to_internal_project_id.assert_not_called()


def test_cross_project_raises_for_non_weave_uri() -> None:
    resolver = MagicMock()

    with pytest.raises(ValueError, match="Invalid URI"):
        convert_cross_project_ref(
            "https://example.com/foo",
            ext_project_id="entity/proj",
            resolver=resolver,
        )
