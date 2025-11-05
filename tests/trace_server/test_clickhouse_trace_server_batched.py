from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock, patch

from weave.trace_server import clickhouse_trace_server_batched as chts
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.secret_fetcher_context import _secret_fetcher_context
from weave.trace_server.trace_server_interface_util import str_digest
from weave.trace_server.errors import ObjectDeletedError
import json
import pytest


class MockObjectReadError(Exception):
    """Custom exception for mock object read failures."""

    pass


def test_clickhouse_storage_size_query_generation():
    """Test that ClickHouse storage size query generation works correctly."""
    # Mock the query builder and query stream
    with (
        patch(
            "weave.trace_server.clickhouse_trace_server_batched.CallsQuery",
            autospec=True,
        ) as mock_cq,
        patch.object(chts.ClickHouseTraceServer, "_query_stream") as mock_query_stream,
    ):
        # Create a mock CallsQuery instance
        mock_calls_query = Mock()
        # Mock the CallsQuery class to return our mock instance
        mock_cq.return_value = mock_calls_query

        # Mock the query stream to return empty list
        mock_query_stream.return_value = []
        # Mock the select_fields property to return an empty columns list
        mock_calls_query.select_fields = []

        # Create a request with storage size fields
        req = tsi.CallsQueryReq(
            project_id="test_project",
            include_storage_size=True,
            include_total_storage_size=True,
        )

        # Create server instance
        server = chts.ClickHouseTraceServer(host="test_host")

        # Call the method that generates the query and consume the generator
        list(server.calls_query_stream(req))

        # Verify that storage size fields were added
        mock_calls_query.add_field.assert_any_call("storage_size_bytes")
        mock_calls_query.add_field.assert_any_call("total_storage_size_bytes")

        # Verify that _query_stream was called once
        mock_query_stream.assert_called_once()
        call_args = mock_query_stream.call_args[0]
        assert (
            call_args[0] == mock_calls_query.as_sql()
        )  # First argument should be the query
        # with mocks, we don't have any params generated
        assert call_args[1] == {}  # Second argument should be project_id


def test_clickhouse_storage_size_schema_conversion():
    """Test that storage size fields are correctly converted in ClickHouse schema."""
    # Test data with proper datetime structures
    started_at = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    ended_at = datetime(2024, 1, 1, 0, 1, 0, tzinfo=timezone.utc)
    test_data = {
        "storage_size_bytes": 1000,
        "total_storage_size_bytes": 2000,
        "id": "test_id",
        "name": "test_name",
        "project_id": "test_project",
        "trace_id": "test_trace",
        "parent_id": None,
        "started_at": started_at,
        "ended_at": ended_at,
        "inputs": {},
        "outputs": {},
        "error": None,
        "summary": None,
        "summary_dump": None,
        "cost": None,
        "wb_run_id": None,
        "wb_run_step": None,
        "wb_user_id": None,
    }

    # Test ClickHouse conversion
    ch_schema = chts._ch_call_dict_to_call_schema_dict(test_data)
    assert ch_schema["storage_size_bytes"] == 1000
    assert ch_schema["total_storage_size_bytes"] == 2000


def test_clickhouse_storage_size_null_handling():
    """Test that NULL values in storage size fields are handled correctly in ClickHouse."""
    # Test data with NULL values and proper datetime structures
    started_at = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    ended_at = datetime(2024, 1, 1, 0, 1, 0, tzinfo=timezone.utc)
    test_data = {
        "storage_size_bytes": None,
        "total_storage_size_bytes": None,
        "id": "test_id",
        "name": "test_name",
        "project_id": "test_project",
        "trace_id": "test_trace",
        "parent_id": None,
        "started_at": started_at,
        "ended_at": ended_at,
        "inputs": {},
        "outputs": {},
        "error": None,
        "summary": None,
        "summary_dump": None,
        "cost": None,
        "wb_run_id": None,
        "wb_run_step": None,
        "wb_user_id": None,
    }

    # Test ClickHouse conversion
    ch_schema = chts._ch_call_dict_to_call_schema_dict(test_data)
    assert ch_schema["storage_size_bytes"] is None
    assert ch_schema["total_storage_size_bytes"] is None


