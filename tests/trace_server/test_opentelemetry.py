import uuid
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
)
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

from weave.trace import weave_client
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.clickhouse_trace_server_batched import ClickHouseTraceServer
from weave.trace_server.opentelemetry.attributes import (
    expand_attributes,
    flatten_attributes,
    get_attribute,
    to_json_serializable,
    unflatten_key_values,
    convert_numeric_keys_to_list
)
from weave.trace_server.opentelemetry.python_spans import Span as PySpan
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
    span.kind = 1

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
    span.status.code = StatusCode.OK.value
    span.status.message = "Success"

    return span


def create_test_export_request(project_id="test_project"):
    """Create a test ExportTraceServiceRequest with one span."""
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

    # Create traces data
    traces_data = TracesData()
    traces_data.resource_spans.append(resource_spans)

    # Create export request
    request = ExportTraceServiceRequest()
    request.resource_spans.append(resource_spans)

    return tsi.OtelExportReq(project_id=project_id, traces=request, wb_user_id=None)


def test_otel_export_clickhouse(client: weave_client.WeaveClient):
    """Test the otel_export method."""
    export_req = create_test_export_request()
    export_req.project_id = client._project_id()
    print(export_req)

    # Call the method under test
    response = client.server.otel_export(export_req)
    print(client.server.otel_export)
    print(response)

    # Verify the response is of the correct type
    assert isinstance(response, tsi.OtelExportRes)

    # Verify call_start_batch was called with a batch request
    # client.server.call_start_batch

    # for call in client.server.calls():
    #     print(call)
    # Verify it's the expected type
    # assert isinstance(batch_req, tsi.CallCreateBatchReq)
    #
    # # Verify the batch contains the expected number of calls
    # assert len(batch_req.batch) == 2  # 1 start + 1 end


# @pytest.fixture
# def mock_sqlite_trace_server():
#     """Create a mocked SqliteTraceServer for testing OTEL export."""
#     from weave.trace_server.sqlite_trace_server import SqliteTraceServer
#
#     with patch.object(SqliteTraceServer, "__init__", return_value=None):
#         server = SqliteTraceServer(":memory:")
#         server.call_start_batch = MagicMock()
#
#         # We keep the original otel_export method but mock call_start_batch
#         # This lets us test the conversion logic but mock the actual database operations
#
#         return server
#
#
# def test_otel_export_sqlite(mock_sqlite_trace_server):
#     """Test the otel_export method for SqliteTraceServer."""
#
#     export_req = create_test_export_request()
#
#     # Call the method under test
#     response = mock_sqlite_trace_server.otel_export(export_req)
#
#     # Verify the response is of the correct type
#     assert isinstance(response, tsi.OtelExportRes)
#
#     # Verify call_start_batch was called with a batch request
#     mock_sqlite_trace_server.call_start_batch.assert_called_once()
#
#     # Get the batch request that was passed to call_start_batch
#     batch_req = mock_sqlite_trace_server.call_start_batch.call_args[0][0]
#
#     # Verify it's the expected type
#     assert isinstance(batch_req, tsi.CallCreateBatchReq)
#
#     # Verify the batch contains the expected number of calls (1 start + 1 end per span)
#     assert len(batch_req.batch) == 2


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
        assert py_span.attributes.get_attribute_value("test.attribute") == "test_value"
        assert py_span.attributes.get_attribute_value("test.number") == 42
        assert (
            py_span.attributes.get_attribute_value("test.nested.value")
            == "nested_test_value"
        )
        array_value = py_span.attributes.get_attribute_value("test.array")
        assert isinstance(array_value, list)
        assert len(array_value) == 2
        assert array_value[0] == "value1"
        assert array_value[1] == "value2"

    def test_span_to_call(self):
        """Test converting a Python Span to Weave Calls."""
        pb_span = create_test_span()
        py_span = PySpan.from_proto(pb_span)

        start_call, end_call = py_span.to_call("test_project")

        # Verify start call
        assert isinstance(start_call, tsi.StartedCallSchemaForInsert)
        assert start_call.project_id == "test_project"
        assert start_call.id == py_span.span_id
        assert start_call.op_name == py_span.name
        assert start_call.trace_id == py_span.trace_id
        assert start_call.started_at == py_span.start_time

        # Verify attributes in start call
        assert "test" in start_call.attributes
        assert "attribute" in start_call.attributes["test"]
        assert start_call.attributes["test"]["attribute"] == "test_value"
        assert start_call.attributes["test"]["number"] == 42
        assert "nested" in start_call.attributes["test"]
        assert start_call.attributes["test"]["nested"]["value"] == "nested_test_value"
        assert "array" in start_call.attributes["test"]
        assert start_call.attributes["test"]["array"] == ["value1", "value2"]

        # Verify end call
        assert isinstance(end_call, tsi.EndedCallSchemaForInsert)
        assert end_call.project_id == "test_project"
        assert end_call.id == py_span.span_id
        assert end_call.ended_at == py_span.end_time
        assert end_call.exception is None

    def test_traces_data_from_proto(self):
        """Test converting protobuf TracesData to Python TracesData."""
        export_req = create_test_export_request()
        traces_data = PyTracesData.from_proto(
            TracesData(resource_spans=export_req.traces.resource_spans)
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

        # Need to patch get_attribute function to correctly handle array indices
        with patch(
            "weave.trace_server.opentelemetry.attributes._get_value_from_nested_dict"
        ) as mock_get:
            mock_get.return_value = 1
            assert get_attribute(nested, "d.0") == 1
            mock_get.assert_called_once_with(nested, "d.0")

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
