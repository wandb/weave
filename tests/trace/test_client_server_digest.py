"""Tests for client-server digest matching.

These tests verify that client-side digest calculation produces identical
results to server-side calculation, enabling fire-and-forget publishing.
"""

import json
from unittest.mock import Mock

import pytest

from weave.trace.refs import ObjectRef, TableRef
from weave.trace.serialization.serialize import _ref_to_internal_uri, to_json_internal
from weave.trace_server import refs_internal
from weave.trace_server.client_server_common.digest import bytes_digest, str_digest
from weave.trace_server.trace_server_converter import (
    _extract_project_from_internal_ref,
    universal_ext_to_int_ref_converter,
)


class TestDigestFunctions:
    """Tests for the core digest functions."""

    def test_bytes_digest_deterministic(self) -> None:
        """Verify bytes_digest produces consistent results."""
        data = b"hello world"
        digest1 = bytes_digest(data)
        digest2 = bytes_digest(data)
        assert digest1 == digest2

    def test_str_digest_deterministic(self) -> None:
        """Verify str_digest produces consistent results."""
        data = "hello world"
        digest1 = str_digest(data)
        digest2 = str_digest(data)
        assert digest1 == digest2

    def test_str_digest_matches_bytes_digest(self) -> None:
        """Verify str_digest is equivalent to bytes_digest with utf-8 encoding."""
        data = "hello world"
        assert str_digest(data) == bytes_digest(data.encode("utf-8"))

    def test_digest_no_invalid_chars(self) -> None:
        """Verify digest doesn't contain URL-unsafe characters."""
        data = "test data for digest"
        digest = str_digest(data)
        # Should not contain - or _ (replaced with X and Y)
        # Should not contain = (stripped)
        assert "-" not in digest
        assert "_" not in digest
        assert "=" not in digest


class TestRefToInternalUri:
    """Tests for converting refs to internal URI format."""

    def test_table_ref_to_internal(self) -> None:
        """Test TableRef conversion to internal URI."""
        ref = TableRef(entity="myentity", project="myproject", _digest="abc123")

        def get_internal_id(ext_id: str) -> str:
            return "INTERNAL_ID_123"

        uri = _ref_to_internal_uri(ref, get_internal_id)
        assert uri == "weave-trace-internal:///INTERNAL_ID_123/table/abc123"

    def test_object_ref_to_internal(self) -> None:
        """Test ObjectRef conversion to internal URI."""
        ref = ObjectRef(
            entity="myentity", project="myproject", name="myobj", _digest="def456"
        )

        def get_internal_id(ext_id: str) -> str:
            assert ext_id == "myentity/myproject"
            return "INTERNAL_ID_456"

        uri = _ref_to_internal_uri(ref, get_internal_id)
        assert uri == "weave-trace-internal:///INTERNAL_ID_456/object/myobj:def456"

    def test_object_ref_with_extra_to_internal(self) -> None:
        """Test ObjectRef with extra path components."""
        ref = ObjectRef(
            entity="myentity",
            project="myproject",
            name="myobj",
            _digest="def456",
            _extra=("attr", "field"),
        )

        def get_internal_id(ext_id: str) -> str:
            return "INTERNAL_ID_789"

        uri = _ref_to_internal_uri(ref, get_internal_id)
        assert uri == "weave-trace-internal:///INTERNAL_ID_789/object/myobj:def456/attr/field"


class TestToJsonInternal:
    """Tests for to_json_internal serialization."""

    def test_simple_dict_unchanged(self) -> None:
        """Verify simple dicts are serialized without changes."""
        client = Mock()
        obj = {"key": "value", "num": 42}

        def get_internal_id(ext_id: str) -> str:
            raise AssertionError("Should not be called for simple data")

        result = to_json_internal(obj, "entity/project", client, get_internal_id)
        assert result == {"key": "value", "num": 42}

    def test_nested_ref_converted(self) -> None:
        """Verify nested refs are converted to internal format."""
        client = Mock()
        ref = ObjectRef(
            entity="myentity", project="myproject", name="child", _digest="childdigest"
        )
        obj = {"data": "value", "ref": ref}

        def get_internal_id(ext_id: str) -> str:
            return "PROJ_123"

        result = to_json_internal(obj, "entity/project", client, get_internal_id)
        assert result == {
            "data": "value",
            "ref": "weave-trace-internal:///PROJ_123/object/child:childdigest",
        }

    def test_list_with_refs(self) -> None:
        """Verify lists containing refs are properly converted."""
        client = Mock()
        ref1 = ObjectRef(entity="e", project="p", name="obj1", _digest="d1")
        ref2 = ObjectRef(entity="e", project="p", name="obj2", _digest="d2")
        obj = [ref1, ref2]

        def get_internal_id(ext_id: str) -> str:
            return "INT_PROJ"

        result = to_json_internal(obj, "e/p", client, get_internal_id)
        assert result == [
            "weave-trace-internal:///INT_PROJ/object/obj1:d1",
            "weave-trace-internal:///INT_PROJ/object/obj2:d2",
        ]