def test_completions_create_stream_custom_provider():
    """Test completions_create_stream for a custom provider (no call tracking)."""
    # Mock chunks to be returned by the stream
    mock_chunks = [
        {
            "choices": [
                {
                    "delta": {"content": "Streamed"},
                    "finish_reason": None,
                    "index": 0,
                }
            ],
            "id": "test-id",
            "model": "custom-model",
            "created": 1234567890,
        },
        {
            "choices": [
                {
                    "delta": {},
                    "finish_reason": "stop",
                    "index": 0,
                }
            ],
            "id": "test-id",
            "model": "custom-model",
            "created": 1234567890,
            "usage": {
                "prompt_tokens": 5,
                "completion_tokens": 1,
                "total_tokens": 6,
            },
        },
    ]

    with (
        patch(
            "weave.trace_server.clickhouse_trace_server_batched.lite_llm_completion_stream"
        ) as mock_litellm,
        patch.object(chts.ClickHouseTraceServer, "obj_read") as mock_obj_read,
    ):
        # Mock the litellm completion stream
        mock_stream = MagicMock()
        mock_stream.__iter__.return_value = mock_chunks
        mock_litellm.return_value = mock_stream

        # Mock provider and model objects
        mock_provider = tsi.ObjSchema(
            project_id="test_project",
            object_id="custom-provider",
            digest="digest-1",
            base_object_class="Provider",
            leaf_object_class="Provider",
            val={
                "base_url": "https://api.custom.com",
                "api_key_name": "CUSTOM_API_KEY",
                "extra_headers": {"X-Custom": "value"},
                "return_type": "openai",
                "api_base": "https://api.custom.com",
            },
            created_at=datetime.now(),
            version_index=1,
            is_latest=1,
            kind="object",
            deleted_at=None,
        )

        mock_model = tsi.ObjSchema(
            project_id="test_project",
            object_id="custom-provider-model",
            digest="digest-2",
            base_object_class="ProviderModel",
            leaf_object_class="ProviderModel",
            val={
                "name": "custom-model",
                "provider": "custom-provider",
                "max_tokens": 4096,
                "mode": "chat",
            },
            created_at=datetime.now(),
            version_index=1,
            is_latest=1,
            kind="object",
            deleted_at=None,
        )

        def mock_obj_read_func(req):
            if req.object_id == "custom-provider":
                return tsi.ObjReadRes(obj=mock_provider)
            elif req.object_id == "custom-provider-model":
                return tsi.ObjReadRes(obj=mock_model)
            raise MockObjectReadError(f"Unknown object_id: {req.object_id}")

        mock_obj_read.side_effect = mock_obj_read_func

        # Set up mock secret fetcher
        mock_secret_fetcher = MagicMock()
        mock_secret_fetcher.fetch.return_value = {
            "secrets": {"CUSTOM_API_KEY": "test-api-key-value"}
        }
        token = _secret_fetcher_context.set(mock_secret_fetcher)

        try:
            # Create test request
            req = tsi.CompletionsCreateReq(
                project_id="test_project",
                inputs=tsi.CompletionsCreateRequestInputs(
                    model="custom::custom-provider::model",
                    messages=[{"role": "user", "content": "Say hello"}],
                ),
                track_llm_call=False,
            )

            server = chts.ClickHouseTraceServer(host="test_host")
            stream = server.completions_create_stream(req)
            chunks = list(stream)

            assert len(chunks) == 2
            assert chunks[0]["choices"][0]["delta"]["content"] == "Streamed"
            assert chunks[1]["choices"][0]["finish_reason"] == "stop"
            assert "usage" in chunks[1]

            # Verify litellm was called with correct parameters
            mock_litellm.assert_called_once()
            call_args = mock_litellm.call_args[1]
            assert (
                call_args.get("api_base")
                or call_args.get("base_url") == "https://api.custom.com"
            )
            assert call_args["extra_headers"] == {"X-Custom": "value"}
        finally:
            _secret_fetcher_context.reset(token)


