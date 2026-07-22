import base64
import datetime as dt
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock, patch

import clickhouse_connect
import pytest
from clickhouse_connect.driver.exceptions import DatabaseError, ProgrammingError

from tests.trace_server.test_project_version import make_project_id
from weave.trace_server import ch_sentinel_values
from weave.trace_server import clickhouse_trace_server_batched as chts
from weave.trace_server import clickhouse_trace_server_settings as ch_settings
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.agents.clickhouse import AgentWriteHandler
from weave.trace_server.agents.schema import AgentSpanCHInsertable
from weave.trace_server.agents.types import GenAIOTelExportReq, GenAIOTelExportRes
from weave.trace_server.ch_sentinel_values import EXPIRE_AT_NEVER
from weave.trace_server.clickhouse.schema_converters import (
    ch_call_to_row,
    ch_complete_call_to_row,
)
from weave.trace_server.clickhouse.utilities import insert_with_empty_query_retry
from weave.trace_server.clickhouse_schema import (
    ALL_CALL_COMPLETE_INSERT_COLUMNS,
    ALL_CALL_INSERT_COLUMNS,
    CallCompleteCHInsertable,
    CallStartCHInsertable,
)
from weave.trace_server.errors import NotFoundError, ObjectDeletedError
from weave.trace_server.project_version.types import ReadTable
from weave.trace_server.secret_fetcher_context import secret_fetcher_context


class MockObjectReadError(Exception):
    """Custom exception for mock object read failures."""

    pass