class TestExtractProjectFromInternalRef:
    """Tests for extracting project ID from internal refs."""

    def test_extract_from_object_ref(self) -> None:
        """Extract project ID from internal object ref."""
        uri = "weave-trace-internal:///PROJECT_123/object/myobj:digest"
        project_id = _extract_project_from_internal_ref(uri)
        assert project_id == "PROJECT_123"

    def test_extract_from_table_ref(self) -> None:
        """Extract project ID from internal table ref."""
        uri = "weave-trace-internal:///PROJECT_456/table/tabledigest"
        project_id = _extract_project_from_internal_ref(uri)
        assert project_id == "PROJECT_456"


class TestClientServerDigestMatch:
    """Tests verifying client and server compute identical digests."""

    def test_simple_object_digest_match(self) -> None:
        """Verify digest matches for a simple object."""
        # Simulate what the server does: convert refs to internal format, then hash
        internal_project_id = "INT_PROJ_ABC"

        # Object with no refs - digest should be based on JSON serialization
        obj_val = {"name": "test", "value": 123}
        json_str = json.dumps(obj_val)
        expected_digest = str_digest(json_str)

        # Client computes the same
        client_digest = str_digest(json.dumps(obj_val))

        assert client_digest == expected_digest

    def test_object_with_refs_digest_match(self) -> None:
        """Verify digest matches for object containing refs."""
        # Setup: object contains a ref that must be converted to internal format
        internal_project_id = "INT_PROJ_XYZ"

        # What the server sees after ref conversion
        server_val = {
            "data": "some data",
            "child": f"weave-trace-internal:///{internal_project_id}/object/child:childdigest",
        }
        server_digest = str_digest(json.dumps(server_val))

        # What the client computes using to_json_internal
        client = Mock()
        child_ref = ObjectRef(
            entity="ent", project="proj", name="child", _digest="childdigest"
        )
        client_val = {"data": "some data", "child": child_ref}

        def get_internal_id(ext_id: str) -> str:
            return internal_project_id

        json_val = to_json_internal(client_val, "ent/proj", client, get_internal_id)
        client_digest = str_digest(json.dumps(json_val))

        assert client_digest == server_digest
        assert json_val == server_val


class TestServerInternalRefValidation:
    """Tests for server-side validation of internal refs from clients."""

    def test_internal_ref_passthrough_when_validated(self) -> None:
        """Internal refs pass through when validation succeeds."""
        internal_ref = "weave-trace-internal:///VALID_PROJECT/object/myobj:digest"
        obj = {"ref": internal_ref, "data": "test"}

        def convert_ext_to_int(ext_id: str) -> str:
            raise AssertionError("Should not be called for internal refs")

        def validate_access(project_id: str) -> bool:
            assert project_id == "VALID_PROJECT"
            return True

        result = universal_ext_to_int_ref_converter(
            obj, convert_ext_to_int, validate_access
        )
        # Internal ref should pass through unchanged
        assert result["ref"] == internal_ref
        assert result["data"] == "test"

    def test_internal_ref_rejected_when_no_access(self) -> None:
        """Internal refs are rejected when validation fails."""
        internal_ref = "weave-trace-internal:///INVALID_PROJECT/object/myobj:digest"
        obj = {"ref": internal_ref}

        def convert_ext_to_int(ext_id: str) -> str:
            raise AssertionError("Should not be called")

        def validate_access(project_id: str) -> bool:
            return False  # No access

        from weave.trace_server.errors import InvalidExternalRef

        with pytest.raises(InvalidExternalRef, match="No read access"):
            universal_ext_to_int_ref_converter(obj, convert_ext_to_int, validate_access)

    def test_internal_ref_rejected_when_no_validator(self) -> None:
        """Internal refs are rejected when no validator is provided (legacy mode)."""
        internal_ref = "weave-trace-internal:///PROJECT/object/myobj:digest"
        obj = {"ref": internal_ref}

        def convert_ext_to_int(ext_id: str) -> str:
            raise AssertionError("Should not be called")

        from weave.trace_server.errors import InvalidExternalRef

        with pytest.raises(InvalidExternalRef, match="unexpected ref format"):
            # No validate_internal_project_access callback = legacy mode
            universal_ext_to_int_ref_converter(obj, convert_ext_to_int, None)

    def test_external_ref_still_converted(self) -> None:
        """External refs are still converted even when validator is provided."""
        external_ref = "weave:///myentity/myproject/object/myobj:digest"
        obj = {"ref": external_ref}

        def convert_ext_to_int(ext_id: str) -> str:
            assert ext_id == "myentity/myproject"
            return "CONVERTED_PROJECT"

        def validate_access(project_id: str) -> bool:
            return True

        result = universal_ext_to_int_ref_converter(
            obj, convert_ext_to_int, validate_access
        )
        # External ref should be converted to internal format
        assert (
            result["ref"]
            == "weave-trace-internal:///CONVERTED_PROJECT/object/myobj:digest"
        )
