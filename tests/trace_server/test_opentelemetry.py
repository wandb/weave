import hashlib
import json
import uuid
from binascii import hexlify
from datetime import datetime
from typing import Any

import pytest
from openinference.semconv.trace import SpanAttributes as OISpanAttr
from opentelemetry.proto.common.v1.common_pb2 import (
    AnyValue,
    InstrumentationScope,
    KeyValue,
)
from opentelemetry.proto.resource.v1.resource_pb2 import Resource
from opentelemetry.proto.trace.v1.trace_pb2 import (
    ResourceSpans,
    ScopeSpans,
    Span,
    TracesData,
)
from opentelemetry.semconv_ai import SpanAttributes as OTSpanAttr

from weave.trace import weave_client
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.constants import MAX_OP_NAME_LENGTH
from weave.trace_server.opentelemetry.attributes import (
    get_span_overrides,
    get_wandb_attributes,
    get_weave_attributes,
    get_weave_inputs,
    get_weave_outputs,
    get_weave_usage,
)
from weave.trace_server.opentelemetry.helpers import (
    AttributePathConflictError,
    capture_parts,
    convert_numeric_keys_to_list,
    expand_attributes,
    flatten_attributes,
    get_attribute,
    shorten_name,
    to_json_serializable,
    try_parse_timestamp,
    unflatten_key_values,
)
from weave.trace_server.opentelemetry.python_spans import (
    Span as PySpan,
)
from weave.trace_server.opentelemetry.python_spans import (
    SpanKind,
    StatusCode,
)
from weave.trace_server.opentelemetry.python_spans import TracesData as PyTracesData


def create_test_span():
    """Create a test OpenTelemetry Span."""
    span = Span()
    span.name = "test_span"
    span.trace_id = uuid.uuid4().bytes
    span.span_id = uuid.uuid4().bytes[:8]
    span.start_time_unix_nano = int(datetime.now().timestamp() * 1_000_000_000)
    span.end_time_unix_nano = (
        span.start_time_unix_nano + 1_000_000_000
    )  # 1 second later
    span.kind = 1  # type: ignore

    # Add some attributes
    kv1 = KeyValue()
    kv1.key = "test.attribute"
    kv1.value.string_value = "test_value"
    span.attributes.append(kv1)

    kv2 = KeyValue()
    kv2.key = "test.number"
    kv2.value.int_value = 42
    span.attributes.append(kv2)

    # Create nested attributes
    kv3 = KeyValue()
    kv3.key = "test.nested.value"
    kv3.value.string_value = "nested_test_value"
    span.attributes.append(kv3)

    # Create an array attribute
    kv4 = KeyValue()
    kv4.key = "test.array"
    array_value = AnyValue()
    value1 = AnyValue()
    value1.string_value = "value1"
    value2 = AnyValue()
    value2.string_value = "value2"
    array_value.array_value.values.extend([value1, value2])
    kv4.value.CopyFrom(array_value)
    span.attributes.append(kv4)

    # Set status
    span.status.code = StatusCode.OK.value  # type: ignore
    span.status.message = "Success"

    return span


def create_test_export_request(project_id="test_project") -> tsi.OTelExportReq:
    """Create a test OTelExportReq with one span."""
    span = create_test_span()

    # Create instrumentation scope
    scope = InstrumentationScope()
    scope.name = "test_instrumentation"
    scope.version = "1.0.0"

    # Create scope spans
    scope_spans = ScopeSpans()
    scope_spans.scope.CopyFrom(scope)
    scope_spans.spans.append(span)

    # Create resource with attributes
    resource = Resource()
    kv = KeyValue()
    kv.key = "service.name"
    kv.value.string_value = "test_service"
    resource.attributes.append(kv)

    # Create resource spans
    resource_spans = ResourceSpans()
    resource_spans.resource.CopyFrom(resource)
    resource_spans.scope_spans.append(scope_spans)

    # Create processed resource spans
    processed_span = tsi.ProcessedResourceSpans(
        entity="test-entity",
        project="test-project",
        run_id=None,
        resource_spans=resource_spans,
    )

    return tsi.OTelExportReq(
        project_id=project_id, processed_spans=[processed_span], wb_user_id=None
    )


def test_otel_export_clickhouse(client: weave_client.WeaveClient):
    """Test the otel_export method."""
    export_req = create_test_export_request()
    project_id = client.project_id
    export_req.project_id = project_id
    export_req.wb_user_id = "abcd123"

    # Export the otel traces
    response = client.server.otel_export(export_req)
    # Verify the response is of the correct type
    assert isinstance(response, tsi.OTelExportRes)

    # Query the calls
    res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=project_id,
        )
    )
    # Verify that the start and end calls were merged into a single call
    assert len(res.calls) == 1

    call = res.calls[0]
    export_span = export_req.processed_spans[0].resource_spans.scope_spans[0].spans[0]
    decoded_trace = hexlify(export_span.trace_id).decode("ascii")
    decoded_span = hexlify(export_span.span_id).decode("ascii")

    assert call.id == decoded_span
    assert call.trace_id == decoded_trace

    for kv in export_span.attributes:
        key = kv.key
        value = kv.value
        if value.HasField("string_value"):
            assert get_attribute(call.attributes, key) == value.string_value
        elif value.HasField("int_value"):
            assert get_attribute(call.attributes, key) == value.int_value
        elif value.HasField("double_value"):
            assert get_attribute(call.attributes, key) == value.double_value
        elif value.HasField("bool_value"):
            assert get_attribute(call.attributes, key) == value.bool_value
        elif value.HasField("array_value"):
            # Handle array values
            array_values = [v.string_value for v in value.array_value.values]
            assert get_attribute(call.attributes, key) == array_values

    # Verify call deletion using client provided ID works
    client.server.calls_delete(
        tsi.CallsDeleteReq(
            project_id=project_id, call_ids=[decoded_span], wb_user_id=None
        )
    )

    res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=project_id,
        )
    )

    # Verify that the call was deleted
    assert len(res.calls) == 0


def test_otel_export_multiple_processed_spans(client: weave_client.WeaveClient):
    """Test that exporting multiple ProcessedResourceSpans produces correct calls.

    Regression test: the object creation code was previously nested inside the
    per-processed-span loop, causing it to re-process already-resolved calls on
    the 2nd+ iteration and corrupt their op_name with a mangled ref URI.
    """
    project_id = client.project_id

    # Build two separate ProcessedResourceSpans, each with one span
    processed_spans = []
    expected_span_ids = []
    for i in range(2):
        span = create_test_span()
        span.name = f"span_{i}"
        expected_span_ids.append(hexlify(span.span_id).decode("ascii"))

        scope = InstrumentationScope()
        scope.name = "test_instrumentation"
        scope.version = "1.0.0"

        scope_spans = ScopeSpans()
        scope_spans.scope.CopyFrom(scope)
        scope_spans.spans.append(span)

        resource = Resource()
        kv = KeyValue()
        kv.key = "service.name"
        kv.value.string_value = "test_service"
        resource.attributes.append(kv)

        resource_spans = ResourceSpans()
        resource_spans.resource.CopyFrom(resource)
        resource_spans.scope_spans.append(scope_spans)

        processed_spans.append(
            tsi.ProcessedResourceSpans(
                entity="test-entity",
                project="test-project",
                run_id=f"run_{i}" if i > 0 else None,
                resource_spans=resource_spans,
            )
        )

    export_req = tsi.OTelExportReq(
        project_id=project_id,
        processed_spans=processed_spans,
        wb_user_id="abcd123",
    )

    response = client.server.otel_export(export_req)
    assert isinstance(response, tsi.OTelExportRes)
    assert response.partial_success is None

    # Both spans should be ingested
    res = client.server.calls_query(tsi.CallsQueryReq(project_id=project_id))
    assert len(res.calls) == 2

    ingested_ids = {c.id for c in res.calls}
    for sid in expected_span_ids:
        assert sid in ingested_ids

    # In clickhouse, every call's op_name must be a valid ref URI, not a
    # mangled/re-sanitized name.
    for call in res.calls:
        assert call.op_name.startswith("weave:///"), (
            f"op_name should be a ref URI, got: {call.op_name}"
        )