def test_completions_create_stream_custom_provider_with_tracking():
    """Test completions_create_stream for a custom provider with call tracking enabled."""
    # Mock chunks to be returned by the stream
    mock_chunks = [
        {
            "choices": [
                {
                    "delta": {"content": "Streamed"},
                    "finish_reason": None,
                    "index": 0,
                }
            ],
            "id": "test-id",
            "model": "custom-model",
            "created": 1234567890,
        },
        {
            "choices": [
                {
                    "delta": {},
                    "finish_reason": "stop",
                    "index": 0,
                }
            ],
            "id": "test-id",
            "model": "custom-model",
            "created": 1234567890,
            "usage": {
                "prompt_tokens": 5,
                "completion_tokens": 1,
                "total_tokens": 6,
            },
        },
    ]

    with (
        patch(
            "weave.trace_server.clickhouse_trace_server_batched.lite_llm_completion_stream"
        ) as mock_litellm,
        patch.object(chts.ClickHouseTraceServer, "obj_read") as mock_obj_read,
        patch.object(chts.ClickHouseTraceServer, "_insert_call") as mock_insert_call,
    ):
        # Mock the litellm completion stream
        mock_stream = MagicMock()
        mock_stream.__iter__.return_value = mock_chunks
        mock_litellm.return_value = mock_stream

        # Mock provider and model objects
        mock_provider = tsi.ObjSchema(
            project_id="dGVzdF9wcm9qZWN0",
            object_id="custom-provider",
            digest="digest-1",
            base_object_class="Provider",
            leaf_object_class="Provider",
            val={
                "base_url": "https://api.custom.com",
                "api_key_name": "CUSTOM_API_KEY",
                "extra_headers": {"X-Custom": "value"},
                "return_type": "openai",
                "api_base": "https://api.custom.com",
            },
            created_at=datetime.now(),
            version_index=1,
            is_latest=1,
            kind="object",
            deleted_at=None,
        )

        mock_model = tsi.ObjSchema(
            project_id="dGVzdF9wcm9qZWN0",
            object_id="custom-provider-model",
            digest="digest-2",
            base_object_class="ProviderModel",
            leaf_object_class="ProviderModel",
            val={
                "name": "custom-model",
                "provider": "custom-provider",
                "max_tokens": 4096,
                "mode": "chat",
            },
            created_at=datetime.now(),
            version_index=1,
            is_latest=1,
            kind="object",
            deleted_at=None,
        )

        def mock_obj_read_func(req):
            if req.object_id == "custom-provider":
                return tsi.ObjReadRes(obj=mock_provider)
            elif req.object_id == "custom-provider-model":
                return tsi.ObjReadRes(obj=mock_model)
            raise MockObjectReadError(f"Unknown object_id: {req.object_id}")

        mock_obj_read.side_effect = mock_obj_read_func

        # Set up mock secret fetcher
        mock_secret_fetcher = MagicMock()
        mock_secret_fetcher.fetch.return_value = {
            "secrets": {"CUSTOM_API_KEY": "test-api-key-value"}
        }
        token = _secret_fetcher_context.set(mock_secret_fetcher)

        try:
            # Create test request with tracking enabled
            req = tsi.CompletionsCreateReq(
                project_id="dGVzdF9wcm9qZWN0",
                inputs=tsi.CompletionsCreateRequestInputs(
                    model="custom::custom-provider::model",
                    messages=[{"role": "user", "content": "Say hello"}],
                ),
                track_llm_call=True,
            )

            server = chts.ClickHouseTraceServer(host="test_host")
            stream = server.completions_create_stream(req)
            chunks = list(stream)

            # Verify streaming functionality
            assert len(chunks) == 3  # Meta chunk + 2 content chunks
            assert "_meta" in chunks[0]
            assert "weave_call_id" in chunks[0]["_meta"]
            assert chunks[1]["choices"][0]["delta"]["content"] == "Streamed"
            assert chunks[2]["choices"][0]["finish_reason"] == "stop"
            assert "usage" in chunks[2]

            # Verify call tracking
            assert mock_insert_call.call_count == 2  # Start and end calls
            start_call = mock_insert_call.call_args_list[0][0][0]
            end_call = mock_insert_call.call_args_list[1][0][0]
            assert start_call.project_id == "dGVzdF9wcm9qZWN0"
            assert end_call.project_id == "dGVzdF9wcm9qZWN0"
            assert end_call.id == start_call.id

            # Verify litellm was called with correct parameters
            mock_litellm.assert_called_once()
            call_args = mock_litellm.call_args[1]
            assert (
                call_args.get("api_base")
                or call_args.get("base_url") == "https://api.custom.com"
            )
            assert call_args["extra_headers"] == {"X-Custom": "value"}
        finally:
            _secret_fetcher_context.reset(token)


