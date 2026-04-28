import base64
import datetime as dt
import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock, patch

import clickhouse_connect
import pytest
from clickhouse_connect.driver.exceptions import DatabaseError, ProgrammingError

from weave.trace_server import clickhouse_trace_server_batched as chts
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.clickhouse_schema import ALL_CALL_INSERT_COLUMNS
from weave.trace_server.errors import NotFoundError
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


def test_clickhouse_calls_query_stream_empty_thread_ids_against_real_clickhouse(
    ch_server,
):
    """Filter with thread_ids=[] against real ClickHouse: query runs and returns 0 rows.

    When run with --trace-server=clickhouse (and ClickHouse available), uses the real
    server. The query builder emits thread_id IN ([]) which ClickHouse accepts and
    returns no rows. Skips when trace_server is SQLite.
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
        patch.object(
            chts.ClickHouseTraceServer, "_insert_call_complete"
        ) as mock_insert_complete,
        patch.object(
            chts.ClickHouseTraceServer, "_update_call_end_in_calls_complete"
        ) as mock_update_end,
        patch.object(
            chts.ClickHouseTraceServer, "_mint_client", return_value=mock_ch_client
        ),
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

        # Verify call tracking via calls_complete (empty project → CALLS_COMPLETE)
        mock_insert_complete.assert_called_once()
        mock_update_end.assert_called_once()
        start_call = mock_insert_complete.call_args[0][0]
        assert start_call.project_id == "dGVzdF9wcm9qZWN0"
        assert start_call.ended_at is None

        # Verify litellm was called with correct parameters
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
        patch.object(
            chts.ClickHouseTraceServer, "_insert_call_complete"
        ) as mock_insert_complete,
        patch.object(
            chts.ClickHouseTraceServer, "_update_call_end_in_calls_complete"
        ) as mock_update_end,
        patch.object(
            chts.ClickHouseTraceServer, "_mint_client", return_value=mock_ch_client
        ),
    ):
        # Mock the litellm completion stream
        mock_stream = MagicMock()
        mock_stream.__iter__.return_value = mock_chunks
        mock_litellm.return_value = mock_stream

        # Create test request with n=2 and tracking enabled
        req = tsi.CompletionsCreateReq(
            project_id="dGVzdF9wcm9qZWN0",
            inputs=tsi.CompletionsCreateRequestInputs(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "Say hello"}],
                n=2,  # Request 2 completions
            ),
            track_llm_call=True,
        )

        server = chts.ClickHouseTraceServer(host="test_host")
        stream = server.completions_create_stream(req)
        chunks = list(stream)

        # Verify streaming functionality
        assert len(chunks) == 4  # Meta chunk + 3 content chunks
        assert "_meta" in chunks[0]
        assert "weave_call_id" in chunks[0]["_meta"]  # Single call ID (not multiple)
        assert (
            "weave_call_ids" not in chunks[0]["_meta"]
        )  # Should not have multiple format

        # Verify original chunks are preserved
        assert chunks[1]["choices"][0]["delta"]["content"] == "Hello"
        assert chunks[1]["choices"][1]["delta"]["content"] == "Hi"
        assert chunks[3]["choices"][0]["finish_reason"] == "stop"
        assert chunks[3]["choices"][1]["finish_reason"] == "stop"

        # Verify call tracking via calls_complete (empty project → CALLS_COMPLETE)
        mock_insert_complete.assert_called_once()
        mock_update_end.assert_called_once()

        # Verify start call
        start_call = mock_insert_complete.call_args[0][0]
        assert start_call.project_id == "dGVzdF9wcm9qZWN0"
        start_call_inputs = json.loads(start_call.inputs_dump)
        assert start_call_inputs["model"] == "gpt-3.5-turbo"
        assert start_call_inputs["n"] == 2
        assert "choice_index" not in start_call_inputs

        # Verify end call has correct output with BOTH choices
        end_call = mock_update_end.call_args[0][0]
        assert end_call.project_id == "dGVzdF9wcm9qZWN0"
        end_call_output = end_call.output
        assert "choices" in end_call_output
        assert len(end_call_output["choices"]) == 2

        # Verify both choices are accumulated correctly
        choices = end_call_output["choices"]

        # Choice 0
        choice_0 = next(c for c in choices if c["index"] == 0)
        assert choice_0["message"]["content"] == "Hello there!"
        assert choice_0["finish_reason"] == "stop"

        # Choice 1
        choice_1 = next(c for c in choices if c["index"] == 1)
        assert choice_1["message"]["content"] == "Hi friend!"
        assert choice_1["finish_reason"] == "stop"

        # Verify litellm was called with correct parameters
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
        patch.object(
            chts.ClickHouseTraceServer, "_insert_call_complete"
        ) as mock_insert_complete,
        patch.object(
            chts.ClickHouseTraceServer, "_update_call_end_in_calls_complete"
        ) as mock_update_end,
        patch.object(
            chts.ClickHouseTraceServer, "_mint_client", return_value=mock_ch_client
        ),
    ):
        # Mock the litellm completion stream
        mock_stream = MagicMock()
        mock_stream.__iter__.return_value = mock_chunks
        mock_litellm.return_value = mock_stream

        # Create test request with n=1 and tracking enabled
        req = tsi.CompletionsCreateReq(
            project_id="dGVzdF9wcm9qZWN0",
            inputs=tsi.CompletionsCreateRequestInputs(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "Say hello"}],
                n=1,  # Single completion
            ),
            track_llm_call=True,
        )

        server = chts.ClickHouseTraceServer(host="test_host")
        stream = server.completions_create_stream(req)
        chunks = list(stream)

        # Verify streaming functionality - should maintain legacy format
        assert len(chunks) == 3  # Meta chunk + 2 content chunks
        assert "_meta" in chunks[0]
        assert "weave_call_id" in chunks[0]["_meta"]
        assert "weave_call_ids" not in chunks[0]["_meta"]

        # Verify content
        assert chunks[1]["choices"][0]["delta"]["content"] == "Hello world!"
        assert chunks[2]["choices"][0]["finish_reason"] == "stop"

        # Verify call tracking via calls_complete (empty project → CALLS_COMPLETE)
        mock_insert_complete.assert_called_once()
        mock_update_end.assert_called_once()

        # Verify start call
        start_call = mock_insert_complete.call_args[0][0]
        assert start_call.project_id == "dGVzdF9wcm9qZWN0"
        start_call_inputs = json.loads(start_call.inputs_dump)
        assert start_call_inputs["model"] == "gpt-3.5-turbo"
        assert start_call_inputs["n"] == 1
        assert "choice_index" not in start_call_inputs

        # Verify end call has correct output
        end_call = mock_update_end.call_args[0][0]
        assert end_call.project_id == "dGVzdF9wcm9qZWN0"
        end_call_output = end_call.output
        assert "choices" in end_call_output
        assert len(end_call_output["choices"]) == 1
        choice = end_call_output["choices"][0]
        assert choice["index"] == 0
        assert choice["message"]["content"] == "Hello world!"

        # Verify litellm was called with correct parameters
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

    # Mock query to return empty project (resolves to CALLS_MERGED write target)
    mock_query_result = MagicMock()
    mock_query_result.result_rows = [(None, None)]
    mock_ch_client.query.return_value = mock_query_result

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


def _make_project_id(prefix: str) -> str:
    raw = f"test/{prefix}_{uuid.uuid4().hex[:8]}"
    return base64.b64encode(raw.encode()).decode()


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
    project_id = _make_project_id("vidx")
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
    project_id = _make_project_id("vidx")
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
