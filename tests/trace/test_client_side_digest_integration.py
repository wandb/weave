"""Integration tests for client-side digest calculation.

These tests verify:
1. Fallback behavior when server doesn't support client-side digest
2. End-to-end flows with actual server implementations
3. Cross-project ref handling
4. Security validation of internal refs
"""

import json
import tempfile
from concurrent.futures import Future
from unittest.mock import MagicMock, Mock, patch

import pytest

from weave.trace.refs import ObjectRef, TableRef
from weave.trace.weave_client import WeaveClient
from weave.trace_server.client_server_common.digest import (
    json_digest,
    str_digest,
    table_digest_from_row_digests,
)
from weave.trace_server.sqlite_trace_server import SqliteTraceServer
from weave.trace_server.trace_server_interface import (
    GetProjectIdReq,
    GetProjectIdRes,
    ObjCreateReq,
    ObjReadReq,
    ObjSchemaForInsert,
    TableCreateReq,
    TableSchemaForInsert,
)


class TestClientFallbackBehavior:
    """Tests for client fallback when server doesn't support client-side digest."""

    def test_can_use_client_side_digest_returns_false_for_old_server(self) -> None:
        """When server returns None for internal_project_id, client falls back."""
        mock_server = Mock()
        mock_server.ensure_project_exists.return_value = Mock(project_name="test-project")
        mock_server.get_project_id.return_value = GetProjectIdRes(internal_project_id=None)

        client = WeaveClient(
            entity="test-entity",
            project="test-project",
            server=mock_server,
            ensure_project_exists=True,
        )

        assert client._can_use_client_side_digest() is False
        # Verify it's cached
        assert client._use_client_side_digest is False

    def test_can_use_client_side_digest_returns_true_for_new_server(self) -> None:
        """When server returns internal_project_id, client uses client-side digest."""
        mock_server = Mock()
        mock_server.ensure_project_exists.return_value = Mock(project_name="test-project")
        mock_server.get_project_id.return_value = GetProjectIdRes(
            internal_project_id="INT_PROJ_123"
        )

        client = WeaveClient(
            entity="test-entity",
            project="test-project",
            server=mock_server,
            ensure_project_exists=True,
        )

        assert client._can_use_client_side_digest() is True
        assert client._use_client_side_digest is True
        # Verify project_id is cached
        assert client._project_id_cache["test-entity/test-project"] == "INT_PROJ_123"

    def test_can_use_client_side_digest_handles_exception(self) -> None:
        """When server throws exception (old server without endpoint), fall back."""
        mock_server = Mock()
        mock_server.ensure_project_exists.return_value = Mock(project_name="test-project")
        mock_server.get_project_id.side_effect = Exception("Endpoint not found")

        client = WeaveClient(
            entity="test-entity",
            project="test-project",
            server=mock_server,
            ensure_project_exists=True,
        )

        assert client._can_use_client_side_digest() is False
        assert client._use_client_side_digest is False

    def test_get_internal_project_id_caches_results(self) -> None:
        """Verify project IDs are cached to avoid repeated server calls."""
        mock_server = Mock()
        mock_server.ensure_project_exists.return_value = Mock(project_name="test-project")
        mock_server.get_project_id.return_value = GetProjectIdRes(
            internal_project_id="INT_PROJ_ABC"
        )

        client = WeaveClient(
            entity="test-entity",
            project="test-project",
            server=mock_server,
            ensure_project_exists=True,
        )

        # First call should hit server
        result1 = client._get_internal_project_id("test-entity/test-project")
        assert result1 == "INT_PROJ_ABC"
        assert mock_server.get_project_id.call_count == 1

        # Second call should use cache
        result2 = client._get_internal_project_id("test-entity/test-project")
        assert result2 == "INT_PROJ_ABC"
        assert mock_server.get_project_id.call_count == 1  # No additional call

    def test_get_internal_project_id_supports_cross_project_refs(self) -> None:
        """Verify different projects can be looked up and cached."""
        mock_server = Mock()
        mock_server.ensure_project_exists.return_value = Mock(project_name="main-project")

        # Return different IDs for different projects
        def get_project_id(req):
            if req.project_id == "entity1/project1":
                return GetProjectIdRes(internal_project_id="INT_1")
            elif req.project_id == "entity2/project2":
                return GetProjectIdRes(internal_project_id="INT_2")
            return GetProjectIdRes(internal_project_id=None)

        mock_server.get_project_id.side_effect = get_project_id

        client = WeaveClient(
            entity="entity1",
            project="main-project",
            server=mock_server,
            ensure_project_exists=True,
        )

        # Look up multiple projects
        id1 = client._get_internal_project_id("entity1/project1")
        id2 = client._get_internal_project_id("entity2/project2")

        assert id1 == "INT_1"
        assert id2 == "INT_2"
        assert len(client._project_id_cache) == 2

    def test_get_internal_project_id_raises_for_old_server(self) -> None:
        """When server returns None, raise ValueError."""
        mock_server = Mock()
        mock_server.ensure_project_exists.return_value = Mock(project_name="test-project")
        mock_server.get_project_id.return_value = GetProjectIdRes(internal_project_id=None)

        client = WeaveClient(
            entity="test-entity",
            project="test-project",
            server=mock_server,
            ensure_project_exists=True,
        )

        with pytest.raises(ValueError, match="does not support client-side digest"):
            client._get_internal_project_id("test-entity/test-project")