def test_otel_export_with_turn_and_thread(client: weave_client.WeaveClient):
    """Test the otel_export method with turn and thread attributes."""
    # Create a test export request
    export_req = create_test_export_request()
    project_id = client.project_id
    export_req.project_id = project_id
    export_req.wb_user_id = "abcd123"

    # Add turn and thread attributes to the span
    # Materialize processed_spans to avoid iterator exhaustion
    test_thread_id = str(uuid.uuid4())
    processed_spans_list = export_req.processed_spans
    span = processed_spans_list[0].resource_spans.scope_spans[0].spans[0]

    kv_is_turn = KeyValue()
    kv_is_turn.key = "wandb.is_turn"
    kv_is_turn.value.bool_value = True
    span.attributes.append(kv_is_turn)

    kv_thread = KeyValue()
    kv_thread.key = "wandb.thread_id"
    kv_thread.value.string_value = test_thread_id
    span.attributes.append(kv_thread)

    export_req.processed_spans = processed_spans_list

    # Export the otel traces
    response = client.server.otel_export(export_req)
    assert isinstance(response, tsi.OTelExportRes)

    # Query the calls
    res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=project_id,
        )
    )
    assert len(res.calls) == 1

    call = res.calls[0]

    # Verify turn_id equals call.id when is_turn is True
    assert hasattr(call, "turn_id")
    assert call.turn_id == call.id

    # Verify thread_id is set correctly
    assert hasattr(call, "thread_id")
    assert call.thread_id == test_thread_id

    # Clean up
    client.server.calls_delete(
        tsi.CallsDeleteReq(project_id=project_id, call_ids=[call.id], wb_user_id=None)
    )


def test_otel_export_with_turn_no_thread(client: weave_client.WeaveClient):
    """Test the otel_export method with is_turn=True but no thread_id."""
    # Create a test export request
    export_req = create_test_export_request()
    project_id = client.project_id
    export_req.project_id = project_id
    export_req.wb_user_id = "abcd123"

    # Add only is_turn attribute (no thread_id)
    # Materialize processed_spans to avoid iterator exhaustion
    processed_spans_list = export_req.processed_spans
    span = processed_spans_list[0].resource_spans.scope_spans[0].spans[0]

    kv_is_turn = KeyValue()
    kv_is_turn.key = "wandb.is_turn"
    kv_is_turn.value.bool_value = True
    span.attributes.append(kv_is_turn)

    export_req.processed_spans = processed_spans_list

    # Export the otel traces
    response = client.server.otel_export(export_req)
    assert isinstance(response, tsi.OTelExportRes)

    # Query the calls
    res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=project_id,
        )
    )
    assert len(res.calls) == 1

    call = res.calls[0]

    # Verify turn_id is NOT set when is_turn is True but thread_id is missing
    assert hasattr(call, "turn_id")
    assert call.turn_id is None

    # Verify thread_id is not set
    assert hasattr(call, "thread_id")
    assert call.thread_id is None

    # Clean up
    client.server.calls_delete(
        tsi.CallsDeleteReq(project_id=project_id, call_ids=[call.id], wb_user_id=None)
    )


def test_span_from_proto() -> None:
    """Test converting a protobuf Span to a Python Span."""
    pb_span = create_test_span()
    py_span = PySpan.from_proto(pb_span)

    assert py_span.name == pb_span.name
    assert py_span.trace_id == pb_span.trace_id.hex()
    assert py_span.span_id == pb_span.span_id.hex()
    assert py_span.start_time_unix_nano == pb_span.start_time_unix_nano
    assert py_span.end_time_unix_nano == pb_span.end_time_unix_nano
    assert py_span.kind == SpanKind.INTERNAL
    assert py_span.status.code == StatusCode.OK
    assert py_span.status.message == pb_span.status.message

    # Verify attributes were correctly converted
    assert get_attribute(py_span.attributes, "test.attribute") == "test_value"
    assert get_attribute(py_span.attributes, "test.number") == 42
    assert get_attribute(py_span.attributes, "test.nested.value") == "nested_test_value"
    array_value = get_attribute(py_span.attributes, "test.array")
    assert isinstance(array_value, list)
    assert len(array_value) == 2
    assert array_value[0] == "value1"
    assert array_value[1] == "value2"


def test_span_from_proto_parent_id_normalization() -> None:
    """Test that empty and all-zero parent_span_id values normalize to None."""
    # All-zero parent_span_id is the OTel invalid-id sentinel; must mean no parent.
    pb_span = create_test_span()
    pb_span.parent_span_id = b"\x00" * 8
    assert PySpan.from_proto(pb_span).parent_id is None, (
        "all-zero parent_span_id should yield parent_id=None"
    )

    pb_span = create_test_span()
    pb_span.parent_span_id = b""
    assert PySpan.from_proto(pb_span).parent_id is None, (
        "empty parent_span_id should yield parent_id=None"
    )

    pb_span = create_test_span()
    pb_span.parent_span_id = bytes.fromhex("0123456789abcdef")
    assert PySpan.from_proto(pb_span).parent_id == "0123456789abcdef", (
        "real parent_span_id should hex-encode to parent_id"
    )


def test_span_to_call() -> None:
    """Test converting a Python Span to Weave Calls."""
    pb_span = create_test_span()
    py_span = PySpan.from_proto(pb_span)

    start_call, _ = py_span.to_call("test_project")

    # Verify start call
    assert isinstance(start_call, tsi.StartedCallSchemaForInsert)
    assert start_call.project_id == "test_project"
    assert start_call.id == py_span.span_id
    assert (
        start_call.op_name == py_span.name
    )  # This should be using the shortened name if necessary
    assert start_call.trace_id == py_span.trace_id
    assert start_call.started_at == py_span.start_time


def test_span_to_call_long_name() -> None:
    """Test that span names are properly shortened when too long."""
    # Create a test span with a very long name
    pb_span = create_test_span()
    long_name = "a" * (MAX_OP_NAME_LENGTH + 10)
    pb_span.name = long_name

    py_span = PySpan.from_proto(pb_span)
    start_call, end_call = py_span.to_call("test_project")

    # Verify that the op_name was shortened
    identifier = hashlib.sha256(long_name.encode("utf-8")).hexdigest()[:4]
    shortened_name = shorten_name(
        long_name,
        MAX_OP_NAME_LENGTH,
        abbrv=f":{identifier}",
        use_delimiter_in_abbr=False,
    )
    assert start_call.op_name == shortened_name
    assert len(start_call.op_name) <= MAX_OP_NAME_LENGTH

    # Verify attributes in start call
    assert "test" in start_call.attributes
    assert "attribute" in start_call.attributes["test"]
    assert start_call.attributes["test"]["attribute"] == "test_value"
    assert start_call.attributes["test"]["number"] == 42
    assert "nested" in start_call.attributes["test"]
    assert start_call.attributes["test"]["nested"]["value"] == "nested_test_value"
    assert "array" in start_call.attributes["test"]
    assert start_call.attributes["test"]["array"] == ["value1", "value2"]

    # Verify otel_dump is included in the call (otel_span is now in otel_dump)
    assert start_call.otel_dump is not None
    assert start_call.otel_dump["name"] == long_name
    assert start_call.otel_dump["context"]["trace_id"] == py_span.trace_id
    assert start_call.otel_dump["context"]["span_id"] == py_span.span_id

    # Verify end call
    assert isinstance(end_call, tsi.EndedCallSchemaForInsert)
    assert end_call.project_id == "test_project"
    assert end_call.id == py_span.span_id
    assert end_call.ended_at == py_span.end_time
    assert end_call.exception is None