def test_clickhouse_storage_size_query_generation():
    """Test that ClickHouse storage size query generation works correctly."""
    # Mock the query builder and query stream
    mock_ch_client = MagicMock()
    with (
        patch(
            "weave.trace_server.clickhouse_trace_server_batched.CallsQuery",
            autospec=True,
        ) as mock_cq,
        patch.object(chts.ClickHouseTraceServer, "_query_stream") as mock_query_stream,
        patch.object(
            chts.ClickHouseTraceServer, "_mint_client", return_value=mock_ch_client
        ),
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


@pytest.mark.parametrize(
    ("sort_by", "limit", "expected_orders", "expect_streaming_setting"),
    [
        pytest.param(
            None,
            100,
            [("started_at", "asc"), ("id", "asc")],
            False,
            id="none-uses-default-order",
        ),
        pytest.param([], 100, [], True, id="empty-list-disables-sort"),
        pytest.param([], None, [], False, id="empty-list-no-limit-no-setting"),
        pytest.param(
            [tsi.SortBy(field="started_at", direction="desc")],
            100,
            [("started_at", "desc"), ("id", "desc")],
            False,
            id="user-sort-disables-setting",
        ),
    ],
)
def test_clickhouse_calls_query_stream_sort_modes(
    sort_by, limit, expected_orders, expect_streaming_setting
):
    """sort_by=None keeps default order; [] is explicit no-sort and engages
    optimize_aggregation_in_order; a user-supplied sort defeats the setting.
    """
    with (
        patch(
            "weave.trace_server.clickhouse_trace_server_batched.CallsQuery",
            autospec=True,
        ) as mock_cq,
        patch.object(chts.ClickHouseTraceServer, "_query_stream") as mock_query_stream,
        patch.object(
            chts.ClickHouseTraceServer, "_mint_client", return_value=MagicMock()
        ),
    ):
        mock_calls_query = Mock()
        mock_calls_query.order_fields = []
        mock_calls_query.select_fields = []
        mock_calls_query.add_order.side_effect = lambda field, direction: (
            mock_calls_query.order_fields.append((field, direction))
        )
        mock_cq.return_value = mock_calls_query
        mock_query_stream.return_value = []

        req = tsi.CallsQueryReq(project_id="p", sort_by=sort_by, limit=limit)
        server = chts.ClickHouseTraceServer(host="h")
        with patch.object(
            server.table_routing_resolver,
            "resolve_read_table",
            return_value=ReadTable.CALLS_MERGED,
        ):
            list(server.calls_query_stream(req))

        assert mock_calls_query.order_fields == expected_orders
        settings = mock_query_stream.call_args.kwargs.get("settings") or {}
        assert ("optimize_aggregation_in_order" in settings) == expect_streaming_setting


def test_clickhouse_calls_query_stream_empty_thread_ids_against_real_clickhouse(
    ch_server,
):
    """Filter with thread_ids=[] against real ClickHouse: query runs and returns 0 rows.

    When run with --trace-server=clickhouse (and ClickHouse available), uses the real
    server. The query builder emits thread_id IN ([]) which ClickHouse accepts and
    returns no rows.
    """
    req = tsi.CallsQueryReq(
        project_id="test_project",
        filter=tsi.CallsFilter(thread_ids=[]),
        limit=100,
    )
    result = list(ch_server.calls_query_stream(req))

    # Empty thread_ids -> IN [] -> no rows from ClickHouse
    assert result == []


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
    ch_schema = chts.ch_call_dict_to_call_schema_dict(test_data)
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
    ch_schema = chts.ch_call_dict_to_call_schema_dict(test_data)
    assert ch_schema["storage_size_bytes"] is None
    assert ch_schema["total_storage_size_bytes"] is None


def test_clickhouse_expire_at_sentinel_converts_to_none():
    """The DB far-future expire_at sentinel is hidden at the API boundary."""
    started_at = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    test_data = {
        "storage_size_bytes": None,
        "total_storage_size_bytes": None,
        "id": "test_id",
        "project_id": "test_project",
        "trace_id": "test_trace",
        "parent_id": None,
        "started_at": started_at,
        "ended_at": None,
        "summary_dump": None,
        "wb_run_id": None,
        "wb_run_step": None,
        "wb_user_id": None,
        "expire_at": EXPIRE_AT_NEVER,
    }

    ch_schema = chts.ch_call_dict_to_call_schema_dict(test_data)

    assert ch_schema["expire_at"] is None


def test_ch_call_to_row_sentinelizes_expire_at_for_v1_insert_paths():
    """expire_at=None on an insertable lands as EXPIRE_AT_NEVER in the call_parts row.

    Regression guard for the refactor that moved expire_at from a per-subclass
    `default=EXPIRE_AT_NEVER` to a base-class `default=None`. The non-null call_parts
    column now relies on `ch_call_to_row` -> `to_ch_value('expire_at', None)` to
    sentinelize at write time.

    Covers both v1 insert paths through `ch_call_to_row`:
      - `_insert_call(CallStartCHInsertable)` (and CallEnd/Update/Delete via the union)
      - `_insert_call_to_v1(CallCompleteCHInsertable)` (v1 fallback when a project
        has not yet migrated to calls_complete)
    """
    expire_at_idx = ALL_CALL_INSERT_COLUMNS.index("expire_at")
    started_at = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    # validation requires a base64-encoded project_id
    project_id = base64.b64encode(b"test_project").decode("ascii")

    # CallStartCHInsertable: expire_at default is None -> sentinelized at row time.
    start = CallStartCHInsertable(
        project_id=project_id,
        id="0193f7a5-1234-7000-8000-000000000000",
        trace_id="0193f7a5-1234-7000-8000-000000000001",
        op_name="test_op",
        started_at=started_at,
        attributes_dump="{}",
        inputs_dump="{}",
    )
    assert start.expire_at is None
    assert ch_call_to_row(start)[expire_at_idx] == EXPIRE_AT_NEVER

    # CallCompleteCHInsertable: same default, exercised via _insert_call_to_v1.
    complete = CallCompleteCHInsertable(
        project_id=project_id,
        id="0193f7a5-1234-7000-8000-000000000002",
        trace_id="0193f7a5-1234-7000-8000-000000000003",
        op_name="test_op",
        started_at=started_at,
        ended_at=started_at,
        attributes_dump="{}",
        inputs_dump="{}",
        output_dump="null",
        summary_dump="{}",
    )
    assert complete.expire_at is None
    assert ch_call_to_row(complete)[expire_at_idx] == EXPIRE_AT_NEVER

    # Explicitly-set expire_at must pass through unchanged (not re-sentinelized).
    explicit_expire = datetime(2025, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
    start_with_ttl = start.model_copy(update={"expire_at": explicit_expire})
    assert ch_call_to_row(start_with_ttl)[expire_at_idx] == explicit_expire


def test_ch_row_helpers_match_model_dump_baseline():
    """ch_call_to_row / ch_complete_call_to_row read fields via getattr instead of
    model_dump() to skip per-insert dict allocation. The row contents must stay
    byte-for-byte identical to the previous model_dump-based implementation.
    """
    started_at = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    project_id = base64.b64encode(b"test_project").decode("ascii")
    explicit_expire = datetime(2025, 6, 1, 0, 0, 0, tzinfo=timezone.utc)

    start = CallStartCHInsertable(
        project_id=project_id,
        id="0193f7a5-1234-7000-8000-000000000010",
        trace_id="0193f7a5-1234-7000-8000-000000000011",
        op_name="test_op",
        display_name="display",
        started_at=started_at,
        attributes_dump="{}",
        inputs_dump="{}",
        input_refs=[f"weave-trace-internal:///{project_id}/object/name:digest"],
        output_refs=[],
        wb_user_id="dXNlci1pZA==",
        wb_run_id="dXNlci1pZA==:run",
        wb_run_step=1,
    )
    start_with_ttl = start.model_copy(update={"expire_at": explicit_expire})
    complete = CallCompleteCHInsertable(
        project_id=project_id,
        id="0193f7a5-1234-7000-8000-000000000012",
        trace_id="0193f7a5-1234-7000-8000-000000000013",
        op_name="test_op",
        started_at=started_at,
        ended_at=started_at,
        attributes_dump="{}",
        inputs_dump="{}",
        output_dump="null",
        summary_dump="{}",
    )

    for call in (start, start_with_ttl, complete):
        dumped = call.model_dump()
        expected = [
            ch_sentinel_values.to_ch_value(col, dumped.get(col))
            if col in ch_sentinel_values.SENTINEL_IN_CALLS_MERGED_FIELDS
            else dumped.get(col)
            for col in ALL_CALL_INSERT_COLUMNS
        ]
        assert ch_call_to_row(call) == expected

    expected_complete = [
        ch_sentinel_values.to_ch_value(col, complete.model_dump().get(col))
        for col in ALL_CALL_COMPLETE_INSERT_COLUMNS
    ]
    assert ch_complete_call_to_row(complete) == expected_complete


def test_clickhouse_distributed_mode_properties():
    """Test that ClickHouse distributed mode properties are correctly initialized."""
    # Test with distributed mode enabled
    with (
        patch(
            "weave.trace_server.environment.wf_clickhouse_use_distributed_tables"
        ) as mock_distributed,
        patch(
            "weave.trace_server.environment.wf_clickhouse_replicated_cluster"
        ) as mock_cluster,
    ):
        mock_distributed.return_value = True
        mock_cluster.return_value = "test_cluster"

        server = chts.ClickHouseTraceServer(host="test_host")

        # Test distributed mode property
        assert server.use_distributed_mode is True
        assert server.clickhouse_cluster_name == "test_cluster"
        from weave.trace_server import clickhouse_trace_server_settings as ch_settings

        expected_table = f"calls_complete{ch_settings.LOCAL_TABLE_SUFFIX}"
        assert server._get_calls_complete_table_name() == expected_table

    # Test with distributed mode disabled
    with (
        patch(
            "weave.trace_server.environment.wf_clickhouse_use_distributed_tables"
        ) as mock_distributed,
        patch(
            "weave.trace_server.environment.wf_clickhouse_replicated_cluster"
        ) as mock_cluster,
    ):
        mock_distributed.return_value = False
        mock_cluster.return_value = None

        server = chts.ClickHouseTraceServer(host="test_host")

        # Test distributed mode property
        assert server.use_distributed_mode is False
        assert server.clickhouse_cluster_name is None
        assert server._get_calls_complete_table_name() == "calls_complete"


def test_keyless_custom_stream_preserves_none_api_key():
    server = chts.ClickHouseTraceServer(host="test_host")
    req = tsi.CompletionsCreateReq(
        project_id="test_project",
        inputs=tsi.CompletionsCreateRequestInputs(
            model="custom::runtime::agent",
            messages=[{"role": "user", "content": "Hello"}],
        ),
        track_llm_call=False,
    )
    model_info = chts.CompletionModelInfo(
        model_name="runtime/agent",
        api_key=None,
        provider="custom",
        base_url="https://runtime.example.com/v1",
        extra_headers={"X-Auth": "header-token"},
        return_type="openai",
    )

    with (
        patch.object(
            chts,
            "resolve_and_apply_prompt",
            return_value=(req.inputs.messages, req.inputs.messages),
        ),
        patch.object(chts, "_setup_completion_model_info", return_value=model_info),
        patch.object(
            chts,
            "lite_llm_completion_stream",
            return_value=iter([{"choices": []}]),
        ) as completion_stream,
    ):
        list(server.completions_create_stream(req))

    completion_stream.assert_called_once()
    assert completion_stream.call_args.kwargs["api_key"] is None


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

    # Set up mock secret fetcher
    mock_secret_fetcher = MagicMock()
    mock_secret_fetcher.fetch.return_value = {
        "secrets": {"CUSTOM_API_KEY": "test-api-key-value"}
    }

    with (
        secret_fetcher_context(mock_secret_fetcher),
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

    # Set up mock secret fetcher
    mock_secret_fetcher = MagicMock()
    mock_secret_fetcher.fetch.return_value = {
        "secrets": {"CUSTOM_API_KEY": "test-api-key-value"}
    }

    # Mock ClickHouse client to prevent real connection
    mock_ch_client = MagicMock()

    with (
        secret_fetcher_context(mock_secret_fetcher),
        patch(
            "weave.trace_server.clickhouse_trace_server_batched.lite_llm_completion_stream"
        ) as mock_litellm,
        patch.object(chts.ClickHouseTraceServer, "obj_read") as mock_obj_read,
        patch(
            "weave.trace_server.clickhouse_trace_server_batched.AgentWriteHandler"
        ) as mock_agent_writer_cls,
        patch.object(
            chts.ClickHouseTraceServer, "_mint_client", return_value=mock_ch_client
        ),
    ):
        mock_agent_writer = MagicMock()
        mock_agent_writer_cls.return_value = mock_agent_writer

        mock_stream = MagicMock()
        mock_stream.__iter__.return_value = mock_chunks
        mock_litellm.return_value = mock_stream

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

        assert len(chunks) == 3  # Meta chunk + 2 content chunks
        assert "_meta" in chunks[0]
        assert "weave_call_id" in chunks[0]["_meta"]
        assert chunks[1]["choices"][0]["delta"]["content"] == "Streamed"
        assert chunks[2]["choices"][0]["finish_reason"] == "stop"
        assert "usage" in chunks[2]

        # Open span + completed span
        assert mock_agent_writer.insert_span.call_count == 2
        completed_span = mock_agent_writer.insert_span.call_args_list[1][0][0]
        assert completed_span.project_id == "dGVzdF9wcm9qZWN0"

        mock_litellm.assert_called_once()
        call_args = mock_litellm.call_args[1]
        assert (
            call_args.get("api_base")
            or call_args.get("base_url") == "https://api.custom.com"
        )
        assert call_args["extra_headers"] == {"X-Custom": "value"}


def test_completions_create_stream_multiple_choices():
    """Test completions_create_stream with n > 1 properly separates choices in a single call."""
    # Mock chunks to be returned by the stream with multiple choices (n=2)
    mock_chunks = [
        {
            "choices": [
                {
                    "delta": {"content": "Hello"},
                    "finish_reason": None,
                    "index": 0,
                },
                {
                    "delta": {"content": "Hi"},
                    "finish_reason": None,
                    "index": 1,
                },
            ],
            "id": "test-id",
            "model": "gpt-3.5-turbo",
            "created": 1234567890,
        },
        {
            "choices": [
                {
                    "delta": {"content": " there!"},
                    "finish_reason": None,
                    "index": 0,
                },
                {
                    "delta": {"content": " friend!"},
                    "finish_reason": None,
                    "index": 1,
                },
            ],
            "id": "test-id",
            "model": "gpt-3.5-turbo",
            "created": 1234567890,
        },
        {
            "choices": [
                {
                    "delta": {},
                    "finish_reason": "stop",
                    "index": 0,
                },
                {
                    "delta": {},
                    "finish_reason": "stop",
                    "index": 1,
                },
            ],
            "id": "test-id",
            "model": "gpt-3.5-turbo",
            "created": 1234567890,
            "usage": {
                "prompt_tokens": 5,
                "completion_tokens": 4,
                "total_tokens": 9,
            },
        },
    ]

    # Mock the secret fetcher
    mock_secret_fetcher = MagicMock()
    mock_secret_fetcher.fetch.return_value = {"secrets": {"OPENAI_API_KEY": "test-key"}}

    # Mock ClickHouse client to prevent real connection
    mock_ch_client = MagicMock()

    with (
        secret_fetcher_context(mock_secret_fetcher),
        patch(
            "weave.trace_server.clickhouse_trace_server_batched.lite_llm_completion_stream"
        ) as mock_litellm,
        patch(
            "weave.trace_server.clickhouse_trace_server_batched.AgentWriteHandler"
        ) as mock_agent_writer_cls,
        patch.object(
            chts.ClickHouseTraceServer, "_mint_client", return_value=mock_ch_client
        ),
    ):
        mock_agent_writer = MagicMock()
        mock_agent_writer_cls.return_value = mock_agent_writer

        mock_stream = MagicMock()
        mock_stream.__iter__.return_value = mock_chunks
        mock_litellm.return_value = mock_stream

        req = tsi.CompletionsCreateReq(
            project_id="dGVzdF9wcm9qZWN0",
            inputs=tsi.CompletionsCreateRequestInputs(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "Say hello"}],
                n=2,
            ),
            track_llm_call=True,
        )

        server = chts.ClickHouseTraceServer(host="test_host")
        stream = server.completions_create_stream(req)
        chunks = list(stream)

        assert len(chunks) == 4  # Meta chunk + 3 content chunks
        assert "_meta" in chunks[0]
        assert "weave_call_id" in chunks[0]["_meta"]
        assert "weave_call_ids" not in chunks[0]["_meta"]

        assert chunks[1]["choices"][0]["delta"]["content"] == "Hello"
        assert chunks[1]["choices"][1]["delta"]["content"] == "Hi"
        assert chunks[3]["choices"][0]["finish_reason"] == "stop"
        assert chunks[3]["choices"][1]["finish_reason"] == "stop"

        # Open span + completed span
        assert mock_agent_writer.insert_span.call_count == 2

        completed_span = mock_agent_writer.insert_span.call_args_list[1][0][0]
        assert completed_span.project_id == "dGVzdF9wcm9qZWN0"
        assert completed_span.request_model == "gpt-3.5-turbo"

        # Verify both choices are captured in output_messages
        assert len(completed_span.output_messages) == 2

        mock_litellm.assert_called_once()
        call_args = mock_litellm.call_args[1]
        assert call_args["inputs"].n == 2


def test_completions_create_stream_single_choice_unified_wrapper():
    """Test completions_create_stream with n=1 using the unified wrapper maintains backward compatibility."""
    # Mock chunks for single choice (n=1)
    mock_chunks = [
        {
            "choices": [
                {
                    "delta": {"content": "Hello world!"},
                    "finish_reason": None,
                    "index": 0,
                },
            ],
            "id": "test-id",
            "model": "gpt-3.5-turbo",
            "created": 1234567890,
        },
        {
            "choices": [
                {
                    "delta": {},
                    "finish_reason": "stop",
                    "index": 0,
                },
            ],
            "id": "test-id",
            "model": "gpt-3.5-turbo",
            "created": 1234567890,
            "usage": {
                "prompt_tokens": 5,
                "completion_tokens": 2,
                "total_tokens": 7,
            },
        },
    ]

    # Mock the secret fetcher
    mock_secret_fetcher = MagicMock()
    mock_secret_fetcher.fetch.return_value = {"secrets": {"OPENAI_API_KEY": "test-key"}}

    # Mock ClickHouse client to prevent real connection
    mock_ch_client = MagicMock()

    with (
        secret_fetcher_context(mock_secret_fetcher),
        patch(
            "weave.trace_server.clickhouse_trace_server_batched.lite_llm_completion_stream"
        ) as mock_litellm,
        patch(
            "weave.trace_server.clickhouse_trace_server_batched.AgentWriteHandler"
        ) as mock_agent_writer_cls,
        patch.object(
            chts.ClickHouseTraceServer, "_mint_client", return_value=mock_ch_client
        ),
    ):
        mock_agent_writer = MagicMock()
        mock_agent_writer_cls.return_value = mock_agent_writer

        mock_stream = MagicMock()
        mock_stream.__iter__.return_value = mock_chunks
        mock_litellm.return_value = mock_stream

        req = tsi.CompletionsCreateReq(
            project_id="dGVzdF9wcm9qZWN0",
            inputs=tsi.CompletionsCreateRequestInputs(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "Say hello"}],
                n=1,
            ),
            track_llm_call=True,
        )

        server = chts.ClickHouseTraceServer(host="test_host")
        stream = server.completions_create_stream(req)
        chunks = list(stream)

        assert len(chunks) == 3  # Meta chunk + 2 content chunks
        assert "_meta" in chunks[0]
        assert "weave_call_id" in chunks[0]["_meta"]
        assert "weave_call_ids" not in chunks[0]["_meta"]

        assert chunks[1]["choices"][0]["delta"]["content"] == "Hello world!"
        assert chunks[2]["choices"][0]["finish_reason"] == "stop"

        # Open span + completed span
        assert mock_agent_writer.insert_span.call_count == 2

        completed_span = mock_agent_writer.insert_span.call_args_list[1][0][0]
        assert completed_span.project_id == "dGVzdF9wcm9qZWN0"
        assert completed_span.request_model == "gpt-3.5-turbo"
        assert len(completed_span.output_messages) == 1
        assert completed_span.output_messages[0].content == "Hello world!"

        mock_litellm.assert_called_once()
        call_args = mock_litellm.call_args[1]
        assert call_args["inputs"].n == 1


