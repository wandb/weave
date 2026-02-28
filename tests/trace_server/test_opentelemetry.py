import hashlib
import json
import uuid
from binascii import hexlify
from datetime import datetime
from typing import Any

import pytest
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

from tests.trace.util import client_is_sqlite
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
    SpanEvent,
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
    project_id = client._project_id()
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
    project_id = client._project_id()

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
    # mangled/re-sanitized name.  The sqlite server doesn't do op object
    # resolution, so we skip this assertion there.
    if not client_is_sqlite(client):
        for call in res.calls:
            assert call.op_name.startswith("weave:///"), (
                f"op_name should be a ref URI, got: {call.op_name}"
            )


def test_otel_export_with_turn_and_thread(client: weave_client.WeaveClient):
    """Test the otel_export method with turn and thread attributes."""
    # Create a test export request
    export_req = create_test_export_request()
    project_id = client._project_id()
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
    project_id = client._project_id()
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


class TestPythonSpans:
    def test_span_from_proto(self):
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
        assert (
            get_attribute(py_span.attributes, "test.nested.value")
            == "nested_test_value"
        )
        array_value = get_attribute(py_span.attributes, "test.array")
        assert isinstance(array_value, list)
        assert len(array_value) == 2
        assert array_value[0] == "value1"
        assert array_value[1] == "value2"

    def test_span_to_call(self):
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

    def test_span_to_call_long_name(self):
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

    def test_span_to_call_with_turn_and_thread(self):
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

    def test_traces_data_from_proto(self):
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