class TestEndToEndWithSqliteServer:
    """End-to-end tests using SqliteTraceServer."""

    @pytest.fixture
    def sqlite_server(self):
        """Create a temporary sqlite server for testing."""
        # Use in-memory database for speed
        db_path = "file::memory:?cache=shared"
        server = SqliteTraceServer(db_path)
        server.setup_tables()
        yield server
        server.drop_tables()

    def test_object_digest_consistency(self, sqlite_server) -> None:
        """Verify object digests are consistent between creates."""
        project_id = "test-entity/test-project"

        # Create same object twice
        val = {"name": "test", "value": 123}
        req1 = ObjCreateReq(
            obj=ObjSchemaForInsert(
                project_id=project_id,
                object_id="test-obj",
                val=val,
            )
        )
        req2 = ObjCreateReq(
            obj=ObjSchemaForInsert(
                project_id=project_id,
                object_id="test-obj",
                val=val,
            )
        )

        res1 = sqlite_server.obj_create(req1)
        res2 = sqlite_server.obj_create(req2)

        # Same content should produce same digest (deduplication)
        assert res1.digest == res2.digest

    def test_object_digest_differs_for_different_content(self, sqlite_server) -> None:
        """Verify different content produces different digests."""
        project_id = "test-entity/test-project"

        val1 = {"name": "test1", "value": 123}
        val2 = {"name": "test2", "value": 456}

        req1 = ObjCreateReq(
            obj=ObjSchemaForInsert(
                project_id=project_id,
                object_id="obj1",
                val=val1,
            )
        )
        req2 = ObjCreateReq(
            obj=ObjSchemaForInsert(
                project_id=project_id,
                object_id="obj2",
                val=val2,
            )
        )

        res1 = sqlite_server.obj_create(req1)
        res2 = sqlite_server.obj_create(req2)

        assert res1.digest != res2.digest

    def test_table_digest_from_row_digests_matches_server(self, sqlite_server) -> None:
        """Verify table_digest_from_row_digests matches what server computes."""
        project_id = "test-entity/test-project"

        rows = [{"a": 1}, {"b": 2}, {"c": 3}]
        req = TableCreateReq(
            table=TableSchemaForInsert(
                project_id=project_id,
                rows=rows,
            )
        )

        res = sqlite_server.table_create(req)

        # Compute table digest from row digests using centralized function
        computed_table_digest = table_digest_from_row_digests(res.row_digests)

        assert res.digest == computed_table_digest

    def test_table_row_order_affects_digest(self, sqlite_server) -> None:
        """Verify row order affects table digest."""
        project_id = "test-entity/test-project"

        rows1 = [{"a": 1}, {"b": 2}]
        rows2 = [{"b": 2}, {"a": 1}]

        req1 = TableCreateReq(
            table=TableSchemaForInsert(project_id=project_id, rows=rows1)
        )
        req2 = TableCreateReq(
            table=TableSchemaForInsert(project_id=project_id, rows=rows2)
        )

        res1 = sqlite_server.table_create(req1)
        res2 = sqlite_server.table_create(req2)

        # Different row order = different table digest
        assert res1.digest != res2.digest