def test_completions_create_stream_with_prompt_and_template_vars():
    """Test completions_create_stream with prompt and template variables."""
    # Mock the MessagesPrompt object with template variables
    mock_prompt_obj = tsi.ObjSchema(
        project_id="test_project",
        object_id="test-prompt",
        digest="digest-1",
        base_object_class="MessagesPrompt",
        leaf_object_class="MessagesPrompt",
        val={
            "messages": [
                {"role": "system", "content": "You are {assistant_name}."},
            ]
        },
        created_at=datetime.now(),
        version_index=1,
        is_latest=1,
        kind="object",
        deleted_at=None,
    )

    # Mock response chunks
    mock_chunks = [
        {
            "choices": [
                {
                    "delta": {"content": "Math"},
                    "finish_reason": None,
                    "index": 0,
                }
            ],
            "id": "test-id",
            "model": "gpt-3.5-turbo",
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
            "model": "gpt-3.5-turbo",
            "created": 1234567890,
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 1,
                "total_tokens": 11,
            },
        },
    ]

    # Set up mock secret fetcher
    mock_secret_fetcher = MagicMock()
    mock_secret_fetcher.fetch.return_value = {
        "secrets": {"OPENAI_API_KEY": "test-api-key-value"}
    }

    with (
        secret_fetcher_context(mock_secret_fetcher),
        patch(
            "weave.trace_server.clickhouse_trace_server_batched.lite_llm_completion_stream"
        ) as mock_litellm,
        patch.object(chts.ClickHouseTraceServer, "obj_read") as mock_obj_read,
    ):
        # Mock the litellm completion stream
        mock_stream = MagicMock()
        mock_stream.__iter__.return_value = mock_chunks
        mock_litellm.return_value = mock_stream

        # Mock obj_read to return the prompt
        mock_obj_read.return_value = tsi.ObjReadRes(obj=mock_prompt_obj)

        prompt_uri = "weave-trace-internal:///test_project/object/test-prompt:digest-1"

        # Create test request with prompt and template_vars
        req = tsi.CompletionsCreateReq(
            project_id="test_project",
            inputs=tsi.CompletionsCreateRequestInputs(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "What is {subject}?"}],
                prompt=prompt_uri,
                template_vars={"assistant_name": "MathBot", "subject": "algebra"},
            ),
            track_llm_call=False,
        )

        server = chts.ClickHouseTraceServer(host="test_host")
        stream = server.completions_create_stream(req)
        chunks = list(stream)

        # Verify the chunks
        assert len(chunks) == 2
        assert chunks[0]["choices"][0]["delta"]["content"] == "Math"
        assert chunks[1]["choices"][0]["finish_reason"] == "stop"

        # Verify litellm was called with substituted messages
        mock_litellm.assert_called_once()
        call_kwargs = mock_litellm.call_args[1]
        messages = call_kwargs["inputs"].messages

        # Should have 2 messages: prompt + user (both with template vars replaced)
        assert len(messages) == 2
        assert messages[0]["content"] == "You are MathBot."
        assert messages[1]["content"] == "What is algebra?"