class TestAttributes:
    def test_to_json_serializable(self):
        """Test converting various types to JSON serializable values."""
        # Test primitive types
        assert to_json_serializable("string") == "string"
        assert to_json_serializable(42) == 42
        assert to_json_serializable(3.14) == 3.14
        assert to_json_serializable(True) == True
        assert to_json_serializable(None) is None

        # Test lists and tuples
        assert to_json_serializable(["a", 1, True]) == ["a", 1, True]
        assert to_json_serializable(("a", 1, True)) == ["a", 1, True]

        # Test dictionaries
        assert to_json_serializable({"a": 1, "b": "two"}) == {"a": 1, "b": "two"}

        # Test nested structures
        nested = {"a": [1, 2, {"b": "c"}], "d": {"e": [3, 4]}}
        assert to_json_serializable(nested) == nested

        # Test datetime
        dt = datetime(2023, 1, 1, 12, 0, 0)
        assert to_json_serializable(dt) == "2023-01-01T12:00:00"

        # Test enums
        assert to_json_serializable(SpanKind.INTERNAL) == 1

    def test_to_json_serializable_special_floats(self):
        """Test converting special float values (NaN, Infinity)."""
        # Test NaN
        assert to_json_serializable(float("nan")) == "nan"

        # Test positive infinity
        assert to_json_serializable(float("inf")) == "inf"

        # Test negative infinity
        assert to_json_serializable(float("-inf")) == "-inf"

    def test_to_json_serializable_date_time(self):
        """Test converting date and time objects."""
        from datetime import date, time

        # Test date
        d = date(2023, 1, 1)
        assert to_json_serializable(d) == "2023-01-01"

        # Test time
        t = time(12, 30, 45)
        assert to_json_serializable(t) == "12:30:45"

    def test_to_json_serializable_timedelta(self):
        """Test converting timedelta objects."""
        from datetime import timedelta

        # Test one day
        td = timedelta(days=1)
        assert to_json_serializable(td) == 86400.0  # 24 * 60 * 60 seconds

        # Test complex timedelta
        td = timedelta(days=1, hours=2, minutes=30, seconds=15)
        expected_seconds = (1 * 24 * 60 * 60) + (2 * 60 * 60) + (30 * 60) + 15
        assert to_json_serializable(td) == expected_seconds

    def test_to_json_serializable_uuid(self):
        """Test converting UUID objects."""
        import uuid

        # Create a UUID with a known value
        test_uuid = uuid.UUID("12345678-1234-5678-1234-567812345678")
        assert to_json_serializable(test_uuid) == "12345678-1234-5678-1234-567812345678"

    def test_to_json_serializable_decimal(self):
        """Test converting Decimal objects."""
        from decimal import Decimal

        # Test simple decimal
        assert to_json_serializable(Decimal("10.5")) == 10.5

        # Test high precision decimal
        assert (
            to_json_serializable(Decimal("3.14159265358979323846"))
            == 3.14159265358979323846
        )

        # Test zero
        assert to_json_serializable(Decimal("0")) == 0.0

    def test_to_json_serializable_sets(self):
        """Test converting set and frozenset objects."""
        # Test set
        s = {1, 2, 3, "test"}
        result = to_json_serializable(s)
        assert isinstance(result, list)
        assert len(result) == 4
        assert 1 in result
        assert 2 in result
        assert 3 in result
        assert "test" in result

        # Test frozenset
        fs = frozenset([4, 5, 6, "frozen"])
        result = to_json_serializable(fs)
        assert isinstance(result, list)
        assert len(result) == 4
        assert 4 in result
        assert 5 in result
        assert 6 in result
        assert "frozen" in result

    def test_to_json_serializable_complex(self):
        """Test converting complex numbers."""
        c = complex(3, 4)
        result = to_json_serializable(c)
        assert isinstance(result, dict)
        assert result == {"real": 3.0, "imag": 4.0}

        # Test complex with negative imaginary part
        c = complex(1, -2)
        assert to_json_serializable(c) == {"real": 1.0, "imag": -2.0}

    def test_to_json_serializable_bytes(self):
        """Test converting bytes and bytearray objects."""
        # Test bytes
        b = b"hello world"
        assert to_json_serializable(b) == "aGVsbG8gd29ybGQ="  # Base64 encoded

        # Test bytearray
        ba = bytearray(b"hello world")
        assert to_json_serializable(ba) == "aGVsbG8gd29ybGQ="  # Base64 encoded

    def test_to_json_serializable_dataclass(self):
        """Test converting dataclass objects."""
        from dataclasses import dataclass

        @dataclass
        class Person:
            name: str
            age: int

        person = Person(name="John", age=30)
        result = to_json_serializable(person)
        assert isinstance(result, dict)
        assert result == {"name": "John", "age": 30}

        # Nested dataclass
        @dataclass
        class Department:
            name: str
            head: Person

        dept = Department(name="Engineering", head=Person(name="Jane", age=35))
        result = to_json_serializable(dept)
        assert result == {"name": "Engineering", "head": {"name": "Jane", "age": 35}}

    def test_unflatten_key_values(self):
        """Test unflattening key-value pairs into nested structure."""
        # Create key-value pairs
        kv1 = KeyValue(key="a.b.c", value=AnyValue(string_value="value1"))
        kv2 = KeyValue(key="a.b.d", value=AnyValue(int_value=42))
        kv3 = KeyValue(key="a.e", value=AnyValue(bool_value=True))
        kv4 = KeyValue(key="f.0", value=AnyValue(string_value="item0"))
        kv5 = KeyValue(key="f.1", value=AnyValue(string_value="item1"))

        # Unflatten key-values
        result = unflatten_key_values([kv1, kv2, kv3, kv4, kv5])

        # Verify the result
        assert result == {
            "a": {"b": {"c": "value1", "d": 42}, "e": True},
            "f": {"0": "item0", "1": "item1"},
        }

    def test_get_attribute(self):
        """Test getting attributes from nested structures."""
        nested = {"a": {"b": {"c": "value1"}}, "d": [1, 2, 3]}

        assert get_attribute(nested, "a.b.c") == "value1"
        assert get_attribute(nested, "a.b") == {"c": "value1"}
        assert get_attribute(nested, "d") == [1, 2, 3]

        assert get_attribute(nested, "d.0") == 1

        assert get_attribute(nested, "nonexistent") is None

    def test_expand_attributes(self):
        """Test expanding flattened attributes into nested structure."""
        flat_attrs = [
            ("a.b.c", "value1"),
            ("a.b.d", 42),
            ("a.e", True),
            ("f.0", "item0"),
            ("f.1", "item1"),
        ]

        result = expand_attributes(flat_attrs)

        assert result == {
            "a": {"b": {"c": "value1", "d": 42}, "e": True},
            "f": {"0": "item0", "1": "item1"},
        }

    def test_expand_attributes_convert_numeric_to_list(self):
        """Test expanding flattened attributes into nested structure."""
        flat_attrs = [
            ("a.b.c", "value1"),
            ("a.b.d", 42),
            ("a.e", True),
            ("f.0", "item0"),
            ("f.1", "item1"),
        ]

        result = convert_numeric_keys_to_list(expand_attributes(flat_attrs))

        assert result == {
            "a": {"b": {"c": "value1", "d": 42}, "e": True},
            "f": ["item0", "item1"],
        }

    def test_flatten_attributes(self):
        """Test flattening nested attributes into key-value pairs."""
        nested = {
            "a": {"b": {"c": "value1", "d": 42}, "e": True},
            "f": ["item0", "item1"],
        }

        result = flatten_attributes(nested)

        expected = {
            "a.b.c": "value1",
            "a.b.d": 42,
            "a.e": True,
            "f.0": "item0",
            "f.1": "item1",
        }

        assert result == expected

    def test_expand_attributes_conflict_parent_then_child(self):
        """Setting a parent primitive then a nested subkey should raise a clear error."""
        flat_attrs = [
            ("gen_ai.prompt", True),
            ("gen_ai.prompt.content", "Hello"),
        ]

        try:
            expand_attributes(flat_attrs)
            raise AssertionError("Expected AttributePathConflictError")
        except AttributePathConflictError as e:
            msg = str(e)
            assert "gen_ai.prompt" in msg
            assert "content" in msg
            assert "Do not" in msg or "Invalid attribute structure" in msg

    def test_expand_attributes_conflict_child_then_parent(self):
        """Setting nested subkeys then a parent primitive should raise a clear error."""
        flat_attrs = [
            ("gen_ai.prompt.content", "Hello"),
            ("gen_ai.prompt", True),
        ]

        try:
            expand_attributes(flat_attrs)
            raise AssertionError("Expected AttributePathConflictError")
        except AttributePathConflictError as e:
            msg = str(e)
            assert "gen_ai.prompt" in msg
            assert "Do not" in msg or "Invalid attribute structure" in msg