def test_span_to_call_with_turn_and_thread() -> None:
    """Test that turn_id equals thread_id when is_turn is True."""
    # Create a test span with turn and thread attributes
    pb_span = create_test_span()
    test_thread_id = str(uuid.uuid4())

    # Add wandb.is_turn and wandb.thread_id attributes
    kv_is_turn = KeyValue()
    kv_is_turn.key = "wandb.is_turn"
    kv_is_turn.value.bool_value = True
    pb_span.attributes.append(kv_is_turn)

    kv_thread = KeyValue()
    kv_thread.key = "wandb.thread_id"
    kv_thread.value.string_value = test_thread_id
    pb_span.attributes.append(kv_thread)

    py_span = PySpan.from_proto(pb_span)
    start_call, end_call = py_span.to_call("test_project")

    # Verify turn_id equals call.id (span_id) when is_turn is True
    assert start_call.turn_id == py_span.span_id
    # Verify thread_id is passed through
    assert start_call.thread_id == test_thread_id

    # Test with is_turn = False
    pb_span_false = create_test_span()
    kv_is_turn_false = KeyValue()
    kv_is_turn_false.key = "wandb.is_turn"
    kv_is_turn_false.value.bool_value = False
    pb_span_false.attributes.append(kv_is_turn_false)

    kv_thread_false = KeyValue()
    kv_thread_false.key = "wandb.thread_id"
    kv_thread_false.value.string_value = test_thread_id
    pb_span_false.attributes.append(kv_thread_false)

    py_span_false = PySpan.from_proto(pb_span_false)
    start_call_false, _ = py_span_false.to_call("test_project")

    # Verify turn_id is None when is_turn is False
    assert start_call_false.turn_id is None
    assert start_call_false.thread_id == test_thread_id

    # Test without is_turn (should default to None)
    pb_span_no_turn = create_test_span()
    kv_thread_only = KeyValue()
    kv_thread_only.key = "wandb.thread_id"
    kv_thread_only.value.string_value = test_thread_id
    pb_span_no_turn.attributes.append(kv_thread_only)

    py_span_no_turn = PySpan.from_proto(pb_span_no_turn)
    start_call_no_turn, _ = py_span_no_turn.to_call("test_project")

    # Verify turn_id is None when is_turn is not present
    assert start_call_no_turn.turn_id is None
    assert start_call_no_turn.thread_id == test_thread_id

    # Test with is_turn = True but no thread_id
    pb_span_turn_no_thread = create_test_span()
    kv_is_turn_only = KeyValue()
    kv_is_turn_only.key = "wandb.is_turn"
    kv_is_turn_only.value.bool_value = True
    pb_span_turn_no_thread.attributes.append(kv_is_turn_only)

    py_span_turn_no_thread = PySpan.from_proto(pb_span_turn_no_thread)
    start_call_turn_no_thread, _ = py_span_turn_no_thread.to_call("test_project")

    # Verify turn_id is None when is_turn is True but thread_id is missing
    assert start_call_turn_no_thread.turn_id is None
    assert start_call_turn_no_thread.thread_id is None

    # gen_ai.conversation.id sets thread_id and (being truthy) turn_id.
    pb_span_conv = create_test_span()
    kv_conv = KeyValue()
    kv_conv.key = "gen_ai.conversation.id"
    kv_conv.value.string_value = "conv-xyz"
    pb_span_conv.attributes.append(kv_conv)

    py_span_conv = PySpan.from_proto(pb_span_conv)
    start_call_conv, _ = py_span_conv.to_call("test_project")
    assert start_call_conv.thread_id == "conv-xyz"
    assert start_call_conv.turn_id == py_span_conv.span_id


def test_span_to_call_with_cache_tokens() -> None:
    """Test that cache token usage attributes flow through to_call summary."""
    pb_span = create_test_span()

    # Add cache token usage attributes
    kv_cache_creation = KeyValue()
    kv_cache_creation.key = "gen_ai.usage.cache_creation.input_tokens"
    kv_cache_creation.value.int_value = 500
    pb_span.attributes.append(kv_cache_creation)

    kv_cache_read = KeyValue()
    kv_cache_read.key = "gen_ai.usage.cache_read.input_tokens"
    kv_cache_read.value.int_value = 200
    pb_span.attributes.append(kv_cache_read)

    kv_input = KeyValue()
    kv_input.key = "gen_ai.usage.input_tokens"
    kv_input.value.int_value = 100
    pb_span.attributes.append(kv_input)

    kv_output = KeyValue()
    kv_output.key = "gen_ai.usage.output_tokens"
    kv_output.value.int_value = 50
    pb_span.attributes.append(kv_output)

    py_span = PySpan.from_proto(pb_span)
    _, end_call = py_span.to_call("test_project")

    # Usage is keyed by model name or "usage" when no model is set
    usage = end_call.summary["usage"]["usage"]  # type: ignore
    assert usage["cache_creation_input_tokens"] == 500
    assert usage["cache_read_input_tokens"] == 200
    assert usage["input_tokens"] == 100
    assert usage["output_tokens"] == 50


def test_traces_data_from_proto() -> None:
    """Test converting protobuf TracesData to Python TracesData."""
    export_req = create_test_export_request()
    resource_spans_list = [ps.resource_spans for ps in export_req.processed_spans]
    traces_data = PyTracesData.from_proto(
        TracesData(resource_spans=resource_spans_list)
    )

    assert len(traces_data.resource_spans) == 1
    resource_spans = traces_data.resource_spans[0]
    assert len(resource_spans.scope_spans) == 1
    scope_spans = resource_spans.scope_spans[0]
    assert len(scope_spans.spans) == 1
    span = scope_spans.spans[0]

    assert span.name == "test_span"
    assert span.kind == SpanKind.INTERNAL


def test_to_json_serializable() -> None:
    """to_json_serializable handles primitives, containers, and stdlib types."""
    from dataclasses import dataclass
    from datetime import date, time, timedelta
    from decimal import Decimal

    # Primitives, lists/tuples, dicts, nested structures, datetime, enums.
    assert to_json_serializable("string") == "string"
    assert to_json_serializable(42) == 42
    assert to_json_serializable(3.14) == 3.14
    assert to_json_serializable(True) == True
    assert to_json_serializable(None) is None
    assert to_json_serializable(["a", 1, True]) == ["a", 1, True]
    assert to_json_serializable(("a", 1, True)) == ["a", 1, True]
    assert to_json_serializable({"a": 1, "b": "two"}) == {"a": 1, "b": "two"}
    nested = {"a": [1, 2, {"b": "c"}], "d": {"e": [3, 4]}}
    assert to_json_serializable(nested) == nested
    assert to_json_serializable(datetime(2023, 1, 1, 12, 0, 0)) == "2023-01-01T12:00:00"
    assert to_json_serializable(SpanKind.INTERNAL) == 1

    # Special floats serialize to their string form.
    assert to_json_serializable(float("nan")) == "nan"
    assert to_json_serializable(float("inf")) == "inf"
    assert to_json_serializable(float("-inf")) == "-inf"

    # date / time.
    assert to_json_serializable(date(2023, 1, 1)) == "2023-01-01"
    assert to_json_serializable(time(12, 30, 45)) == "12:30:45"

    # timedelta -> total seconds.
    assert to_json_serializable(timedelta(days=1)) == 86400.0
    assert (
        to_json_serializable(timedelta(days=1, hours=2, minutes=30, seconds=15))
        == (1 * 24 * 60 * 60) + (2 * 60 * 60) + (30 * 60) + 15
    )

    # UUID -> str.
    assert (
        to_json_serializable(uuid.UUID("12345678-1234-5678-1234-567812345678"))
        == "12345678-1234-5678-1234-567812345678"
    )

    # Decimal -> float.
    assert to_json_serializable(Decimal("10.5")) == 10.5
    assert (
        to_json_serializable(Decimal("3.14159265358979323846"))
        == 3.14159265358979323846
    )
    assert to_json_serializable(Decimal("0")) == 0.0

    # set / frozenset -> unordered list.
    set_result = to_json_serializable({1, 2, 3, "test"})
    assert isinstance(set_result, list)
    assert len(set_result) == 4
    assert {1, 2, 3, "test"} == set(set_result)
    frozen_result = to_json_serializable(frozenset([4, 5, 6, "frozen"]))
    assert isinstance(frozen_result, list)
    assert len(frozen_result) == 4
    assert {4, 5, 6, "frozen"} == set(frozen_result)

    # complex -> {real, imag}.
    assert to_json_serializable(complex(3, 4)) == {"real": 3.0, "imag": 4.0}
    assert to_json_serializable(complex(1, -2)) == {"real": 1.0, "imag": -2.0}

    # bytes / bytearray -> base64.
    assert to_json_serializable(b"hello world") == "aGVsbG8gd29ybGQ="
    assert to_json_serializable(bytearray(b"hello world")) == "aGVsbG8gd29ybGQ="

    # dataclass -> dict (including nested dataclasses).
    @dataclass
    class Person:
        name: str
        age: int

    assert to_json_serializable(Person(name="John", age=30)) == {
        "name": "John",
        "age": 30,
    }

    @dataclass
    class Department:
        name: str
        head: Person

    assert to_json_serializable(
        Department(name="Engineering", head=Person(name="Jane", age=35))
    ) == {"name": "Engineering", "head": {"name": "Jane", "age": 35}}