@pytest.mark.disable_logging_error_check
def test_completions_create_stream_prompt_not_found_error():
    """Test error handling when prompt object is not found during streaming."""
    # Set up mock secret fetcher
    mock_secret_fetcher = MagicMock()
    mock_secret_fetcher.fetch.return_value = {
        "secrets": {"OPENAI_API_KEY": "test-api-key-value"}
    }

    with (
        secret_fetcher_context(mock_secret_fetcher),
        patch.object(chts.ClickHouseTraceServer, "obj_read") as mock_obj_read,
    ):
        # Mock obj_read to raise NotFoundError
        from weave.trace_server.errors import NotFoundError

        mock_obj_read.side_effect = NotFoundError("Prompt not found")

        prompt_uri = (
            "weave-trace-internal:///test_project/object/missing-prompt:digest-1"
        )

        # Create test request with non-existent prompt
        req = tsi.CompletionsCreateReq(
            project_id="test_project",
            inputs=tsi.CompletionsCreateRequestInputs(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "Hi"}],
                prompt=prompt_uri,
            ),
            track_llm_call=False,
        )

        server = chts.ClickHouseTraceServer(host="test_host")
        stream = server.completions_create_stream(req)

        # Collect all chunks - should get error chunk
        chunks = list(stream)

        # Should have exactly one error chunk
        assert len(chunks) == 1
        assert "error" in chunks[0]
        assert "Failed to resolve and apply prompt" in chunks[0]["error"]


class _MockInsertError(Exception):
    """Simulates a ClickHouse insert error."""

    pass


def test_insert_retries_empty_query_error():
    """Verify 'Empty query' errors are retried (generator exhaustion during HTTP retry)."""
    mock_ch_client = MagicMock()
    mock_ch_client.command.return_value = None
    mock_summary = MagicMock()
    # First call fails with empty query, second succeeds
    mock_ch_client.insert.side_effect = [
        DatabaseError("Empty query. (SYNTAX_ERROR)"),
        mock_summary,
    ]

    with patch.object(
        chts.ClickHouseTraceServer, "_mint_client", return_value=mock_ch_client
    ):
        server = chts.ClickHouseTraceServer(host="test_host")
        result = server._insert("t", data=[[1]], column_names=["a"])

        assert result == mock_summary
        assert mock_ch_client.insert.call_count == 2  # Retried once


def test_insert_deduplication_token_gated_on_replicated():
    """Replicated/distributed inserts carry a unique dedup-opt-out token; non-replicated is untouched."""

    def capture_settings(replicated: bool) -> list[dict]:
        mock_client = MagicMock()
        with (
            patch(
                "weave.trace_server.environment.wf_clickhouse_replicated",
                return_value=replicated,
            ),
            patch.object(
                chts.ClickHouseTraceServer, "_mint_client", return_value=mock_client
            ),
        ):
            server = chts.ClickHouseTraceServer(host="h")
            server._insert("t", data=[[1]], column_names=["a"])
            server._insert("t", data=[[1]], column_names=["a"])
        return [
            c.kwargs.get("settings") or {} for c in mock_client.insert.call_args_list
        ]

    tokens = [s.get("insert_deduplication_token") for s in capture_settings(True)]
    assert all(tokens), "replicated inserts must carry a dedup token"
    assert tokens[0] != tokens[1], "each insert must get a unique token"

    assert all(
        "insert_deduplication_token" not in s for s in capture_settings(False)
    ), "non-replicated inserts must be unchanged (SharedMergeTree/CH Cloud)"


def test_insert_with_empty_query_retry_contract():
    """The shared direct-insert helper retries empty query, exhausts, and passes through."""
    summary = MagicMock()

    # Retry once then succeed.
    client = MagicMock()
    client.insert.side_effect = [DatabaseError("Empty query. (SYNTAX_ERROR)"), summary]
    assert (
        insert_with_empty_query_retry(client, "spans", data=[[1]], column_names=["a"])
        is summary
    )
    assert client.insert.call_count == 2
    # The retry must re-send the same rows (fresh generator over the same list).
    assert client.insert.call_args.kwargs["data"] == [[1]]

    # Empty query on every attempt: exhausts the retry budget then re-raises.
    client = MagicMock()
    client.insert.side_effect = DatabaseError("Empty query. (SYNTAX_ERROR)")
    with pytest.raises(DatabaseError, match="Empty query"):
        insert_with_empty_query_retry(client, "spans", data=[[1]], column_names=["a"])
    assert client.insert.call_count == ch_settings.INSERT_MAX_RETRIES

    # Any other database error raises immediately, no retry.
    client = MagicMock()
    client.insert.side_effect = DatabaseError("Table does not exist")
    with pytest.raises(DatabaseError, match="Table does not exist"):
        insert_with_empty_query_retry(client, "spans", data=[[1]], column_names=["a"])
    assert client.insert.call_count == 1


