import base64
import datetime as dt
import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock, patch

import pytest

from weave.trace_server import clickhouse_trace_server_batched as chts
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.clickhouse_schema import (
    CallEndCHInsertable,
    CallStartCHInsertable,
)
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
        patch.object(chts.ClickHouseTraceServer, "_insert_call") as mock_insert_call,
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
        patch.object(chts.ClickHouseTraceServer, "_insert_call") as mock_insert_call,
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

        # Verify call tracking - should have 1 start call + 1 end call = 2 total
        assert mock_insert_call.call_count == 2

        # Get all the calls
        call_args = [call[0][0] for call in mock_insert_call.call_args_list]
        start_calls = [
            call for call in call_args if isinstance(call, CallStartCHInsertable)
        ]
        end_calls = [
            call for call in call_args if isinstance(call, CallEndCHInsertable)
        ]

        # Should have 1 start call and 1 end call
        assert len(start_calls) == 1
        assert len(end_calls) == 1

        # Verify start call
        start_call = start_calls[0]
        assert start_call.project_id == "dGVzdF9wcm9qZWN0"
        start_call_inputs = json.loads(start_call.inputs_dump)
        assert start_call_inputs["model"] == "gpt-3.5-turbo"
        assert start_call_inputs["n"] == 2
        assert "choice_index" not in start_call_inputs  # Should not have choice_index

        # Verify end call has correct output with BOTH choices
        end_call = end_calls[0]
        assert end_call.project_id == "dGVzdF9wcm9qZWN0"
        end_call_output = json.loads(end_call.output_dump)
        assert "choices" in end_call_output
        assert len(end_call_output["choices"]) == 2  # Should have both choices

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

        # Verify call IDs match between start and end calls
        assert start_call.id == end_call.id

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
        patch.object(chts.ClickHouseTraceServer, "_insert_call") as mock_insert_call,
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
        assert "weave_call_id" in chunks[0]["_meta"]  # Legacy format for n=1
        assert "weave_call_ids" not in chunks[0]["_meta"]  # Should not have new format

        # Verify content
        assert chunks[1]["choices"][0]["delta"]["content"] == "Hello world!"
        assert chunks[2]["choices"][0]["finish_reason"] == "stop"

        # Verify call tracking - should have 1 start call + 1 end call = 2 total
        assert mock_insert_call.call_count == 2

        # Get all the calls
        call_args = [call[0][0] for call in mock_insert_call.call_args_list]
        start_calls = [
            call for call in call_args if isinstance(call, CallStartCHInsertable)
        ]
        end_calls = [
            call for call in call_args if isinstance(call, CallEndCHInsertable)
        ]

        # Should have 1 start call and 1 end call
        assert len(start_calls) == 1
        assert len(end_calls) == 1

        # Verify start call
        start_call = start_calls[0]
        assert start_call.project_id == "dGVzdF9wcm9qZWN0"
        start_call_inputs = json.loads(start_call.inputs_dump)
        assert start_call_inputs["model"] == "gpt-3.5-turbo"
        assert start_call_inputs["n"] == 1
        assert "choice_index" not in start_call_inputs  # Should not have choice_index

        # Verify end call has correct output
        end_call = end_calls[0]
        assert end_call.project_id == "dGVzdF9wcm9qZWN0"
        end_call_output = json.loads(end_call.output_dump)
        assert "choices" in end_call_output
        assert len(end_call_output["choices"]) == 1
        choice = end_call_output["choices"][0]
        assert choice["index"] == 0
        assert choice["message"]["content"] == "Hello world!"

        # Verify call IDs match between start and end calls
        assert start_call.id == end_call.id

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


@pytest.mark.disable_logging_error_check
def test_call_batch_clears_on_insert_failure():
    """Verify _call_batch is cleared even when insert fails."""
    mock_ch_client = MagicMock()
    mock_ch_client.command.return_value = None
    mock_ch_client.insert.side_effect = _MockInsertError("Connection refused")

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