def test_unflatten_key_values() -> None:
    """Test unflattening key-value pairs into nested structure."""
    kv1 = KeyValue(key="a.b.c", value=AnyValue(string_value="value1"))
    kv2 = KeyValue(key="a.b.d", value=AnyValue(int_value=42))
    kv3 = KeyValue(key="a.e", value=AnyValue(bool_value=True))
    kv4 = KeyValue(key="f.0", value=AnyValue(string_value="item0"))
    kv5 = KeyValue(key="f.1", value=AnyValue(string_value="item1"))

    result = unflatten_key_values([kv1, kv2, kv3, kv4, kv5])

    assert result == {
        "a": {"b": {"c": "value1", "d": 42}, "e": True},
        "f": {"0": "item0", "1": "item1"},
    }


def test_get_attribute() -> None:
    """Test getting attributes from nested structures."""
    nested = {"a": {"b": {"c": "value1"}}, "d": [1, 2, 3]}

    assert get_attribute(nested, "a.b.c") == "value1"
    assert get_attribute(nested, "a.b") == {"c": "value1"}
    assert get_attribute(nested, "d") == [1, 2, 3]
    assert get_attribute(nested, "d.0") == 1
    assert get_attribute(nested, "nonexistent") is None


def test_expand_and_flatten_attributes() -> None:
    """expand_attributes nests, convert_numeric_keys_to_list lists, flatten reverses."""
    flat_attrs = [
        ("a.b.c", "value1"),
        ("a.b.d", 42),
        ("a.e", True),
        ("f.0", "item0"),
        ("f.1", "item1"),
    ]

    expanded = expand_attributes(flat_attrs)
    assert expanded == {
        "a": {"b": {"c": "value1", "d": 42}, "e": True},
        "f": {"0": "item0", "1": "item1"},
    }

    listed = convert_numeric_keys_to_list(expand_attributes(flat_attrs))
    assert listed == {
        "a": {"b": {"c": "value1", "d": 42}, "e": True},
        "f": ["item0", "item1"],
    }

    assert flatten_attributes(listed) == {
        "a.b.c": "value1",
        "a.b.d": 42,
        "a.e": True,
        "f.0": "item0",
        "f.1": "item1",
    }


def test_expand_attributes_parent_child_primitive_conflict_raises() -> None:
    """A parent primitive and a nested subkey for the same path conflict either order."""
    # parent primitive set first, then a nested subkey.
    try:
        expand_attributes([("gen_ai.prompt", True), ("gen_ai.prompt.content", "Hello")])
        raise AssertionError("Expected AttributePathConflictError")
    except AttributePathConflictError as e:
        msg = str(e)
        assert "gen_ai.prompt" in msg
        assert "content" in msg
        assert "Do not" in msg or "Invalid attribute structure" in msg

    # nested subkey set first, then the parent primitive.
    try:
        expand_attributes([("gen_ai.prompt.content", "Hello"), ("gen_ai.prompt", True)])
        raise AssertionError("Expected AttributePathConflictError")
    except AttributePathConflictError as e:
        msg = str(e)
        assert "gen_ai.prompt" in msg
        assert "Do not" in msg or "Invalid attribute structure" in msg


def test_expand_attributes_json_string_and_dotted_subkeys_merge() -> None:
    """A JSON-string blob and dotted subkeys for the same path merge across orderings."""
    # JSON string first, then a matching dotted subkey -> single merged element.
    result = convert_numeric_keys_to_list(
        expand_attributes(
            [
                ("gen_ai.completion", '[{"role": "assistant", "content": "hello"}]'),
                ("gen_ai.completion.0.role", "assistant"),
            ]
        )
    )
    assert result["gen_ai"]["completion"] == [{"role": "assistant", "content": "hello"}]

    # Dotted subkeys first, then JSON string (reversed ordering) -> same merge.
    result = convert_numeric_keys_to_list(
        expand_attributes(
            [
                ("gen_ai.completion.0.role", "assistant"),
                ("gen_ai.completion.0.content", "hello"),
                ("gen_ai.completion", '[{"role": "assistant", "content": "hello"}]'),
            ]
        )
    )
    assert result["gen_ai"]["completion"] == [{"role": "assistant", "content": "hello"}]

    # Dotted subkeys arriving after JSON string win at the leaves.
    result = convert_numeric_keys_to_list(
        expand_attributes(
            [
                ("gen_ai.completion", '[{"role": "assistant", "content": "original"}]'),
                ("gen_ai.completion.0.content", "overridden"),
            ]
        )
    )
    assert result["gen_ai"]["completion"] == [
        {"role": "assistant", "content": "overridden"}
    ]

    # JSON string arriving after dotted subkeys merges in extra fields.
    result = convert_numeric_keys_to_list(
        expand_attributes(
            [
                ("gen_ai.completion.0.role", "assistant"),
                (
                    "gen_ai.completion",
                    '[{"role": "assistant", "content": "hello", "extra": true}]',
                ),
            ]
        )
    )
    assert result["gen_ai"]["completion"] == [
        {"role": "assistant", "content": "hello", "extra": True}
    ]

    # A nested-list element present only in dotted attrs must survive a later JSON blob:
    # top-level completion lists are index-merged, but _deep_merge clobbers nested lists,
    # so a second tool_call sent only via dotted keys must not vanish.
    result = convert_numeric_keys_to_list(
        expand_attributes(
            [
                ("gen_ai.completion.0.tool_calls.0.id", "call_0"),
                ("gen_ai.completion.0.tool_calls.1.id", "call_1"),
                ("gen_ai.completion.0.tool_calls.1.type", "function"),
                (
                    "gen_ai.completion",
                    '[{"role": "assistant", "tool_calls": [{"id": "call_0", "type": "function"}]}]',
                ),
            ]
        )
    )
    tool_calls = result["gen_ai"]["completion"][0]["tool_calls"]
    assert [tc["id"] for tc in tool_calls] == ["call_0", "call_1"]


def create_attributes(d: dict[str, Any]):
    return expand_attributes(d.items())


def test_openinference_attributes_extraction() -> None:
    """Test extracting attributes from OpenInference attributes."""
    attributes = create_attributes(
        {
            OISpanAttr.LLM_SYSTEM: "This is a system prompt",
            OISpanAttr.LLM_PROVIDER: "test-provider",
            OISpanAttr.LLM_MODEL_NAME: "test-model",
            OISpanAttr.OPENINFERENCE_SPAN_KIND: "llm",
            OISpanAttr.LLM_INVOCATION_PARAMETERS: json.dumps(
                {"temperature": 0.7, "max_tokens": 100}
            ),
        }
    )

    extracted = get_weave_attributes(attributes)
    assert extracted["system"] == "This is a system prompt"
    assert extracted["provider"] == "test-provider"
    assert extracted["model"] == "test-model"
    assert extracted["kind"] == "llm"
    assert extracted["model_parameters"]["max_tokens"] == 100
    assert extracted["model_parameters"]["temperature"] == 0.7


def test_opentelemetry_attributes_extraction() -> None:
    """Test extracting attributes from OpenTelemetry attributes."""
    attributes = create_attributes(
        {
            OTSpanAttr.LLM_SYSTEM: "You are a helpful assistant",
            OTSpanAttr.LLM_REQUEST_MAX_TOKENS: 150,
            OTSpanAttr.TRACELOOP_SPAN_KIND: "llm",
            OTSpanAttr.LLM_RESPONSE_MODEL: "gpt-4",
        }
    )

    extracted = get_weave_attributes(attributes)
    assert extracted["system"] == "You are a helpful assistant"
    assert extracted["model_parameters"]["max_tokens"] == 150
    assert extracted["kind"] == "llm"
    assert extracted["model"] == "gpt-4"