def test_agent_write_handler_retries_empty_query():
    """Regression: the agent spans write path retries empty query (was bypassing _insert)."""
    summary = MagicMock()
    client = MagicMock()
    client.insert.side_effect = [DatabaseError("Empty query. (SYNTAX_ERROR)"), summary]
    span = AgentSpanCHInsertable(
        project_id="entity/project",
        trace_id="trace-1",
        span_id="span-1",
        span_name="chat",
        started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    AgentWriteHandler(client).insert_span(span)

    assert client.insert.call_count == 2
    assert client.insert.call_args.args[0] == "spans"


def test_ensure_obj_version_exists_retries_eventual_consistency():
    """Object-version existence checks should tolerate transient read-after-write misses."""
    server = chts.ClickHouseTraceServer(host="test_host")

    # Transient miss: the first lookup doesn't see the row yet, but the retry does.
    with patch.object(server, "_query") as mock_query:
        mock_query.side_effect = [
            MagicMock(result_rows=[]),
            MagicMock(result_rows=[(1,)]),
        ]

        server._ensure_obj_version_exists("test_project", "test_object", "digest-1")

        assert mock_query.call_count == 2

    # Real miss: after exhausting retries, the original NotFoundError still surfaces.
    with patch.object(
        server,
        "_query",
        return_value=MagicMock(result_rows=[]),
    ) as mock_query:
        with pytest.raises(
            NotFoundError,
            match="Object version test_object:digest-1 not found",
        ):
            server._ensure_obj_version_exists("test_project", "test_object", "digest-1")

        assert mock_query.call_count == chts.OBJ_READ_RETRY_ATTEMPTS


def test_select_objs_query_partial_value_miss_returns_empty():
    """If metadata rows exist but their value rows haven't replicated yet,
    return empty so obj_read raises NotFoundError and the retry wrapper kicks
    in. Without this, the missing val_dump would silently default to "{}" and
    the caller would decode a corrupted empty object.
    """
    server = chts.ClickHouseTraceServer(host="test_host")

    metadata_row = (
        "test_project",  # project_id
        "obj-id-1",  # object_id
        datetime(2024, 1, 1, tzinfo=timezone.utc),  # created_at
        [],  # refs
        "object",  # kind
        None,  # base_object_class
        None,  # leaf_object_class
        "digest-abc",  # digest
        0,  # version_index
        1,  # is_latest
        None,  # deleted_at
        None,  # wb_user_id
        1,  # version_count
        0,  # is_op
    )

    builder = chts.ObjectMetadataQueryBuilder("test_project")
    builder.add_digests_conditions("digest-abc")
    builder.add_object_ids_condition(["obj-id-1"])

    # Metadata SELECT finds the row; value SELECT returns nothing.
    with patch.object(
        chts.ClickHouseTraceServer,
        "_query_stream",
        side_effect=[iter([metadata_row]), iter([])],
    ):
        result = server._select_objs_query(builder, metadata_only=False)

    assert result == []

    # Sanity: when the value row is present, we get a populated result.
    with patch.object(
        chts.ClickHouseTraceServer,
        "_query_stream",
        side_effect=[
            iter([metadata_row]),
            iter([("obj-id-1", "digest-abc", '{"x": 1}')]),
        ],
    ):
        result = server._select_objs_query(builder, metadata_only=False)

    assert len(result) == 1
    assert result[0].val_dump == '{"x": 1}'


def test_file_content_read_retries_eventual_consistency():
    """File reads should tolerate transient read-after-write misses."""
    server = chts.ClickHouseTraceServer(host="test_host")
    req = tsi.FileContentReadReq(project_id="test_project", digest="digest-1")

    # Transient miss: the first lookup doesn't see the chunks yet, but the retry does.
    with patch.object(server, "_file_content_read_once") as mock_read_once:
        mock_read_once.side_effect = [
            NotFoundError("File with digest digest-1 not found"),
            tsi.FileContentReadRes(content=b"saved code"),
        ]

        assert server.file_content_read(req).content == b"saved code"
        assert mock_read_once.call_count == 2

    # Real miss: after exhausting retries, the original NotFoundError still surfaces.
    with patch.object(
        server,
        "_file_content_read_once",
        side_effect=NotFoundError("File with digest digest-1 not found"),
    ) as mock_read_once:
        with pytest.raises(
            NotFoundError,
            match="File with digest digest-1 not found",
        ):
            server.file_content_read(req)

        assert mock_read_once.call_count == 2


@pytest.mark.disable_logging_error_check
@pytest.mark.parametrize(
    ("error", "expected_calls"),
    [
        # Other errors should NOT be retried (call_count=1)
        (RuntimeError("unexpected"), 1),
        (ValueError("some value error"), 1),
        # Empty query errors retry up to INSERT_MAX_RETRIES
        pytest.param(
            "empty_query",
            3,  # INSERT_MAX_RETRIES
            id="empty_query_exhausts_retries",
        ),
    ],
)
def test_insert_error_handling(error, expected_calls):
    """Verify only 'Empty query' errors are retried; others fail immediately."""
    mock_ch_client = MagicMock()
    mock_ch_client.command.return_value = None

    if error == "empty_query":
        mock_ch_client.insert.side_effect = DatabaseError("Empty query. (SYNTAX_ERROR)")
        expected_exception = DatabaseError
    else:
        mock_ch_client.insert.side_effect = error
        expected_exception = type(error)

    with patch.object(
        chts.ClickHouseTraceServer, "_mint_client", return_value=mock_ch_client
    ):
        server = chts.ClickHouseTraceServer(host="test_host")
        with pytest.raises(expected_exception):
            server._insert("t", data=[[1]], column_names=["a"])

        assert mock_ch_client.insert.call_count == expected_calls


@pytest.mark.disable_logging_error_check
def test_call_batch_clears_on_insert_failure():
    """Verify _call_batch is cleared even when insert fails."""
    mock_ch_client = MagicMock()
    mock_ch_client.command.return_value = None
    mock_ch_client.insert.side_effect = _MockInsertError("Connection refused")
    # Mock query to return empty project (no data in calls_complete or calls_merged)
    mock_query_result = MagicMock()
    mock_query_result.result_rows = [(None, None)]
    mock_ch_client.query.return_value = mock_query_result

    project_id = base64.b64encode(b"test_entity/test_project").decode("utf-8")

    with patch.object(
        chts.ClickHouseTraceServer, "_mint_client", return_value=mock_ch_client
    ):
        server = chts.ClickHouseTraceServer(host="test_host")

        for i in range(5):
            try:
                req = tsi.CallStartReq(
                    start=tsi.StartedCallSchemaForInsert(
                        project_id=project_id,
                        op_name=f"test_op_{i}",
                        started_at=dt.datetime.now(dt.timezone.utc),
                        attributes={},
                        inputs={"test_input": "value"},
                    )
                )
                server.call_start(req)
            except _MockInsertError:
                pass

        assert len(server._call_batch) == 0, (
            f"Memory leak: _call_batch retained {len(server._call_batch)} rows "
            f"after failed inserts. Batch should be cleared on any exception."
        )


@pytest.fixture
def server_with_mock_kafka():
    """Create a ClickHouseTraceServer with mocked Kafka producer and CH client."""
    mock_ch_client = MagicMock()
    mock_ch_client.command.return_value = None
    mock_ch_client.insert.return_value = MagicMock()

    # Empty residence (resolves v2 writes to calls_complete); the calls_complete
    # end path then reads the stored started_at, so return one for that query.
    def _query_side_effect(query, *args, **kwargs):
        result = MagicMock()
        if "started_at" in query:
            result.result_rows = [(dt.datetime.now(dt.timezone.utc),)]
        else:
            result.result_rows = [(None, None)]
        return result

    mock_ch_client.query.side_effect = _query_side_effect

    mock_producer = MagicMock()

    with patch.object(
        chts.ClickHouseTraceServer, "_mint_client", return_value=mock_ch_client
    ):
        server = chts.ClickHouseTraceServer(host="test_host")
        server._kafka_producer = mock_producer
        with patch(
            "weave.trace_server.environment.wf_enable_online_eval",
            return_value=True,
        ):
            yield server, mock_producer


def _make_call_end_req() -> tsi.CallEndReq:
    return tsi.CallEndReq(
        end=tsi.EndedCallSchemaForInsert(
            project_id=base64.b64encode(b"test_entity/test_project").decode("utf-8"),
            id=str(uuid.uuid4()),
            ended_at=dt.datetime.now(dt.timezone.utc),
            output={},
            summary={},
            exception=None,
        )
    )


def test_call_end_flushes_kafka_immediately(server_with_mock_kafka):
    """Non-batch call_end should flush Kafka per-request."""
    server, mock_producer = server_with_mock_kafka

    server.call_end(_make_call_end_req())

    mock_producer.produce_call_end.assert_called_once()
    assert mock_producer.produce_call_end.call_args[0][1] is True


def test_call_end_v2_flushes_kafka_immediately(server_with_mock_kafka):
    """Non-batch call_end_v2 should flush Kafka per-request."""
    server, mock_producer = server_with_mock_kafka
    req = tsi.CallEndV2Req(
        end=tsi.EndedCallSchemaForInsertWithStartedAt(
            project_id=base64.b64encode(b"test_entity/test_project").decode("utf-8"),
            id=str(uuid.uuid4()),
            ended_at=dt.datetime.now(dt.timezone.utc),
            started_at=dt.datetime.now(dt.timezone.utc),
            output={},
            summary={},
            exception=None,
        )
    )

    server.call_end_v2(req)

    mock_producer.produce_call_end.assert_called_once()
    assert mock_producer.produce_call_end.call_args[0][1] is True


def test_call_end_adds_expire_at_from_ended_at(server_with_mock_kafka):
    """call_end adds expire_at = ended_at + retention_days on the end row."""
    server, _ = server_with_mock_kafka
    ended_at = dt.datetime(2026, 3, 1, tzinfo=dt.timezone.utc)
    req = tsi.CallEndReq(
        end=tsi.EndedCallSchemaForInsert(
            project_id=base64.b64encode(b"test_entity/test_project").decode("utf-8"),
            id=str(uuid.uuid4()),
            ended_at=ended_at,
            output={},
            summary={},
            exception=None,
        )
    )

    expire_index = ALL_CALL_INSERT_COLUMNS.index("expire_at")
    with (
        patch.object(chts, "get_project_retention_days", return_value=30),
        server.call_batch(),
    ):
        server.call_end(req)
        assert server._call_batch[-1][expire_index] == ended_at + dt.timedelta(days=30)


def test_call_batch_flushes_kafka_once_not_per_call_end(server_with_mock_kafka):
    """Batched call_end should NOT flush per-call. Flush happens once at batch exit."""
    server, mock_producer = server_with_mock_kafka
    num_calls = 5

    with server.call_batch():
        for _ in range(num_calls):
            server.call_end(_make_call_end_req())

    # All 5 calls produced a Kafka message
    assert mock_producer.produce_call_end.call_count == num_calls

    # Every produce_call_end was called with flush_immediately=False
    for call in mock_producer.produce_call_end.call_args_list:
        assert call[0][1] is False, (
            "produce_call_end should be called with flush_immediately=False inside batch"
        )

    # flush() called exactly once — by _flush_kafka_producer at batch exit
    mock_producer.flush.assert_called_once()


@pytest.mark.disable_logging_error_check
def test_file_batch_clears_on_insert_failure():
    """Verify _file_batch is cleared even when insert fails."""
    mock_ch_client = MagicMock()
    mock_ch_client.command.return_value = None
    mock_ch_client.insert.side_effect = _MockInsertError("Connection refused")

    with patch.object(
        chts.ClickHouseTraceServer, "_mint_client", return_value=mock_ch_client
    ):
        server = chts.ClickHouseTraceServer(host="test_host")

        file_chunk = MagicMock()
        file_chunk.model_dump.return_value = {
            "project_id": "test",
            "digest": "digest_0",
            "n_chunks": 1,
            "chunk_index": 0,
            "b64_data": "dGVzdA==",
        }
        server._file_batch.append(file_chunk)

        try:
            server._flush_file_chunks()
        except _MockInsertError:
            pass

        assert len(server._file_batch) == 0, (
            f"Memory leak: _file_batch retained {len(server._file_batch)} items "
            f"after failed insert. Batch should be cleared on any exception."
        )


# ── version_index ordering with MV-backed _first_created_at ─────────


def _obj_create(server, project_id, obj_id, val):
    return server.obj_create(
        tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(project_id=project_id, object_id=obj_id, val=val)
        )
    )