def _mk_obj(project_id: str, object_id: str, val: dict[str, object]):
    return tsi.ObjSchemaForInsert(project_id=project_id, object_id=object_id, val=val)


def _internal_pid() -> str:
    # Any base64 string is valid for internal project id validation
    # Reuse the same value as other tests in this module
    return "dGVzdF9wcm9qZWN0"


def test_obj_create_batch_internal_clickhouse_insert_once():
    """Test internal obj_create_batch performs a single ClickHouse insert."""
    from weave.trace_server.clickhouse_trace_server_batched import ClickHouseTraceServer

    mock_ch_client = MagicMock()
    mock_ch_client.command.return_value = None
    mock_ch_client.insert.return_value = MagicMock()

    with patch.object(ClickHouseTraceServer, "_mint_client", return_value=mock_ch_client):
        server = ClickHouseTraceServer(host="test_host")
        pid = _internal_pid()
        batch = [
            _mk_obj(pid, "obj_a", {"v": 1}),
            _mk_obj(pid, "obj_b", {"v": 2}),
            _mk_obj(pid, "obj_c", {"v": 3}),
        ]
        res = server.obj_create_batch(tsi.ObjCreateBatchReq(batch=batch))

        # Single insert to the object_versions table with 3 rows
        assert mock_ch_client.insert.call_count == 1
        assert mock_ch_client.insert.call_args_list[0][0][0] == "object_versions"
        # Verify result digests match expected values
        expected = [str_digest(json.dumps(x.val)) for x in batch]
        assert [r.digest for r in res.results] == expected
        assert [r.object_id for r in res.results] == [x.object_id for x in batch]


def test_obj_batch_same_object_id_different_hash(trace_server):
    """Two versions for same object_id with different digests."""
    server = trace_server._internal_trace_server
    pid = _internal_pid()
    obj_id = "my_obj"
    v1 = {"k": 1}
    v2 = {"k": 2}

    server.obj_create_batch(
        tsi.ObjCreateBatchReq(
            batch=[
                _mk_obj(pid, obj_id, v1),
                _mk_obj(pid, obj_id, v2),
            ]
        )
    )

    res = server.objs_query(
        tsi.ObjQueryReq(
            project_id=pid,
            filter=tsi.ObjectVersionFilter(object_ids=[obj_id], latest_only=False),
        )
    )
    assert len(res.objs) == 2
    digests = {o.digest for o in res.objs}
    assert digests == {str_digest(json.dumps(v1)), str_digest(json.dumps(v2))}
    # Exactly one latest
    assert sum(o.is_latest for o in res.objs) == 1


def test_obj_batch_same_hash_different_object_ids(trace_server):
    """Same digest payload uploaded under different object_ids yields distinct objects."""
    server = trace_server._internal_trace_server
    pid = _internal_pid()
    val = {"shared": True}
    server.obj_create_batch(
        tsi.ObjCreateBatchReq(
            batch=[
                _mk_obj(pid, "obj_1", val),
                _mk_obj(pid, "obj_2", val),
            ]
        )
    )
    res = server.objs_query(
        tsi.ObjQueryReq(
            project_id=pid,
            filter=tsi.ObjectVersionFilter(object_ids=["obj_1", "obj_2"], latest_only=False),
        )
    )
    assert len(res.objs) == 2
    assert {o.object_id for o in res.objs} == {"obj_1", "obj_2"}