def test_wandb_attributes_extraction() -> None:
    """Test extracting wandb-specific attributes (flat, empty, partial, nested)."""
    extracted = get_wandb_attributes(
        create_attributes({"wandb.display_name": "My Custom Display Name"})
    )
    assert extracted["display_name"] == "My Custom Display Name"

    assert get_wandb_attributes(create_attributes({})) == {}

    extracted = get_wandb_attributes(
        create_attributes({"wandb.display_name": "Only Display Name"})
    )
    assert extracted["display_name"] == "Only Display Name"
    assert "project_id" not in extracted

    extracted = get_wandb_attributes(
        create_attributes({"wandb": {"display_name": "Nested Display Name"}})
    )
    assert extracted["display_name"] == "Nested Display Name"


def test_wandb_turn_and_thread_attributes() -> None:
    """is_turn is only kept when truthy; thread_id is always passed through."""
    test_thread_id = str(uuid.uuid4())

    extracted = get_wandb_attributes(
        create_attributes({"wandb.is_turn": True, "wandb.thread_id": test_thread_id})
    )
    assert extracted["is_turn"] is True
    assert extracted["thread_id"] == test_thread_id

    extracted_false = get_wandb_attributes(
        create_attributes({"wandb.is_turn": False, "wandb.thread_id": test_thread_id})
    )
    assert "is_turn" not in extracted_false.keys()
    assert extracted_false["thread_id"] == test_thread_id

    extracted_thread_only = get_wandb_attributes(
        create_attributes({"wandb.thread_id": test_thread_id})
    )
    assert "is_turn" not in extracted_thread_only
    assert extracted_thread_only["thread_id"] == test_thread_id

    extracted_turn_only = get_wandb_attributes(
        create_attributes({"wandb.is_turn": True})
    )
    assert extracted_turn_only["is_turn"] is True
    assert "thread_id" not in extracted_turn_only


@pytest.mark.skip(reason="wb_run_id extraction not yet implemented")
def test_wandb_wb_run_id_extraction() -> None:
    """Test extracting wb_run_id from both wb_run_id and wandb.wb_run_id attributes."""
    extracted_top_level = get_wandb_attributes(
        create_attributes({"wb_run_id": "run_top_123"})
    )
    assert extracted_top_level["wb_run_id"] == "run_top_123"

    extracted_namespaced = get_wandb_attributes(
        create_attributes({"wandb.wb_run_id": "run_ns_456"})
    )
    assert extracted_namespaced["wb_run_id"] == "run_ns_456"

    # Both present: top-level takes precedence.
    extracted_both = get_wandb_attributes(
        create_attributes(
            {"wb_run_id": "preferred_top", "wandb.wb_run_id": "fallback_ns"}
        )
    )
    assert extracted_both["wb_run_id"] == "preferred_top"


def test_openinference_inputs_extraction() -> None:
    """get_weave_inputs handles OpenInference text and JSON input values."""
    inputs = get_weave_inputs(
        [],
        create_attributes(
            {
                OISpanAttr.INPUT_VALUE: "What is machine learning?",
                OISpanAttr.INPUT_MIME_TYPE: "text/plain",
            }
        ),
    )
    assert inputs == {"input.value": "What is machine learning?"}

    json_input = json.dumps(
        {
            "messages": [
                {"role": "system", "content": "You are an assistant"},
                {"role": "user", "content": "What is machine learning?"},
            ]
        }
    )
    inputs = get_weave_inputs(
        [],
        create_attributes(
            {
                OISpanAttr.INPUT_VALUE: json_input,
                OISpanAttr.INPUT_MIME_TYPE: "application/json",
            }
        ),
    )
    assert inputs == {
        "input.value": {
            "messages": [
                {"role": "system", "content": "You are an assistant"},
                {"role": "user", "content": "What is machine learning?"},
            ]
        },
    }


def test_openinference_outputs_extraction() -> None:
    """get_weave_outputs handles OpenInference text and JSON output values."""
    outputs = get_weave_outputs(
        [],
        create_attributes(
            {
                OISpanAttr.OUTPUT_VALUE: "Machine learning is a field of AI...",
                OISpanAttr.OUTPUT_MIME_TYPE: "text/plain",
            }
        ),
    )
    assert outputs == {"output.value": "Machine learning is a field of AI..."}

    json_output = json.dumps(
        {
            "response": {
                "role": "assistant",
                "content": "Machine learning is a field of AI...",
            }
        }
    )
    outputs = get_weave_outputs(
        [],
        create_attributes(
            {
                OISpanAttr.OUTPUT_VALUE: json_output,
                OISpanAttr.OUTPUT_MIME_TYPE: "application/json",
            }
        ),
    )
    assert outputs == {
        "output.value": {
            "response": {
                "role": "assistant",
                "content": "Machine learning is a field of AI...",
            }
        },
    }


def test_opentelemetry_inputs_extraction() -> None:
    """get_weave_inputs expands OpenTelemetry prompts into a message list."""
    attributes = create_attributes(
        {
            OTSpanAttr.LLM_PROMPTS: {
                "0": {"role": "user", "content": "Tell me about quantum computing"}
            }
        }
    )
    inputs = get_weave_inputs([], attributes)
    assert inputs == {
        "gen_ai.prompt": [
            {"role": "user", "content": "Tell me about quantum computing"}
        ]
    }


def test_opentelemetry_outputs_extraction() -> None:
    """get_weave_outputs expands OpenTelemetry completions into a message list."""
    attributes = create_attributes(
        {
            OTSpanAttr.LLM_COMPLETIONS: {
                "0": {
                    "role": "assistant",
                    "content": "Quantum computing uses quantum mechanics...",
                }
            }
        }
    )
    outputs = get_weave_outputs([], attributes)
    assert outputs == {
        "gen_ai.completion": [
            {
                "role": "assistant",
                "content": "Quantum computing uses quantum mechanics...",
            }
        ]
    }


def test_usage_token_extraction() -> None:
    """get_weave_usage parses token counts across OpenInference, OTel, gen_ai, and cache."""
    # OpenInference token counts.
    usage = get_weave_usage(
        create_attributes(
            {
                OISpanAttr.LLM_TOKEN_COUNT_PROMPT: 10,
                OISpanAttr.LLM_TOKEN_COUNT_COMPLETION: 20,
                OISpanAttr.LLM_TOKEN_COUNT_TOTAL: 30,
            }
        )
    )
    assert usage.get("prompt_tokens") == 10
    assert usage.get("completion_tokens") == 20
    assert usage.get("total_tokens") == 30

    # OpenTelemetry token counts.
    usage = (
        get_weave_usage(
            create_attributes(
                {
                    OTSpanAttr.LLM_USAGE_PROMPT_TOKENS: 15,
                    OTSpanAttr.LLM_USAGE_COMPLETION_TOKENS: 25,
                    OTSpanAttr.LLM_USAGE_TOTAL_TOKENS: 40,
                }
            )
        )
        or {}
    )
    assert usage.get("prompt_tokens") == 15
    assert usage.get("completion_tokens") == 25
    assert usage.get("total_tokens") == 40

    # gen_ai input/output tokens: total is computed when not provided.
    usage = (
        get_weave_usage(
            create_attributes(
                {"gen_ai.usage.input_tokens": 10, "gen_ai.usage.output_tokens": 20}
            )
        )
        or {}
    )
    assert usage.get("input_tokens") == 10
    assert usage.get("output_tokens") == 20
    assert usage.get("total_tokens") == 30

    # An explicit total_tokens takes precedence over the computed value.
    usage = (
        get_weave_usage(
            create_attributes(
                {
                    "gen_ai.usage.input_tokens": 10,
                    "gen_ai.usage.output_tokens": 20,
                    "llm.usage.total_tokens": 35,
                }
            )
        )
        or {}
    )
    assert usage.get("input_tokens") == 10
    assert usage.get("output_tokens") == 20
    assert usage.get("total_tokens") == 35

    # cache_creation / cache_read token usage rolls into the total.
    usage = (
        get_weave_usage(
            create_attributes(
                {
                    "gen_ai.usage.input_tokens": 100,
                    "gen_ai.usage.output_tokens": 50,
                    "gen_ai.usage.cache_creation.input_tokens": 80,
                    "gen_ai.usage.cache_read.input_tokens": 20,
                }
            )
        )
        or {}
    )
    assert usage.get("input_tokens") == 100
    assert usage.get("output_tokens") == 50
    assert usage.get("cache_creation_input_tokens") == 80
    assert usage.get("cache_read_input_tokens") == 20
    assert usage.get("total_tokens") == 150