def _objs_query(server, project_id, obj_id):
    return server.objs_query(
        tsi.ObjQueryReq(
            project_id=project_id,
            filter=tsi.ObjectVersionFilter(object_ids=[obj_id]),
        )
    ).objs


def test_version_index_stable_on_republish(ch_server):
    """Republishing old content should not shift version indices.

    This verifies that the MV-backed _first_created_at anchors each digest
    to its original creation time, so re-inserting digest A doesn't push
    it to the end of the version ordering.
    """
    project_id = make_project_id("vidx")
    obj_id = "vidx_obj"

    r0 = _obj_create(ch_server, project_id, obj_id, {"v": "A"})
    r1 = _obj_create(ch_server, project_id, obj_id, {"v": "B"})
    r2 = _obj_create(ch_server, project_id, obj_id, {"v": "C"})

    # Re-publish A — inserts a duplicate row, but _first_created_at
    # from the MV should still return A's original timestamp
    _obj_create(ch_server, project_id, obj_id, {"v": "A"})

    objs = _objs_query(ch_server, project_id, obj_id)
    assert len(objs) == 3

    by_digest = {o.digest: o for o in objs}
    assert by_digest[r0.digest].version_index == 0
    assert by_digest[r1.digest].version_index == 1
    assert by_digest[r2.digest].version_index == 2


def test_delete_preserves_version_index_gaps(ch_server):
    """Deleting a version should leave a gap, not shift indices."""
    project_id = make_project_id("vidx")
    obj_id = "vidx_gap"

    digests = []
    for i in range(3):
        r = _obj_create(ch_server, project_id, obj_id, {"i": i})
        digests.append(r.digest)

    ch_server.obj_delete(
        tsi.ObjDeleteReq(project_id=project_id, object_id=obj_id, digests=[digests[1]])
    )

    non_deleted = [
        o for o in _objs_query(ch_server, project_id, obj_id) if o.deleted_at is None
    ]
    assert len(non_deleted) == 2

    by_digest = {o.digest: o for o in non_deleted}
    assert by_digest[digests[0]].version_index == 0
    assert by_digest[digests[2]].version_index == 2


@pytest.mark.parametrize("autogenerate_session_id", [True, False])
def test_concurrent_queries_on_one_client_vs_session_autogeneration(
    ch_server, autogenerate_session_id: bool
) -> None:
    """Session-id guard: clickhouse-connect rejects overlapping queries on one
    client with ProgrammingError when a session_id is present; with it
    disabled, overlapping queries succeed. See fix PR #6655.
    """
    client = clickhouse_connect.get_client(
        host=ch_server._host,
        port=ch_server._port,
        user=ch_server._user,
        password=ch_server._password,
        secure=ch_server._port == chts.CLICKHOUSE_SECURE_PORT,
        autogenerate_session_id=autogenerate_session_id,
    )
    n_workers = 8
    # Barrier makes all workers fire their query in the same instant; without
    # it the 8 queries can serialize on a cold container and the True branch
    # never produces an overlap.
    barrier = threading.Barrier(n_workers)

    def run_slow_query() -> None:
        barrier.wait()
        client.query("SELECT sleep(1.0)")

    try:
        errors: list[Exception] = []
        with ThreadPoolExecutor(max_workers=n_workers) as pool:
            futures = [pool.submit(run_slow_query) for _ in range(n_workers)]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    errors.append(e)
    finally:
        client.close()

    if autogenerate_session_id:
        # Exactly one query wins the session mutex; the remaining n-1 are
        # rejected client-side by clickhouse-connect.
        assert len(errors) == n_workers - 1, errors
        for e in errors:
            assert isinstance(e, ProgrammingError), (type(e), e)
            assert "concurrent queries within the same session" in str(e), e
    else:
        assert not errors, errors


# ── Explicit "latest" alias on obj_create ────────────────────────────
#
# End-to-end alias behavior (write, move on new version, move on dedup) is
# covered against both backends via tests/trace/test_obj_tags_aliases.py
# (test_alias_resolution + test_republish_promotes_to_latest). The tests
# below cover paths that are unique to the CH server: the obj_create_batch
# API (CH-only) and the partial-failure contract on the alias write.


def _resolve_latest(ch_server, project_id: str, object_id: str) -> str:
    """Resolve 'latest' for an object via the public obj_read API.

    Used to probe alias state in tests: with the hybrid is_latest model,
    obj_read('latest') returns the alias-pointed digest when the explicit
    'latest' alias row is live, and falls back to the computed
    most-recent-surviving digest when the alias is absent or tombstoned.
    """
    return ch_server.obj_read(
        tsi.ObjReadReq(project_id=project_id, object_id=object_id, digest="latest")
    ).obj.digest


def test_obj_create_batch_writes_latest_alias(ch_server):
    """obj_create_batch should write a 'latest' alias for every object in the batch."""
    project_id = make_project_id("alias")
    batch = [
        tsi.ObjSchemaForInsert(
            project_id=project_id, object_id=f"batch_obj_{i}", val={"v": i}
        )
        for i in range(3)
    ]
    results = ch_server.obj_create_batch(batch)

    for obj_in, res in zip(batch, results, strict=True):
        assert _resolve_latest(ch_server, project_id, obj_in.object_id) == res.digest