def create_attributes(d: dict[str, Any]):
    return expand_attributes(d.items())


class TestSemanticConventionParsing:
    """Test the semantic convention parsing functionality in attributes.py."""

    def test_openinference_attributes_extraction(self):
        """Test extracting attributes from OpenInference attributes."""
        from openinference.semconv.trace import SpanAttributes as OISpanAttr

        # Create attribute dictionary with OpenInference attributes
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

        # Test get_weave_attributes
        extracted = get_weave_attributes(attributes)
        assert extracted["system"] == "This is a system prompt"
        assert extracted["provider"] == "test-provider"
        assert extracted["model"] == "test-model"
        assert extracted["kind"] == "llm"
        assert extracted["model_parameters"]["max_tokens"] == 100
        assert extracted["model_parameters"]["temperature"] == 0.7

    def test_wandb_attributes_extraction(self):
        """Test extracting wandb-specific attributes."""
        # Create attribute dictionary with W&B specific attributes
        attributes = create_attributes(
            {
                "wandb.display_name": "My Custom Display Name",
            }
        )

        # Test get_wandb_attributes
        extracted = get_wandb_attributes(attributes)
        assert extracted["display_name"] == "My Custom Display Name"

        # Test with missing attributes
        empty_attributes = create_attributes({})
        extracted = get_wandb_attributes(empty_attributes)
        assert extracted == {}

        # Test with partial attributes
        partial_attributes = create_attributes(
            {
                "wandb.display_name": "Only Display Name",
            }
        )
        extracted = get_wandb_attributes(partial_attributes)
        assert extracted["display_name"] == "Only Display Name"
        assert "project_id" not in extracted

        # Test with nested attributes format
        nested_attributes = create_attributes(
            {
                "wandb": {
                    "display_name": "Nested Display Name",
                }
            }
        )
        extracted = get_wandb_attributes(nested_attributes)
        assert extracted["display_name"] == "Nested Display Name"

    def test_wandb_turn_and_thread_attributes(self):
        """Test extracting turn and thread attributes from wandb attributes."""
        # Test with is_turn = True and thread_id
        test_thread_id = str(uuid.uuid4())
        attributes = create_attributes(
            {
                "wandb.is_turn": True,
                "wandb.thread_id": test_thread_id,
            }
        )

        extracted = get_wandb_attributes(attributes)
        assert extracted["is_turn"] is True
        assert extracted["thread_id"] == test_thread_id

        # Test with is_turn = False
        attributes_false = create_attributes(
            {
                "wandb.is_turn": False,
                "wandb.thread_id": test_thread_id,
            }
        )
        extracted_false = get_wandb_attributes(attributes_false)
        assert "is_turn" not in extracted_false.keys()
        assert extracted_false["thread_id"] == test_thread_id

        # Test with only thread_id
        attributes_thread_only = create_attributes(
            {
                "wandb.thread_id": test_thread_id,
            }
        )
        extracted_thread_only = get_wandb_attributes(attributes_thread_only)
        assert "is_turn" not in extracted_thread_only
        assert extracted_thread_only["thread_id"] == test_thread_id

        # Test with only is_turn
        attributes_turn_only = create_attributes(
            {
                "wandb.is_turn": True,
            }
        )
        extracted_turn_only = get_wandb_attributes(attributes_turn_only)
        assert extracted_turn_only["is_turn"] is True
        assert "thread_id" not in extracted_turn_only

    @pytest.mark.skip(reason="wb_run_id extraction not yet implemented")
    def test_wandb_wb_run_id_extraction(self):
        """Test extracting wb_run_id from both wb_run_id and wandb.wb_run_id attributes."""
        # Case 1: Only top-level wb_run_id present
        attributes_top_level = create_attributes(
            {
                "wb_run_id": "run_top_123",
            }
        )
        extracted_top_level = get_wandb_attributes(attributes_top_level)
        assert extracted_top_level["wb_run_id"] == "run_top_123"

        # Case 2: Only namespaced wandb.wb_run_id present
        attributes_namespaced = create_attributes(
            {
                "wandb.wb_run_id": "run_ns_456",
            }
        )
        extracted_namespaced = get_wandb_attributes(attributes_namespaced)
        assert extracted_namespaced["wb_run_id"] == "run_ns_456"

        # Case 3: Both present, top-level should take precedence
        attributes_both = create_attributes(
            {
                "wb_run_id": "preferred_top",
                "wandb.wb_run_id": "fallback_ns",
            }
        )
        extracted_both = get_wandb_attributes(attributes_both)
        assert extracted_both["wb_run_id"] == "preferred_top"

    def test_openinference_inputs_extraction(self):
        """Test extracting inputs from OpenInference attributes."""
        from openinference.semconv.trace import SpanAttributes as OISpanAttr

        # Create attribute dictionary with OpenInference input value and mime type
        attributes = create_attributes(
            {
                OISpanAttr.INPUT_VALUE: "What is machine learning?",
                OISpanAttr.INPUT_MIME_TYPE: "text/plain",
            }
        )

        # Test get_weave_inputs with text input
        inputs = get_weave_inputs([], attributes)
        assert inputs == {
            "input.value": "What is machine learning?",
        }

        # Test with JSON input
        json_input = json.dumps(
            {
                "messages": [
                    {"role": "system", "content": "You are an assistant"},
                    {"role": "user", "content": "What is machine learning?"},
                ]
            }
        )
        attributes = create_attributes(
            {
                OISpanAttr.INPUT_VALUE: json_input,
                OISpanAttr.INPUT_MIME_TYPE: "application/json",
            }
        )
        inputs = get_weave_inputs([], attributes)
        assert inputs == {
            "input.value": {
                "messages": [
                    {"role": "system", "content": "You are an assistant"},
                    {"role": "user", "content": "What is machine learning?"},
                ]
            },
        }

    def test_openinference_outputs_extraction(self):
        """Test extracting outputs from OpenInference attributes."""
        from openinference.semconv.trace import SpanAttributes as OISpanAttr

        # Create attribute dictionary with OpenInference output value and mime type
        attributes = create_attributes(
            {
                OISpanAttr.OUTPUT_VALUE: "Machine learning is a field of AI...",
                OISpanAttr.OUTPUT_MIME_TYPE: "text/plain",
            }
        )

        # Test get_weave_outputs with text output
        outputs = get_weave_outputs([], attributes)
        assert outputs == {
            "output.value": "Machine learning is a field of AI...",
        }

        # Test with JSON output
        json_output = json.dumps(
            {
                "response": {
                    "role": "assistant",
                    "content": "Machine learning is a field of AI...",
                }
            }
        )
        attributes = create_attributes(
            {
                OISpanAttr.OUTPUT_VALUE: json_output,
                OISpanAttr.OUTPUT_MIME_TYPE: "application/json",
            }
        )
        outputs = get_weave_outputs([], attributes)
        assert outputs == {
            "output.value": {
                "response": {
                    "role": "assistant",
                    "content": "Machine learning is a field of AI...",
                }
            },
        }

    def test_openinference_usage_extraction(self):
        """Test extracting usage from OpenInference attributes."""
        from openinference.semconv.trace import SpanAttributes as OISpanAttr

        # Create attribute dictionary with OpenInference token counts
        attributes = create_attributes(
            {
                OISpanAttr.LLM_TOKEN_COUNT_PROMPT: 10,
                OISpanAttr.LLM_TOKEN_COUNT_COMPLETION: 20,
                OISpanAttr.LLM_TOKEN_COUNT_TOTAL: 30,
            }
        )

        # Test get_weave_usage
        usage = get_weave_usage(attributes)
        assert usage.get("prompt_tokens") == 10
        assert usage.get("completion_tokens") == 20
        assert usage.get("total_tokens") == 30

    def test_opentelemetry_attributes_extraction(self):
        """Test extracting attributes from OpenTelemetry attributes."""
        from opentelemetry.semconv_ai import SpanAttributes as OTSpanAttr

        # Create attribute dictionary with OpenTelemetry attributes
        attributes = create_attributes(
            {
                OTSpanAttr.LLM_SYSTEM: "You are a helpful assistant",
                OTSpanAttr.LLM_REQUEST_MAX_TOKENS: 150,
                OTSpanAttr.TRACELOOP_SPAN_KIND: "llm",
                OTSpanAttr.LLM_RESPONSE_MODEL: "gpt-4",
            }
        )

        # Test get_weave_attributes
        extracted = get_weave_attributes(attributes)
        assert extracted["system"] == "You are a helpful assistant"
        assert extracted["model_parameters"]["max_tokens"] == 150
        assert extracted["kind"] == "llm"
        assert extracted["model"] == "gpt-4"

    def test_opentelemetry_inputs_extraction(self):
        """Test extracting inputs from OpenTelemetry attributes."""
        from opentelemetry.semconv_ai import SpanAttributes as OTSpanAttr

        # Create attribute dictionary with OpenTelemetry prompts
        prompts = {"0": {"role": "user", "content": "Tell me about quantum computing"}}
        attributes = create_attributes(
            {
                OTSpanAttr.LLM_PROMPTS: prompts,
            }
        )

        # Test get_weave_inputs
        inputs = get_weave_inputs([], attributes)
        assert inputs == {
            "gen_ai.prompt": [
                {"role": "user", "content": "Tell me about quantum computing"}
            ]
        }

    def test_opentelemetry_outputs_extraction(self):
        """Test extracting outputs from OpenTelemetry attributes."""
        from opentelemetry.semconv_ai import SpanAttributes as OTSpanAttr

        # Create attribute dictionary with OpenTelemetry completions
        completions = {
            "0": {
                "role": "assistant",
                "content": "Quantum computing uses quantum mechanics...",
            }
        }
        attributes = create_attributes(
            {
                OTSpanAttr.LLM_COMPLETIONS: completions,
            }
        )

        # Create OpenTelemetry attributes object

        # Test get_weave_outputs
        outputs = get_weave_outputs([], attributes)
        assert outputs == {
            "gen_ai.completion": [
                {
                    "role": "assistant",
                    "content": "Quantum computing uses quantum mechanics...",
                }
            ]
        }

    def test_opentelemetry_usage_extraction(self):
        """Test extracting usage from OpenTelemetry attributes."""
        from opentelemetry.semconv_ai import SpanAttributes as OTSpanAttr

        # Create attribute dictionary with OpenTelemetry token usage
        attributes = create_attributes(
            {
                OTSpanAttr.LLM_USAGE_PROMPT_TOKENS: 15,
                OTSpanAttr.LLM_USAGE_COMPLETION_TOKENS: 25,
                OTSpanAttr.LLM_USAGE_TOTAL_TOKENS: 40,
            }
        )

        # Create OpenTelemetry attributes object
        usage = get_weave_usage(attributes) or {}

        assert usage.get("prompt_tokens") == 15
        assert usage.get("completion_tokens") == 25
        assert usage.get("total_tokens") == 40

    def test_opentelemetry_usage_output_tokens_extraction(self):
        """Test that gen_ai.usage.output_tokens is properly parsed and combined with input_tokens."""
        attributes = create_attributes(
            {
                "gen_ai.usage.input_tokens": 10,
                "gen_ai.usage.output_tokens": 20,
            }
        )

        usage = get_weave_usage(attributes) or {}

        # Verify individual tokens are parsed
        assert usage.get("input_tokens") == 10
        assert usage.get("output_tokens") == 20
        # Verify total_tokens is calculated when not provided
        assert usage.get("total_tokens") == 30

    def test_opentelemetry_usage_output_tokens_with_explicit_total(self):
        """Test that explicit total_tokens takes precedence over calculated value."""
        attributes = create_attributes(
            {
                "gen_ai.usage.input_tokens": 10,
                "gen_ai.usage.output_tokens": 20,
                "llm.usage.total_tokens": 35,
            }
        )

        usage = get_weave_usage(attributes) or {}

        # Verify individual tokens are parsed
        assert usage.get("input_tokens") == 10
        assert usage.get("output_tokens") == 20
        # Verify explicit total_tokens is used instead of calculated value
        assert usage.get("total_tokens") == 35

    def test_opentelemetry_cost_calculation(self, client: weave_client.WeaveClient):
        """Test that costs are properly calculated for OTEL spans with usage at query time."""
        if client_is_sqlite(client):
            # SQLite does not support costs
            return

        project_id = client._project_id()

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
        processed_spans_list[0].resource_spans.scope_spans[0].spans[0].CopyFrom(
            span_gpt4
        )
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
            }
        )

        # Verify no cost information when not requested
        assert "costs" not in call_no_cost.summary.get("weave", {})  # type: ignore

    def test_bedrock_agent_event_input_output_and_tools(self):
        """Ensure Bedrock agent OTEL events hydrate inputs, outputs, and attributes."""
        question_text = "How to see configs of runs in W&B Models?"
        answer_text = "Based on the search results, I can now provide you with information..."
        events = [
            SpanEvent(
                name="gen_ai.user.message",
                timestamp=datetime.now(),
                attributes={"content": [{"text": question_text}]},
                dropped_attributes_count=0,
            ),
            SpanEvent(
                name="gen_ai.choice",
                timestamp=datetime.now(),
                attributes={
                    "message": answer_text,
                    "finish_reason": "end_turn",
                },
                dropped_attributes_count=0,
            ),
        ]
        attributes = create_attributes(
            {
                "system_prompt": "You are a helpful documentation assistant for W&B Weave.",
                "gen_ai.agent.tools": [
                    "SearchWeightsBiasesDocumentation",
                    "http_request",
                ],
                "gen_ai.agent.name": "Strands Agents",
                "gen_ai.operation.name": "invoke_agent",
                "gen_ai.request.model": "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
            }
        )

        inputs = get_weave_inputs(events, attributes)
        assert "events.gen_ai.user.message" in inputs
        event_messages = inputs["events.gen_ai.user.message"]
        assert isinstance(event_messages, list)
        assert event_messages[0]["content"][0]["text"] == question_text

        outputs = get_weave_outputs(events, attributes)
        assert "events.gen_ai.choice" in outputs
        choice_events = outputs["events.gen_ai.choice"]
        assert isinstance(choice_events, list)
        assert choice_events[0]["message"] == answer_text

        extracted_attributes = get_weave_attributes(attributes)
        assert (
            extracted_attributes["system"]
            == "You are a helpful documentation assistant for W&B Weave."
        )
        assert extracted_attributes["tools"] == [
            "SearchWeightsBiasesDocumentation",
            "http_request",
        ]
        assert extracted_attributes["agent"] == "Strands Agents"
        assert extracted_attributes["operation"] == "invoke_agent"
        assert (
            extracted_attributes["model"]
            == "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
        )