def test_genai_semconv_attribute_priority_and_fallback() -> None:
    """get_weave_attributes prefers new gen_ai semconv keys, falling back to legacy."""
    # gen_ai.system_instructions takes priority over gen_ai.system.
    extracted = get_weave_attributes(
        create_attributes(
            {
                "gen_ai.system_instructions": "You are a new-style assistant",
                "gen_ai.system": "You are a legacy assistant",
            }
        )
    )
    assert extracted["system"] == "You are a new-style assistant"
    extracted_legacy = get_weave_attributes(
        create_attributes({"gen_ai.system": "You are a legacy assistant"})
    )
    assert extracted_legacy["system"] == "You are a legacy assistant"

    # gen_ai.response.model takes priority over gen_ai.request.model (fallback).
    extracted = get_weave_attributes(
        create_attributes(
            {
                "gen_ai.response.model": "gpt-4-actual",
                "gen_ai.request.model": "gpt-4-requested",
            }
        )
    )
    assert extracted["model"] == "gpt-4-actual"
    extracted_request = get_weave_attributes(
        create_attributes({"gen_ai.request.model": "gpt-4-requested"})
    )
    assert extracted_request["model"] == "gpt-4-requested"

    # gen_ai.provider.name takes priority over llm.provider (fallback).
    extracted = get_weave_attributes(
        create_attributes(
            {"gen_ai.provider.name": "anthropic", "llm.provider": "legacy-provider"}
        )
    )
    assert extracted["provider"] == "anthropic"
    extracted_legacy = get_weave_attributes(
        create_attributes({"llm.provider": "legacy-provider"})
    )
    assert extracted_legacy["provider"] == "legacy-provider"


def test_genai_semconv_scalar_attribute_extraction() -> None:
    """get_weave_attributes maps single gen_ai semconv keys to their weave fields."""
    extracted = get_weave_attributes(
        create_attributes({"gen_ai.operation.name": "chat"})
    )
    assert extracted["operation_name"] == "chat"

    extracted = get_weave_attributes(
        create_attributes({"gen_ai.response.id": "chatcmpl-abc123"})
    )
    assert extracted["response_id"] == "chatcmpl-abc123"

    extracted = get_weave_attributes(
        create_attributes({"gen_ai.response.finish_reasons": ["stop", "length"]})
    )
    assert extracted["finish_reasons"] == ["stop", "length"]

    extracted = get_weave_attributes(
        create_attributes(
            {"gen_ai.agent.name": "my-agent", "gen_ai.agent.id": "agent-42"}
        )
    )
    assert extracted["agent_name"] == "my-agent"
    assert extracted["agent_id"] == "agent-42"


def test_genai_semconv_conversation_id_thread_and_priority() -> None:
    """gen_ai.conversation.id sets thread_id + is_turn and outranks wandb.thread_id."""
    extracted = get_wandb_attributes(
        create_attributes({"gen_ai.conversation.id": "conv-abc-123"})
    )
    assert extracted["thread_id"] == "conv-abc-123"
    assert extracted["is_turn"]

    extracted = get_wandb_attributes(
        create_attributes(
            {
                "gen_ai.conversation.id": "conv-from-semconv",
                "wandb.thread_id": "thread-from-wandb",
            }
        )
    )
    assert extracted["thread_id"] == "conv-from-semconv"


def test_opentelemetry_cost_calculation(client: weave_client.WeaveClient) -> None:
    """Test that costs are properly calculated for OTEL spans with usage at query time."""
    project_id = client.project_id

    # Create span with gpt-4 model and usage
    span_gpt4 = create_test_span()
    span_gpt4.name = "llm_call_gpt4"

    # Add model attribute
    kv_model = KeyValue()
    kv_model.key = "gen_ai.request.model"
    kv_model.value.string_value = "gpt-4"
    span_gpt4.attributes.append(kv_model)

    # Add usage attributes
    kv_prompt = KeyValue()
    kv_prompt.key = "gen_ai.usage.prompt_tokens"
    kv_prompt.value.int_value = 1000000
    span_gpt4.attributes.append(kv_prompt)

    kv_completion = KeyValue()
    kv_completion.key = "gen_ai.usage.completion_tokens"
    kv_completion.value.int_value = 2000000
    span_gpt4.attributes.append(kv_completion)

    # Create export request
    export_req = create_test_export_request(project_id=project_id)
    # Materialize processed_spans to avoid iterator exhaustion
    processed_spans_list = export_req.processed_spans
    processed_spans_list[0].resource_spans.scope_spans[0].spans[0].CopyFrom(span_gpt4)
    export_req.processed_spans = processed_spans_list
    export_req.wb_user_id = "test_user"

    # Export the trace
    client.server.otel_export(export_req)

    # Query with costs
    res_with_cost = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=project_id,
            include_costs=True,
        )
    )

    # Query without costs
    res_no_cost = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=project_id,
            include_costs=False,
        )
    )

    assert len(res_with_cost.calls) == 1
    assert len(res_no_cost.calls) == 1

    call_with_cost = res_with_cost.calls[0]
    call_no_cost = res_no_cost.calls[0]
    assert call_with_cost.summary is not None

    # Verify model cost information is present when requested
    assert "gpt-4" in call_with_cost.summary["weave"]["costs"]  # type: ignore

    gpt4_cost = call_with_cost.summary["weave"]["costs"]["gpt-4"]  # type: ignore
    del gpt4_cost["effective_date"]  # type: ignore
    del gpt4_cost["created_at"]  # type: ignore
    # Verify cost calculation matches expected values
    assert (
        gpt4_cost
        == {
            "prompt_tokens": 1000000,
            "completion_tokens": 2000000,
            "requests": 0,  # OTEL doesn't track requests separately
            "total_tokens": 3000000,  # Now properly calculated from prompt + completion tokens
            "prompt_tokens_total_cost": pytest.approx(30),
            "completion_tokens_total_cost": pytest.approx(120),
            "prompt_token_cost": 3e-05,
            "completion_token_cost": 6e-05,
            "prompt_token_cost_unit": "USD",
            "completion_token_cost_unit": "USD",
            "provider_id": "openai",
            "pricing_level": "default",
            "pricing_level_id": "default",
            "created_by": "system",
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens_total_cost": 0,
            "cache_creation_input_tokens_total_cost": 0,
            "cache_read_input_token_cost": 0,
            "cache_creation_input_token_cost": 0,
        }
    )

    # Verify no cost information when not requested
    assert "costs" not in call_no_cost.summary.get("weave", {})  # type: ignore


def test_capture_parts() -> None:
    """Test capturing parts of a string split by delimiters."""
    assert capture_parts("part1.part2") == ["part1", ".", "part2"]
    assert capture_parts("part1.part2,part3") == [
        "part1",
        ".",
        "part2",
        ",",
        "part3",
    ]
    assert capture_parts("nodelimiters") == ["nodelimiters"]
    assert capture_parts("") == [""]
    assert capture_parts("a-b-c", delimiters=["-"]) == ["a", "-", "b", "-", "c"]
    assert capture_parts("part1..part2") == ["part1", ".", ".", "part2"]


def test_shorten_name() -> None:
    """shorten_name truncates on delimiter boundaries respecting max_len and abbrev."""
    # No delimiters: short names pass through, long names get an ellipsis.
    assert shorten_name("short", 10) == "short"
    assert shorten_name("abcdefghijklmnopqrstuvwxyz", 10) == "abcdefg..."

    # Delimiters: truncate on a boundary, or keep whole when it fits.
    assert shorten_name("part1.part2", 10) == "part1..."
    assert shorten_name("a.b.c", 10) == "a.b.c"
    assert shorten_name("part1.part2.part3", 12) == "part1..."

    # First part already too long.
    assert shorten_name("verylongfirstpart.second", 10) == "verylon..."

    # Custom and empty abbreviations.
    assert shorten_name("part1.part2.part3", 10, "***") == "part1.***"
    assert shorten_name("part1.part2.part3", 10, "") == "part1"

    # Different delimiter types (space, slash, mixed, question mark).
    assert shorten_name("word1 word2 word3", 12) == "word1 ..."
    assert shorten_name("path/to/file", 8) == "path/..."
    assert shorten_name("user.name@example.com", 12) == "user..."
    assert shorten_name("api/endpoint?param=value", 15) == "api/..."

    # '-' is not a default delimiter, so it is treated as part of the string.
    result = shorten_name("part1-part2-part3", 10)
    assert result.startswith("part1-")
    assert result.endswith("...")
    assert len(result) == 10


