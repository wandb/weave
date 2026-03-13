"""Tests for client-side digest plumbing: project ID resolution and ref conversion.

These tests validate the external-to-internal ref conversion pipeline that to_json
will use in the follow-up PR. The pipeline is:

1. ProjectIdResolver resolves entity/project -> internal ID
2. convert_same_project_ref parses a weave:/// URI via Ref.parse_uri, returns
   an Internal*Ref object (caller uses .uri for the string)
3. convert_cross_project_ref does the same but resolves the foreign project first
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from weave.shared.refs_internal import (
    InternalCallRef,
    InternalObjectRef,
    InternalOpRef,
    InternalTableRef,
)
from weave.trace.serialization.serialize import (
    CrossProjectRefError,
    ProjectNotFoundError,
    convert_cross_project_ref,
    convert_same_project_ref,
)
from weave.trace.settings import (
    UserSettings,
    parse_and_apply_settings,
)


@pytest.fixture(autouse=True)
def _reset_settings():
    """Reset settings to defaults after each test to avoid leaking state."""
    yield
    parse_and_apply_settings(UserSettings())


# ---------------------------------------------------------------------------
# convert_same_project_ref -- happy path
# ---------------------------------------------------------------------------


def test_same_project_object_ref() -> None:
    result = convert_same_project_ref(
        "weave:///entity/proj/object/my_obj:abc123",
        ext_project_id="entity/proj",
        internal_project_id="int-id-1",
    )
    assert isinstance(result, InternalObjectRef)
    assert result.name == "my_obj"
    assert result.version == "abc123"
    assert result.uri == "weave-trace-internal:///int-id-1/object/my_obj:abc123"


def test_same_project_op_ref() -> None:
    result = convert_same_project_ref(
        "weave:///entity/proj/op/my_op:def456",
        ext_project_id="entity/proj",
        internal_project_id="int-id-1",
    )
    assert isinstance(result, InternalOpRef)
    assert result.uri == "weave-trace-internal:///int-id-1/op/my_op:def456"


def test_same_project_table_ref() -> None:
    result = convert_same_project_ref(
        "weave:///entity/proj/table/abc123",
        ext_project_id="entity/proj",
        internal_project_id="int-id-1",
    )
    assert isinstance(result, InternalTableRef)
    assert result.digest == "abc123"
    assert result.uri == "weave-trace-internal:///int-id-1/table/abc123"


def test_same_project_call_ref() -> None:
    result = convert_same_project_ref(
        "weave:///entity/proj/call/call-id-123",
        ext_project_id="entity/proj",
        internal_project_id="int-id-1",
    )
    assert isinstance(result, InternalCallRef)
    assert result.id == "call-id-123"
    assert result.uri == "weave-trace-internal:///int-id-1/call/call-id-123"


def test_same_project_preserves_extra_path() -> None:
    """Extra path (attr/rows/id/...) is validated and preserved.

    Internal*Ref dataclasses run validate_extra in __post_init__,
    matching the server's validation in refs_internal.py.
    """
    result = convert_same_project_ref(
        "weave:///entity/proj/object/ds:abc/attr/rows/id/rowdigest",
        ext_project_id="entity/proj",
        internal_project_id="int-id-1",
    )
    assert isinstance(result, InternalObjectRef)
    assert result.extra == ["attr", "rows", "id", "rowdigest"]
    assert (
        result.uri
        == "weave-trace-internal:///int-id-1/object/ds:abc/attr/rows/id/rowdigest"
    )


def test_same_project_with_index_extra() -> None:
    result = convert_same_project_ref(
        "weave:///entity/proj/object/ds:abc/attr/items/index/3",
        ext_project_id="entity/proj",
        internal_project_id="int-id-1",
    )
    assert isinstance(result, InternalObjectRef)
    assert result.extra == ["attr", "items", "index", "3"]
    assert (
        result.uri
        == "weave-trace-internal:///int-id-1/object/ds:abc/attr/items/index/3"
    )


# ---------------------------------------------------------------------------
# convert_same_project_ref -- error cases
# ---------------------------------------------------------------------------


def test_same_project_raises_cross_project_for_different_project() -> None:
    with pytest.raises(CrossProjectRefError, match="other/proj"):
        convert_same_project_ref(
            "weave:///other/proj/object/thing:xyz",
            ext_project_id="entity/proj",
            internal_project_id="int-id-1",
        )


def test_same_project_raises_for_non_weave_uri() -> None:
    with pytest.raises(ValueError, match="Invalid URI"):
        convert_same_project_ref(
            "https://example.com/foo",
            ext_project_id="entity/proj",
            internal_project_id="int-id-1",
        )


def test_same_project_raises_for_malformed_ref() -> None:
    with pytest.raises(ValueError, match="Invalid URI"):
        convert_same_project_ref(
            "weave:///onlyonepart",
            ext_project_id="entity/proj",
            internal_project_id="int-id-1",
        )


def test_same_project_raises_for_already_internal_ref() -> None:
    with pytest.raises(ValueError, match="Invalid URI"):
        convert_same_project_ref(
            "weave-trace-internal:///int-id/object/thing:abc",
            ext_project_id="entity/proj",
            internal_project_id="int-id-1",
        )


def test_same_project_raises_for_unknown_kind() -> None:
    with pytest.raises(ValueError, match="Unknown ref kind"):
        convert_same_project_ref(
            "weave:///entity/proj/unknown/foo:bar",
            ext_project_id="entity/proj",
            internal_project_id="int-id-1",
        )


# ---------------------------------------------------------------------------
# convert_cross_project_ref
# ---------------------------------------------------------------------------


def test_cross_project_resolves_via_resolver() -> None:
    resolver = MagicMock()
    resolver.resolve.return_value = "other-int-id"

    result = convert_cross_project_ref(
        "weave:///other_entity/other_proj/object/thing:xyz",
        ext_project_id="entity/proj",
        resolver=resolver,
    )
    assert isinstance(result, InternalObjectRef)
    assert result.uri == "weave-trace-internal:///other-int-id/object/thing:xyz"
    resolver.resolve.assert_called_once_with("other_entity/other_proj")


def test_cross_project_raises_when_unresolvable() -> None:
    resolver = MagicMock()
    resolver.resolve.return_value = None

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
    resolver.resolve.assert_not_called()


def test_cross_project_raises_for_non_weave_uri() -> None:
    resolver = MagicMock()

    with pytest.raises(ValueError, match="Invalid URI"):
        convert_cross_project_ref(
            "https://example.com/foo",
            ext_project_id="entity/proj",
            resolver=resolver,
        )