class TestHelpers:
    def test_capture_parts(self):
        """Test capturing parts of a string split by delimiters."""
        # Test with a single delimiter
        assert capture_parts("part1.part2") == ["part1", ".", "part2"]

        # Test with multiple delimiters
        assert capture_parts("part1.part2,part3") == [
            "part1",
            ".",
            "part2",
            ",",
            "part3",
        ]

        # Test with delimiters that don't appear in the string
        assert capture_parts("nodelimiters") == ["nodelimiters"]

        # Test with an empty string
        assert capture_parts("") == [""]

        # Test with custom delimiters
        assert capture_parts("a-b-c", delimiters=["-"]) == ["a", "-", "b", "-", "c"]

        # Test with adjacent delimiters
        assert capture_parts("part1..part2") == ["part1", ".", ".", "part2"]

    def test_shorten_name_no_delimiters(self):
        """Test shortening a name with no delimiters."""
        # Test a string shorter than max_len - the function always adds ellipsis
        assert shorten_name("short", 10) == "short"

        # Test a string longer than max_len with no delimiters
        long_name = "abcdefghijklmnopqrstuvwxyz"
        assert shorten_name(long_name, 10) == "abcdefg..."

    def test_shorten_name_with_delimiters(self):
        """Test shortening a name with delimiters."""
        # Test with a single delimiter
        assert shorten_name("part1.part2", 10) == "part1..."

        # Test with multiple delimiters where it fits within the max_len
        assert shorten_name("a.b.c", 10) == "a.b.c"

        # Test with multiple delimiters where it needs truncation
        assert shorten_name("part1.part2.part3", 12) == "part1..."

    def test_shorten_name_first_part_too_long(self):
        """Test shortening a name where first part is already too long."""
        # First part already exceeds max_len
        assert shorten_name("verylongfirstpart.second", 10) == "verylon..."

    def test_shorten_name_custom_abbreviation(self):
        """Test shortening a name with custom abbreviation."""
        assert shorten_name("part1.part2.part3", 10, "***") == "part1.***"

        # Test with empty abbreviation
        assert shorten_name("part1.part2.part3", 10, "") == "part1"

    def test_shorten_name_different_delimiters(self):
        """Test shortening a name with different types of delimiters."""
        # Test with a space delimiter
        assert shorten_name("word1 word2 word3", 12) == "word1 ..."

        # Test with a slash delimiter
        assert shorten_name("path/to/file", 8) == "path/..."

        # Test with mixed delimiters
        assert shorten_name("user.name@example.com", 12) == "user..."

        # Test with a delimiter not in the default list
        # Since '-' is not in the default delimiters list, it's treated as part of the string
        result = shorten_name("part1-part2-part3", 10)
        assert result.startswith("part1-")
        assert result.endswith("...")
        assert len(result) == 10

        # Test with a question mark delimiter
        assert shorten_name("api/endpoint?param=value", 15) == "api/..."

    def test_long_url_regression(self):
        # Test for a modified version of the URL which caused failed traces due to op_name length
        actual = shorten_name(
            "GET /api/trpc/lambda/organization.getActiveOrganization,account.getSubscription,checkout.getPrices,user.getUserToolGroupsConfig?batch=1&input=%8A%220%22%3Z%8A%22json%22%3Znull%2P%22meta%22%3Z%8A%22values%22%3Z%5X%22undefined%22%5D%8D%8D%2P%221%22%3Z%8A%22json%22%3Znull%2P%22meta%22%3Z%8A%22values%22%3Z%5X%22undefined%22%5D%8D%8D%2P%222%22%3Z%8A%22json%22%3Znull%2P%22meta%22%3Z%8A%22values%22%3Z%5X%22undefined%22%5D%8D%8D%2P%223%22%3Z%8A%22json%22%3Znull%2P%22meta%22%3Z%8A%22values%22%3Z%5X%22undefined%22%5D%8D%8D%8D",
            128,
        )
        # The new implementation shortens the URL differently, so we check that it has the correct format
        # and doesn't exceed the maximum length
        assert actual.startswith("GET /")
        assert actual.endswith("...")
        assert len(actual) <= 128

    def test_try_parse_timestamp(self):
        """Test parsing timestamps from various formats."""
        from datetime import datetime

        # Test parsing ISO 8601 format string
        iso_timestamp = "2023-01-01T12:00:00"
        result = try_parse_timestamp(iso_timestamp)
        assert isinstance(result, datetime)
        assert result.year == 2023
        assert result.month == 1
        assert result.day == 1
        assert result.hour == 12
        assert result.minute == 0
        assert result.second == 0

        # Test parsing nanoseconds since epoch (int)
        ns_timestamp = 1672574400000000000  # 2023-01-01T12:00:00 in nanoseconds
        result = try_parse_timestamp(ns_timestamp)
        assert isinstance(result, datetime)
        assert result.year == 2023
        assert result.month == 1
        assert result.day == 1
        # Hour may vary based on timezone, so we don't check it

        # Test parsing seconds since epoch (float)
        seconds_timestamp = 1672574400.0  # 2023-01-01T12:00:00 in seconds
        result = try_parse_timestamp(seconds_timestamp)
        assert isinstance(result, datetime)
        assert result.year == 2023
        assert result.month == 1
        assert result.day == 1
        # Hour may vary based on timezone, so we don't check it

        # Test with invalid string format
        invalid_string = "not-a-timestamp"
        assert try_parse_timestamp(invalid_string) is None

        # Test with other types
        assert try_parse_timestamp(None) is None
        assert try_parse_timestamp({}) is None
        assert try_parse_timestamp([]) is None