def test_long_url_regression() -> None:
    # A modified version of the URL that caused failed traces due to op_name length.
    actual = shorten_name(
        "GET /api/trpc/lambda/organization.getActiveOrganization,account.getSubscription,checkout.getPrices,user.getUserToolGroupsConfig?batch=1&input=%8A%220%22%3Z%8A%22json%22%3Znull%2P%22meta%22%3Z%8A%22values%22%3Z%5X%22undefined%22%5D%8D%8D%2P%221%22%3Z%8A%22json%22%3Znull%2P%22meta%22%3Z%8A%22values%22%3Z%5X%22undefined%22%5D%8D%8D%2P%222%22%3Z%8A%22json%22%3Znull%2P%22meta%22%3Z%8A%22values%22%3Z%5X%22undefined%22%5D%8D%8D%2P%223%22%3Z%8A%22json%22%3Znull%2P%22meta%22%3Z%8A%22values%22%3Z%5X%22undefined%22%5D%8D%8D%8D",
        128,
    )
    assert actual.startswith("GET /")
    assert actual.endswith("...")
    assert len(actual) <= 128


def test_try_parse_timestamp() -> None:
    """Test parsing timestamps from various formats."""
    # ISO 8601 string.
    result = try_parse_timestamp("2023-01-01T12:00:00")
    assert isinstance(result, datetime)
    assert (result.year, result.month, result.day) == (2023, 1, 1)
    assert (result.hour, result.minute, result.second) == (12, 0, 0)

    # Nanoseconds since epoch (int) and seconds since epoch (float).
    # Hour is not checked due to timezone differences.
    for ts in (1672574400000000000, 1672574400.0):
        result = try_parse_timestamp(ts)
        assert isinstance(result, datetime)
        assert (result.year, result.month, result.day) == (2023, 1, 1)

    # Invalid string and unsupported types return None.
    assert try_parse_timestamp("not-a-timestamp") is None
    assert try_parse_timestamp(None) is None
    assert try_parse_timestamp({}) is None
    assert try_parse_timestamp([]) is None


def test_get_span_overrides() -> None:
    """get_span_overrides parses ISO + epoch timestamps and tolerates missing ones."""
    # ISO format timestamps round-trip exactly.
    iso_start = "2023-01-01T10:00:00"
    iso_end = "2023-01-01T10:01:30"
    overrides = get_span_overrides(
        expand_attributes(
            [
                ("langfuse.startTime", iso_start),
                ("langfuse.endTime", iso_end),
                ("other.attribute", "value"),
            ]
        )
    )
    assert len(overrides) == 2
    assert isinstance(overrides["start_time"], datetime)
    assert isinstance(overrides["end_time"], datetime)
    assert overrides["start_time"].isoformat() == iso_start
    assert overrides["end_time"].isoformat() == iso_end

    # Epoch timestamps (nanoseconds int + seconds float). Hour is timezone-dependent.
    overrides = get_span_overrides(
        expand_attributes(
            [
                ("langfuse.startTime", 1672574400000000000),
                ("langfuse.endTime", 1672574460.0),
            ]
        )
    )
    assert len(overrides) == 2
    assert isinstance(overrides["start_time"], datetime)
    assert isinstance(overrides["end_time"], datetime)
    assert (overrides["start_time"].year, overrides["start_time"].month) == (2023, 1)
    assert overrides["start_time"].day == 1
    assert (overrides["end_time"].year, overrides["end_time"].month) == (2023, 1)
    assert overrides["end_time"].day == 1
    delta = overrides["end_time"] - overrides["start_time"]
    assert abs(delta.total_seconds() - 60) < 1

    # No override attributes -> empty dict.
    assert (
        get_span_overrides(
            expand_attributes(
                [
                    ("some.attribute", "value"),
                    ("other.attribute", 123),
                ]
            )
        )
        == {}
    )


def test_otel_export_partial_success_on_attribute_conflict(
    client: weave_client.WeaveClient,
):
    """A batch with one good span and one conflicting span returns partial success.

    The good span is ingested; the conflicting span is rejected with a helpful message.
    """
    export_req = create_test_export_request()
    project_id = client.project_id
    export_req.project_id = project_id
    export_req.wb_user_id = "abcd123"

    # Good span (already present at index 0)
    # Materialize processed_spans to avoid iterator exhaustion
    processed_spans_list = export_req.processed_spans

    # Good span (already present at index 0)
    good_span = processed_spans_list[0].resource_spans.scope_spans[0].spans[0]
    good_span_id = hexlify(good_span.span_id).decode("ascii")

    # Add a conflicting span to the same batch
    bad_span = create_test_span()
    # Clear attributes and set conflicting keys: parent primitive + nested subkey
    del bad_span.attributes[:]
    kv_parent = KeyValue()
    kv_parent.key = "gen_ai.prompt"
    kv_parent.value.bool_value = True
    bad_span.attributes.append(kv_parent)

    kv_child = KeyValue()
    kv_child.key = "gen_ai.prompt.content"
    kv_child.value.string_value = "Hello"
    bad_span.attributes.append(kv_child)

    processed_spans_list[0].resource_spans.scope_spans[0].spans.append(bad_span)
    export_req.processed_spans = processed_spans_list
    bad_span_id = hexlify(bad_span.span_id).decode("ascii")

    # Export
    res = client.server.otel_export(export_req)
    assert isinstance(res, tsi.OTelExportRes)
    assert res.partial_success is not None
    assert res.partial_success.rejected_spans == 1
    # Error message should mention the conflicting key and guidance
    assert "gen_ai.prompt" in res.partial_success.error_message

    # Only the good span should be ingested
    calls = client.server.calls_query(tsi.CallsQueryReq(project_id=project_id)).calls
    ingested_ids = {c.id for c in calls}
    assert good_span_id in ingested_ids
    assert bad_span_id not in ingested_ids

    # Cleanup the good call
    client.server.calls_delete(
        tsi.CallsDeleteReq(
            project_id=project_id, call_ids=[good_span_id], wb_user_id=None
        )
    )

    # Test with multiple prompts
    prompts_multiple = {
        "0": {"role": "system", "content": "You are an expert in quantum physics"},
        "1": {"role": "user", "content": "Tell me about quantum computing"},
    }
    attributes = create_attributes(
        {
            OTSpanAttr.LLM_PROMPTS: prompts_multiple,
        }
    )
    inputs = get_weave_inputs([], attributes)
    assert inputs == {
        "gen_ai.prompt": [
            {"role": "system", "content": "You are an expert in quantum physics"},
            {"role": "user", "content": "Tell me about quantum computing"},
        ]
    }