def test_obj_create_alias_failure_preserves_prior_latest(ch_server):
    """If the alias INSERT raises after the version row lands, the new version
    is readable by digest but 'latest' continues to resolve to the prior version.

    Documents the CH best-effort partial-failure contract for the
    (object_versions insert, aliases insert) pair.
    """
    project_id = make_project_id("alias")
    obj_id = "alias_failure"

    # Establish a prior latest.
    r1 = _obj_create(ch_server, project_id, obj_id, {"v": 1})
    assert _resolve_latest(ch_server, project_id, obj_id) == r1.digest

    # Simulate failure on the alias write for the next obj_create.
    # `mock.patch.object` correctly delattrs on exit when the original was
    # a class method (not an instance attribute) — leaves ch_server.__dict__
    # clean for test_reset_server_state_covers_all_attrs.
    def failing_insert_aliases(*args, **kwargs):
        raise RuntimeError("simulated alias write failure")

    with patch.object(ch_server, "_insert_aliases", failing_insert_aliases):
        with pytest.raises(RuntimeError, match="simulated alias write failure"):
            _obj_create(ch_server, project_id, obj_id, {"v": 2})

    # The version row landed (object_versions insert is unconditional in CH),
    # but 'latest' still resolves to v1 because the alias write never
    # completed. The explicit alias row pointing at v1 wins the hybrid
    # is_latest projection over the (otherwise-newer) v2 row.
    assert _resolve_latest(ch_server, project_id, obj_id) == r1.digest

    # A retry of the same content takes the dedup path, succeeds, and
    # promotes 'latest' to the new digest — the documented recovery flow.
    r2_retry = _obj_create(ch_server, project_id, obj_id, {"v": 2})
    assert _resolve_latest(ch_server, project_id, obj_id) == r2_retry.digest


def test_delete_current_latest_promotes_prior_surviving_version(ch_server):
    """Deleting the version that currently holds 'latest' must promote the
    next surviving version to 'latest'.

    Pre-WB-32435, is_latest was a window function over object_versions
    ranked by `(deleted_at IS NULL) DESC, _first_created_at DESC` so a
    soft-deleted latest naturally yielded the slot to the next surviving
    version. Post-WB-32435, is_latest is projected from the aliases-table
    CTE; obj_delete cascades a soft-delete onto the 'latest' alias row
    but never re-points it. Without a fix, obj_read('latest') and
    objs_query(latest_only=True) both go silent for an object that still
    has a surviving version — a regression the existing test suite does
    not cover because the public Python client's delete_object_versions
    flow only ever exercises 'delete by alias name' or 'delete all'.
    """
    project_id = make_project_id("alias_delete_latest")
    obj_id = "delete_latest_advances"

    r0 = _obj_create(ch_server, project_id, obj_id, {"v": 0})
    r1 = _obj_create(ch_server, project_id, obj_id, {"v": 1})

    ch_server.obj_delete(
        tsi.ObjDeleteReq(project_id=project_id, object_id=obj_id, digests=[r1.digest])
    )

    # objs_query(latest_only=True) should surface the surviving v0 row.
    latest = ch_server.objs_query(
        tsi.ObjQueryReq(
            project_id=project_id,
            filter=tsi.ObjectVersionFilter(object_ids=[obj_id], latest_only=True),
        )
    ).objs
    assert len(latest) == 1
    assert latest[0].digest == r0.digest
    assert latest[0].is_latest == 1

    # obj_read(digest='latest') must resolve to the surviving v0.
    read_res = ch_server.obj_read(
        tsi.ObjReadReq(project_id=project_id, object_id=obj_id, digest="latest")
    )
    assert read_res.obj.digest == r0.digest


# Common column lists for direct-insert seeding in the tests below.
_OBJ_VER_COLS = [
    "project_id",
    "object_id",
    "kind",
    "base_object_class",
    "leaf_object_class",
    "refs",
    "val_dump",
    "digest",
    "wb_user_id",
    "created_at",
    "deleted_at",
]
_ALIAS_COLS = [
    "project_id",
    "object_id",
    "alias",
    "digest",
    "wb_user_id",
    "created_at",
    "deleted_at",
]
_ALIAS_LIVE = dt.datetime.fromtimestamp(0, tz=dt.timezone.utc)


def _seed_obj_version(
    ch_server,
    project_id: str,
    obj_id: str,
    digest: str,
    created_at: dt.datetime,
    deleted_at: dt.datetime | None = None,
) -> None:
    ch_server._insert(
        "object_versions",
        data=[
            [
                project_id,
                obj_id,
                "object",
                None,
                None,
                [],
                "{}",
                digest,
                None,
                created_at,
                deleted_at,
            ]
        ],
        column_names=_OBJ_VER_COLS,
    )


def _seed_alias_row(
    ch_server,
    project_id: str,
    obj_id: str,
    digest: str,
    created_at: dt.datetime,
    wb_user_id: str = "real_user",
    deleted_at: dt.datetime | None = None,
) -> None:
    ch_server._insert(
        "aliases",
        data=[
            [
                project_id,
                obj_id,
                "latest",
                digest,
                wb_user_id,
                created_at,
                deleted_at if deleted_at is not None else _ALIAS_LIVE,
            ]
        ],
        column_names=_ALIAS_COLS,
    )


@pytest.mark.flaky(reruns=3, reruns_delay=0.2)
def test_obj_create_batch_duplicate_object_id_last_entry_wins_latest(ch_server):
    """obj_create_batch with two entries sharing object_id and different vals.

    Both alias-row INSERTs land in one CH batch with effectively the same
    `now64(3)` created_at — `argMax(digest, created_at)` ties, and CH
    breaks ties by storage order (per-part insertion order for rows with
    the same ORDER BY key).  Result: which digest wins 'latest' is
    undefined by CH spec, and `obj_create_batch` does not reject duplicates.

    This test pins the *expected* behavior — last entry in the batch wins
    'latest' — and surfaces the non-determinism if it does not hold.  A
    real fix would either (a) reject duplicate object_ids in the batch
    or (b) deterministically order alias INSERTs so the last batch entry
    wins (e.g. by post-processing alias_rows to keep only the last entry
    per object_id, OR by stamping alias rows with incrementing created_at
    within the batch).

    Decorated with `@pytest.mark.flaky(reruns=3)` because storage-order
    tiebreaking is not stable across runs; the failure mode here is the
    documented non-determinism, not a real regression.
    """
    project_id = make_project_id("alias_batch_dup")
    obj_id = "batch_dup_obj"
    batch = [
        tsi.ObjSchemaForInsert(project_id=project_id, object_id=obj_id, val={"v": "A"}),
        tsi.ObjSchemaForInsert(project_id=project_id, object_id=obj_id, val={"v": "B"}),
    ]
    results = ch_server.obj_create_batch(batch)
    # Both digests should be returned (they're content-derived).
    digest_a = results[0].digest
    digest_b = results[1].digest
    assert digest_a != digest_b, "fixture invariant: vals must yield distinct digests"

    resolved = _resolve_latest(ch_server, project_id, obj_id)
    assert resolved == digest_b, (
        f"obj_create_batch with duplicate object_id resolved 'latest' to "
        f"{resolved!r}; expected {digest_b!r} (the last entry in the batch).  "
        f"Both alias rows land at the same now64(3) timestamp; argMax ties "
        f"and CH breaks the tie by storage order, which is implementation-"
        f"defined.  Either deduplicate alias_rows in obj_create_batch (keep "
        f"only the last per object_id) or reject duplicate object_ids in "
        f"the batch."
    )