class TestDigestStabilityWithDictOrdering:
    """Tests for digest stability across different dict orderings."""

    def test_json_digest_stable_across_orderings(self) -> None:
        """Verify json_digest is stable regardless of dict insertion order."""
        # These are semantically identical but may have different insertion order
        v1 = {"z": 1, "a": 2, "m": 3}
        v2 = {"a": 2, "m": 3, "z": 1}
        v3 = {"m": 3, "z": 1, "a": 2}

        d1 = json_digest(v1)
        d2 = json_digest(v2)
        d3 = json_digest(v3)

        assert d1 == d2 == d3

    def test_json_digest_stable_nested_dicts(self) -> None:
        """Verify nested dict ordering doesn't affect digest."""
        v1 = {
            "outer": {"z": 1, "a": 2},
            "items": [{"b": 1, "a": 2}, {"y": 3, "x": 4}],
        }
        v2 = {
            "items": [{"a": 2, "b": 1}, {"x": 4, "y": 3}],
            "outer": {"a": 2, "z": 1},
        }

        assert json_digest(v1) == json_digest(v2)

    def test_str_digest_vs_json_digest_for_simple_string(self) -> None:
        """Verify str_digest and json_digest produce different results for strings."""
        s = "hello"
        # str_digest hashes the raw string
        sd = str_digest(s)
        # json_digest hashes json.dumps(s, sort_keys=True) which adds quotes
        jd = json_digest(s)

        # They should be different because json.dumps adds quotes
        assert sd != jd
        # json_digest of "hello" is digest of '"hello"'
        assert jd == str_digest('"hello"')


class TestInternalRefSecurityValidation:
    """Tests for security validation of internal refs."""

    def test_internal_ref_with_valid_access_passes(self) -> None:
        """Internal refs pass through when user has access."""
        from weave.trace_server.trace_server_converter import (
            universal_ext_to_int_ref_converter,
        )

        internal_ref = "weave-trace-internal:///VALID_PROJECT/object/test:abc123"
        obj = {"data": internal_ref}

        validated_projects = set()

        def validate(project_id: str) -> bool:
            validated_projects.add(project_id)
            return True

        result = universal_ext_to_int_ref_converter(
            obj,
            lambda x: "should_not_be_called",
            validate,
        )

        assert result["data"] == internal_ref
        assert "VALID_PROJECT" in validated_projects

    def test_internal_ref_with_invalid_access_rejected(self) -> None:
        """Internal refs are rejected when user doesn't have access."""
        from weave.trace_server.errors import InvalidExternalRef
        from weave.trace_server.trace_server_converter import (
            universal_ext_to_int_ref_converter,
        )

        internal_ref = "weave-trace-internal:///FORBIDDEN_PROJECT/object/test:abc123"
        obj = {"data": internal_ref}

        with pytest.raises(InvalidExternalRef, match="No read access"):
            universal_ext_to_int_ref_converter(
                obj,
                lambda x: "should_not_be_called",
                lambda project_id: False,  # Always deny
            )

    def test_mixed_external_and_internal_refs(self) -> None:
        """Handle objects with both external and internal refs."""
        from weave.trace_server.trace_server_converter import (
            universal_ext_to_int_ref_converter,
        )

        obj = {
            "external": "weave:///entity/project/object/name:digest",
            "internal": "weave-trace-internal:///INT_PROJ/object/name2:digest2",
        }

        def convert_ext(ext_id: str) -> str:
            return "CONVERTED_INT_PROJ"

        def validate_int(project_id: str) -> bool:
            return project_id == "INT_PROJ"

        result = universal_ext_to_int_ref_converter(obj, convert_ext, validate_int)

        # External ref should be converted
        assert result["external"] == "weave-trace-internal:///CONVERTED_INT_PROJ/object/name:digest"
        # Internal ref should pass through (validated)
        assert result["internal"] == "weave-trace-internal:///INT_PROJ/object/name2:digest2"

    def test_validation_caches_results(self) -> None:
        """Verify validation results are cached per project_id."""
        from weave.trace_server.trace_server_converter import (
            universal_ext_to_int_ref_converter,
        )

        # Object with multiple refs to same project
        obj = {
            "ref1": "weave-trace-internal:///PROJ_A/object/obj1:d1",
            "ref2": "weave-trace-internal:///PROJ_A/object/obj2:d2",
            "ref3": "weave-trace-internal:///PROJ_B/object/obj3:d3",
        }

        validation_calls = []

        def validate(project_id: str) -> bool:
            validation_calls.append(project_id)
            return True

        universal_ext_to_int_ref_converter(
            obj,
            lambda x: "unused",
            validate,
        )

        # Should only validate each project once
        assert validation_calls.count("PROJ_A") == 1
        assert validation_calls.count("PROJ_B") == 1