def test_obj_batch_identical_same_id_same_hash_deduplicates(trace_server):
    """Duplicate rows (same object_id and digest) are represented once in metadata view."""
    server = trace_server._internal_trace_server
    pid = _internal_pid()
    obj_id = "dup_obj"
    val = {"x": 1}
    server.obj_create_batch(
        tsi.ObjCreateBatchReq(
            batch=[
                _mk_obj(pid, obj_id, val),
                _mk_obj(pid, obj_id, val),
            ]
        )
    )
    res = server.objs_query(
        tsi.ObjQueryReq(
            project_id=pid,
            filter=tsi.ObjectVersionFilter(object_ids=[obj_id], latest_only=False),
        )
    )
    assert len(res.objs) == 1
    assert res.objs[0].digest == str_digest(json.dumps(val))


def test_obj_batch_four_versions_and_read_path(trace_server):
    """Batch upload 4 versions and verify reads over all and latest work."""
    server = trace_server._internal_trace_server
    pid = _internal_pid()
    obj_id = "multi_v"
    vals = [{"i": i} for i in range(4)]
    digests = [str_digest(json.dumps(v)) for v in vals]
    server.obj_create_batch(
        tsi.ObjCreateBatchReq(
            batch=[_mk_obj(pid, obj_id, v) for v in vals]
        )
    )

    # All versions are queryable
    res = server.objs_query(
        tsi.ObjQueryReq(
            project_id=pid,
            filter=tsi.ObjectVersionFilter(object_ids=[obj_id], latest_only=False),
        )
    )
    assert len(res.objs) == 4
    assert {o.digest for o in res.objs} == set(digests)
    assert sum(o.is_latest for o in res.objs) == 1

    # Each digest can be read specifically
    for d, v in zip(digests, vals):
        read = server.obj_read(
            tsi.ObjReadReq(project_id=pid, object_id=obj_id, digest=d)
        )
        assert read.obj.val == v

    # Latest alias reads the most recent version
    latest = server.obj_read(
        tsi.ObjReadReq(project_id=pid, object_id=obj_id, digest="latest")
    )
    assert latest.obj.digest in set(digests)
    assert latest.obj.is_latest == 1


def test_obj_batch_delete_version_preserves_indices(trace_server):
    """Delete one version and ensure indices remain intact and deletion is reflected."""
    server = trace_server._internal_trace_server
    pid = _internal_pid()
    obj_id = "del_v"
    vals = [{"i": i} for i in range(3)]
    digests = [str_digest(json.dumps(v)) for v in vals]

    server.obj_create_batch(
        tsi.ObjCreateBatchReq(
            batch=[_mk_obj(pid, obj_id, v) for v in vals]
        )
    )

    # Delete the middle version
    del_digest = digests[1]
    server.obj_delete(
        tsi.ObjDeleteReq(project_id=pid, object_id=obj_id, digests=[del_digest])
    )

    # Reading deleted digest raises ObjectDeletedError
    with pytest.raises(ObjectDeletedError):
        server.obj_read(tsi.ObjReadReq(project_id=pid, object_id=obj_id, digest=del_digest))

    # Remaining versions are intact; indices are not renumbered in metadata
    res = server.objs_query(
        tsi.ObjQueryReq(
            project_id=pid,
            filter=tsi.ObjectVersionFilter(object_ids=[obj_id], latest_only=False),
        )
    )
    assert len(res.objs) == 2
    assert {o.digest for o in res.objs} == {digests[0], digests[2]}
    # Version indices remain from original sequence (0 and 2)
    assert {o.version_index for o in res.objs} == {0, 2}


@pytest.mark.xfail(reason="Not yet enforced: mixed-project obj_create_batch should error")
def test_obj_batch_mixed_projects_errors(trace_server):
    """Uploading objects to different projects in one batch should error."""
    server = trace_server._internal_trace_server
    pid1 = _internal_pid()
    pid2 = "cHJvamVjdF8y"  # base64("project_2")
    batch = [
        _mk_obj(pid1, "p1_obj", {"a": 1}),
        _mk_obj(pid2, "p2_obj", {"b": 2}),
    ]

    with pytest.raises(ValueError):
        server.obj_create_batch(tsi.ObjCreateBatchReq(batch=batch))