class TestSpanOverrides:
    """Test the functionality for span overrides in opentelemetry attributes."""

    def test_get_span_overrides(self):
        """Test extracting span overrides from attributes."""
        # Create attribute dictionary with timestamp overrides in ISO format
        iso_start = "2023-01-01T10:00:00"
        iso_end = "2023-01-01T10:01:30"
        attributes = expand_attributes(
            [
                ("langfuse.startTime", iso_start),
                ("langfuse.endTime", iso_end),
                ("other.attribute", "value"),
            ]
        )

        # Test extracting the overrides
        overrides = get_span_overrides(attributes)
        assert len(overrides) == 2
        assert isinstance(overrides["start_time"], datetime)
        assert isinstance(overrides["end_time"], datetime)
        assert overrides["start_time"].isoformat() == iso_start
        assert overrides["end_time"].isoformat() == iso_end

    def test_get_span_overrides_with_timestamps(self):
        """Test extracting span overrides with different timestamp formats."""
        from datetime import datetime

        # Create attribute dictionary with epoch timestamps
        start_ns = 1672574400000000000  # 2023-01-01T12:00:00 in nanoseconds
        end_seconds = 1672574460.0  # 2023-01-01T12:01:00 in seconds

        attributes = expand_attributes(
            [
                ("langfuse.startTime", start_ns),
                ("langfuse.endTime", end_seconds),
            ]
        )

        # Test extracting the overrides
        overrides = get_span_overrides(attributes)
        assert len(overrides) == 2
        assert isinstance(overrides["start_time"], datetime)
        assert isinstance(overrides["end_time"], datetime)

        # Check the year/month/day to ensure timestamps were parsed correctly
        # (not checking hour due to timezone differences)
        assert overrides["start_time"].year == 2023
        assert overrides["start_time"].month == 1
        assert overrides["start_time"].day == 1

        assert overrides["end_time"].year == 2023
        assert overrides["end_time"].month == 1
        assert overrides["end_time"].day == 1

        # End time should be 60 seconds after start time
        delta = overrides["end_time"] - overrides["start_time"]
        assert (
            abs(delta.total_seconds() - 60) < 1
        )  # Allow small difference due to float precision

    def test_get_span_overrides_with_missing_attributes(self):
        """Test get_span_overrides when no override attributes are present."""
        # Create attribute dictionary without overrides
        attributes = expand_attributes(
            [
                ("some.attribute", "value"),
                ("other.attribute", 123),
            ]
        )

        # Test extracting the overrides
        overrides = get_span_overrides(attributes)
        assert overrides == {}


def test_otel_export_partial_success_on_attribute_conflict(
    client: weave_client.WeaveClient,
):
    """A batch with one good span and one conflicting span returns partial success.

    The good span is ingested; the conflicting span is rejected with a helpful message.
    """
    export_req = create_test_export_request()
    project_id = client._project_id()
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
    project_id = client._project_id()
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