def test_otel_span_wandb_attributes_and_data_routing(
    client: weave_client.WeaveClient,
):
    """Comprehensive test for OTEL trace write and read path.

    This test verifies that:
    1. Custom attributes set via wandb.attributes appear in call.attributes
    2. The full OTEL span data is stored separately and reconstructed in call.attributes.otel_span
    3. Inputs (gen_ai.prompt) are routed to call.inputs
    4. Outputs (gen_ai.completion) are routed to call.output
    """
    # Create a test export request
    export_req = create_test_export_request()
    project_id = client.project_id
    export_req.project_id = project_id
    export_req.wb_user_id = "abcd123"

    # Get the span to add custom attributes
    # Materialize processed_spans to avoid iterator exhaustion
    processed_spans_list = export_req.processed_spans
    span = processed_spans_list[0].resource_spans.scope_spans[0].spans[0]

    # Clear default test attributes
    del span.attributes[:]

    # 1. Add custom attributes via wandb.attributes (nested JSON object)
    # These should appear at the root level of call.attributes
    kv_custom_attrs = KeyValue()
    kv_custom_attrs.key = "wandb.attributes"

    # Create a nested JSON object for custom attributes
    custom_attrs_value = AnyValue()

    # Add a custom tag
    tag_kv = KeyValue()
    tag_kv.key = "custom_tag"
    tag_kv.value.string_value = "production"
    custom_attrs_value.kvlist_value.values.append(tag_kv)

    # Add a custom environment
    env_kv = KeyValue()
    env_kv.key = "environment"
    env_kv.value.string_value = "staging"
    custom_attrs_value.kvlist_value.values.append(env_kv)

    # Add a custom numeric metric
    metric_kv = KeyValue()
    metric_kv.key = "priority"
    metric_kv.value.int_value = 42
    custom_attrs_value.kvlist_value.values.append(metric_kv)

    kv_custom_attrs.value.CopyFrom(custom_attrs_value)
    span.attributes.append(kv_custom_attrs)

    # 2. Add input data (gen_ai.prompt) - should go to call.inputs
    kv_prompt_role = KeyValue()
    kv_prompt_role.key = "gen_ai.prompt.0.role"
    kv_prompt_role.value.string_value = "user"
    span.attributes.append(kv_prompt_role)

    kv_prompt_content = KeyValue()
    kv_prompt_content.key = "gen_ai.prompt.0.content"
    kv_prompt_content.value.string_value = "What is quantum computing?"
    span.attributes.append(kv_prompt_content)

    # 3. Add output data (gen_ai.completion) - should go to call.output
    kv_completion_role = KeyValue()
    kv_completion_role.key = "gen_ai.completion.0.role"
    kv_completion_role.value.string_value = "assistant"
    span.attributes.append(kv_completion_role)

    kv_completion_content = KeyValue()
    kv_completion_content.key = "gen_ai.completion.0.content"
    kv_completion_content.value.string_value = (
        "Quantum computing is a type of computing that uses quantum mechanics."
    )
    span.attributes.append(kv_completion_content)

    # 4. Add some standard attributes that should also appear in call.attributes
    kv_model = KeyValue()
    kv_model.key = "gen_ai.response.model"
    kv_model.value.string_value = "gpt-4"
    span.attributes.append(kv_model)

    kv_provider = KeyValue()
    kv_provider.key = "llm.provider"
    kv_provider.value.string_value = "openai"
    span.attributes.append(kv_provider)

    export_req.processed_spans = processed_spans_list

    # Export the OTEL traces
    response = client.server.otel_export(export_req)
    assert isinstance(response, tsi.OTelExportRes)

    # Query the calls
    res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=project_id,
        )
    )
    assert len(res.calls) == 1

    call = res.calls[0]

    # VERIFICATION 1: Custom attributes from wandb.attributes are in call.attributes
    assert "custom_tag" in call.attributes
    assert call.attributes["custom_tag"] == "production"

    assert "environment" in call.attributes
    assert call.attributes["environment"] == "staging"

    assert "priority" in call.attributes
    assert call.attributes["priority"] == 42

    # VERIFICATION 2: Standard attributes are in call.attributes
    assert "model" in call.attributes
    assert call.attributes["model"] == "gpt-4"

    assert "provider" in call.attributes
    assert call.attributes["provider"] == "openai"

    # VERIFICATION 3: Full OTEL span data exists in call.attributes.otel_span
    assert "otel_span" in call.attributes
    otel_span = call.attributes["otel_span"]

    # Verify otel_span has the core span structure
    assert "context" in otel_span
    assert "trace_id" in otel_span["context"]
    assert "span_id" in otel_span["context"]
    assert "name" in otel_span
    assert otel_span["name"] == "test_span"
    assert "start_time" in otel_span
    assert "end_time" in otel_span
    assert "attributes" in otel_span
    assert "status" in otel_span
    assert otel_span["status"]["code"] == "OK"

    # The otel_span should contain all the original attributes we set
    otel_attributes = otel_span["attributes"]
    # Attributes are nested under their standard namespaces
    assert "wandb" in otel_attributes
    assert "attributes" in otel_attributes["wandb"]
    assert "gen_ai" in otel_attributes
    assert "prompt" in otel_attributes["gen_ai"]
    assert "completion" in otel_attributes["gen_ai"]
    assert "response" in otel_attributes["gen_ai"]
    assert "model" in otel_attributes["gen_ai"]["response"]
    assert "llm" in otel_attributes
    assert "provider" in otel_attributes["llm"]

    # VERIFICATION 4: Inputs are routed to call.inputs (not in attributes)
    assert "gen_ai.prompt" in call.inputs
    prompts = call.inputs["gen_ai.prompt"]
    assert isinstance(prompts, list)
    assert len(prompts) == 1
    assert prompts[0]["role"] == "user"
    assert prompts[0]["content"] == "What is quantum computing?"

    # Inputs should NOT be in attributes (they're routed to inputs field)
    assert "gen_ai.prompt" not in call.attributes or isinstance(
        call.attributes.get("gen_ai.prompt"), dict
    )

    # VERIFICATION 5: Outputs are routed to call.output (not in attributes)
    assert call.output is not None
    assert "gen_ai.completion" in call.output
    completions = call.output["gen_ai.completion"]
    assert isinstance(completions, list)
    assert len(completions) == 1
    assert completions[0]["role"] == "assistant"
    assert completions[0]["content"] == (
        "Quantum computing is a type of computing that uses quantum mechanics."
    )

    # Outputs should NOT be in attributes (they're routed to output field)
    assert "gen_ai.completion" not in call.attributes or isinstance(
        call.attributes.get("gen_ai.completion"), dict
    )

    # Clean up
    client.server.calls_delete(
        tsi.CallsDeleteReq(project_id=project_id, call_ids=[call.id], wb_user_id=None)
    )


def test_otel_export_json_string_and_dotted_completion_keys(
    client: weave_client.WeaveClient,
):
    """Repro: gen_ai.completion as JSON string + gen_ai.completion.0.role silently drops span.

    When an OTel exporter sends both:
      - gen_ai.completion = '[{"role": "assistant", "content": "hello"}]' (JSON string)
      - gen_ai.completion.0.role = "assistant" (dotted subkey)
    the JSON string is auto-parsed into a list, then _validate_structure raises
    AttributePathConflictError because list is not dict. The span is rejected —
    otel_export returns 200 but no call appears in the database.
    """
    export_req = create_test_export_request()
    project_id = client.project_id
    export_req.project_id = project_id
    export_req.wb_user_id = "abcd123"

    processed_spans_list = export_req.processed_spans
    span = processed_spans_list[0].resource_spans.scope_spans[0].spans[0]
    del span.attributes[:]

    kv_json = KeyValue()
    kv_json.key = "gen_ai.completion"
    kv_json.value.string_value = json.dumps(
        [{"role": "assistant", "content": "Quantum computing uses qubits."}]
    )
    span.attributes.append(kv_json)

    kv_role = KeyValue()
    kv_role.key = "gen_ai.completion.0.role"
    kv_role.value.string_value = "assistant"
    span.attributes.append(kv_role)

    kv_content = KeyValue()
    kv_content.key = "gen_ai.completion.0.content"
    kv_content.value.string_value = "Quantum computing uses qubits."
    span.attributes.append(kv_content)

    kv_model = KeyValue()
    kv_model.key = "gen_ai.response.model"
    kv_model.value.string_value = "gpt-4"
    span.attributes.append(kv_model)

    export_req.processed_spans = processed_spans_list

    response = client.server.otel_export(export_req)
    assert isinstance(response, tsi.OTelExportRes)

    res = client.server.calls_query(tsi.CallsQueryReq(project_id=project_id))
    # BUG: span is silently rejected — this assert fails (0 calls instead of 1)
    assert len(res.calls) == 1, (
        f"Expected 1 call but got {len(res.calls)}. "
        "The span was silently rejected due to AttributePathConflictError "
        "when gen_ai.completion (auto-parsed JSON list) conflicts with "
        "gen_ai.completion.0.role dotted subkey."
    )

    call = res.calls[0]
    assert call.output is not None
    assert "gen_ai.completion" in call.output
    completions = call.output["gen_ai.completion"]
    assert isinstance(completions, list)
    assert len(completions) == 1
    assert completions[0]["role"] == "assistant"