def test_legacy_no_alias_row_resolves_latest_via_computed_fallback(ch_server):
    """An object with a version row but NO 'latest' alias row (legacy data
    that pre-dates obj_create's alias write) must still resolve
    `obj_read('latest')` via the hybrid CTE's computed fallback.

    Catches: re-introducing the `if digest == "latest": return None`
    short-circuit in `_maybe_resolve_alias` while simultaneously
    removing the computed-fallback branch of the is_latest CTE — would
    leave legacy objects with no way to resolve 'latest'.

    Also catches the inverse: removing the short-circuit but breaking
    the fallback such that legacy objects only resolve via the alias row.
    """
    project_id = make_project_id("legacy_no_alias")
    obj_id = "legacy_obj"
    t_old = dt.datetime(2026, 5, 14, 10, 0, 0, tzinfo=dt.timezone.utc)
    t_new = dt.datetime(2026, 5, 14, 11, 0, 0, tzinfo=dt.timezone.utc)

    _seed_obj_version(ch_server, project_id, obj_id, "legacy_v0", t_old)
    _seed_obj_version(ch_server, project_id, obj_id, "legacy_v1", t_new)
    # Note: no alias row inserted.

    # _maybe_resolve_alias returns None (no alias row).  obj_read falls
    # through to make_metadata_query's CTE, where the computed fallback
    # (window function ranked by _first_created_at DESC) picks legacy_v1.
    assert ch_server._maybe_resolve_alias(project_id, obj_id, "latest") is None
    read_res = ch_server.obj_read(
        tsi.ObjReadReq(project_id=project_id, object_id=obj_id, digest="latest")
    )
    assert read_res.obj.digest == "legacy_v1", (
        f"legacy object with no alias row resolved 'latest' to "
        f"{read_res.obj.digest!r}; expected 'legacy_v1' (most recently "
        f"published).  The computed fallback in the is_latest CTE is not "
        f"firing — check that the CTE's IF expression includes the "
        f"`(project_id, object_id) NOT IN latest_alias_per_object` branch."
    )
    # Same answer through the latest_only path.
    latest_only = ch_server.objs_query(
        tsi.ObjQueryReq(
            project_id=project_id,
            filter=tsi.ObjectVersionFilter(object_ids=[obj_id], latest_only=True),
        )
    ).objs
    assert [o.digest for o in latest_only] == ["legacy_v1"]


def test_alias_pointing_at_soft_deleted_version_yields_clean_failure(ch_server):
    """When the 'latest' alias points to a digest whose object_versions
    row has been soft-deleted (a state obj_delete normally prevents by
    cascading the alias soft-delete, but which can arise from partial
    failures or external maintenance), `obj_read('latest')` must fail
    cleanly rather than return a ghost record.

    `_maybe_resolve_alias` returns the (live) alias digest; the
    subsequent obj_read filters on `deleted_at IS NULL` and finds no
    rows.  Expected behavior: raise NotFoundError / ObjectDeletedError.

    Catches: anyone removing the `deleted_at IS NULL` filter from the
    object-fetch path, which would surface deleted versions as 'latest'.
    """
    project_id = make_project_id("alias_to_tomb")
    obj_id = "alias_to_tomb_obj"
    digest_dead = "alias_target_tomb"
    t_pub = dt.datetime(2026, 5, 14, 10, 0, 0, tzinfo=dt.timezone.utc)
    t_tomb = dt.datetime(2026, 5, 14, 11, 0, 0, tzinfo=dt.timezone.utc)
    t_alias = dt.datetime(2026, 5, 14, 12, 0, 0, tzinfo=dt.timezone.utc)

    # Version exists then gets tombstoned, without going through obj_delete
    # (so the alias cascade does not run).  Then the live alias row points
    # at the now-tombstoned digest.
    _seed_obj_version(
        ch_server, project_id, obj_id, digest_dead, t_pub, deleted_at=t_tomb
    )
    _seed_alias_row(ch_server, project_id, obj_id, digest_dead, t_alias)

    # _maybe_resolve_alias resolves to the digest (it only knows about the
    # aliases table, not whether the target is alive in object_versions).
    assert ch_server._maybe_resolve_alias(project_id, obj_id, "latest") == digest_dead

    # obj_read must NOT return the tombstoned version.  Either raises, or
    # falls through to the CTE's computed fallback — which itself filters
    # tombstones via `(deleted_at IS NULL) DESC` and would find nothing.
    with pytest.raises((NotFoundError, ObjectDeletedError)) as exc_info:
        ch_server.obj_read(
            tsi.ObjReadReq(project_id=project_id, object_id=obj_id, digest="latest")
        )
    # Sanity: the error mentions "not found" or "deleted" — i.e. it's a
    # NotFoundError-family failure, not an unrelated crash.
    msg = str(exc_info.value).lower()
    assert "not found" in msg or "deleted" in msg, (
        f"obj_read raised an unexpected exception when 'latest' alias "
        f"pointed at a tombstoned version: {exc_info.value!r}.  Expected a "
        f"NotFoundError-family error mentioning 'not found' or 'deleted'."
    )


def _turn_ended_span_row() -> AgentSpanCHInsertable:
    """A finished root span; ScoreAgentSpansEvent.from_row yields a turn_ended event."""
    return AgentSpanCHInsertable(
        project_id="p",
        trace_id="tr",
        span_id="root",
        parent_span_id="",
        span_name="root",
        started_at=dt.datetime(2024, 1, 1, 11, 0, 0),
        ended_at=dt.datetime(2024, 1, 1, 12, 0, 0),
        agent_name="a",
        operation_name="invoke_agent",
    )


@pytest.mark.parametrize(
    ("online_eval", "scoring", "should_emit"),
    [
        (True, True, True),
        (True, False, False),  # scoring off -> skip
        (False, True, False),  # online eval off -> skip
    ],
    ids=["both-on", "scoring-off", "online-eval-off"],
)
def test_genai_otel_export_emit_gate(monkeypatch, online_eval, scoring, should_emit):
    """OTel ingest emits turn-ended events only when online eval and agent scoring
    are both enabled; otherwise the kafka emit is skipped.
    """
    mock_producer = MagicMock()
    monkeypatch.setattr(
        chts.ClickHouseTraceServer, "_mint_client", lambda self: MagicMock()
    )
    server = chts.ClickHouseTraceServer(host="test_host")
    server._kafka_producer = mock_producer

    monkeypatch.setattr(
        AgentWriteHandler,
        "insert_otel_spans",
        lambda self, req: (
            GenAIOTelExportRes(accepted_spans=1),
            [_turn_ended_span_row()],
        ),
    )
    monkeypatch.setattr(
        "weave.trace_server.environment.wf_enable_online_eval", lambda: online_eval
    )
    monkeypatch.setattr(
        "weave.trace_server.environment.wf_enable_agent_scoring", lambda: scoring
    )

    res = server.genai_otel_export(
        GenAIOTelExportReq(processed_spans=[], project_id="p", wb_user_id="")
    )

    assert res.accepted_spans == 1
    if should_emit:
        mock_producer.produce_score_agent_spans.assert_called_once()
        mock_producer.flush.assert_called_once_with(0)
    else:
        mock_producer.produce_score_agent_spans.assert_not_called()
        mock_producer.flush.assert_not_called()


def test_mint_client_forwards_send_receive_timeout():
    server = chts.ClickHouseTraceServer(host="test_host")
    with (
        patch.object(chts.ClickHouseTraceServer, "_ensure_database"),
        patch(
            "weave.trace_server.clickhouse_trace_server_batched.clickhouse_connect.get_client"
        ) as mock_get_client,
    ):
        mock_get_client.return_value = MagicMock()
        server._mint_client(
            send_receive_timeout=ch_settings.MIGRATION_CLIENT_SEND_RECEIVE_TIMEOUT_SEC
        )
        kwargs = mock_get_client.call_args.kwargs
        assert (
            kwargs["send_receive_timeout"]
            == ch_settings.MIGRATION_CLIENT_SEND_RECEIVE_TIMEOUT_SEC
        )


def test_mint_client_omits_send_receive_timeout_by_default():
    server = chts.ClickHouseTraceServer(host="test_host")
    with (
        patch.object(chts.ClickHouseTraceServer, "_ensure_database"),
        patch(
            "weave.trace_server.clickhouse_trace_server_batched.clickhouse_connect.get_client"
        ) as mock_get_client,
    ):
        mock_get_client.return_value = MagicMock()
        server._mint_client()
        assert "send_receive_timeout" not in mock_get_client.call_args.kwargs
