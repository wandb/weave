import hashlib
import json
import uuid
from binascii import hexlify
from datetime import datetime
from typing import Any

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
    project_id = client._project_id()
    export_req.project_id = project_id

    # Export the otel traces
    response = client.server.otel_export(export_req)
    # Verify the response is of the correct type
    assert isinstance(response, tsi.OtelExportRes)

    # Query the calls
    res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=project_id,
        )
    )
    # Verify that the start and end calls were merged into a single call
    assert len(res.calls) == 1

    call = res.calls[0]
    export_span = export_req.traces.resource_spans[0].scope_spans[0].spans[0]
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

        # Verify otel_span is included in attributes
        assert "otel_span" in start_call.attributes
        assert start_call.attributes["otel_span"]["name"] == py_span.name
        assert (
            start_call.attributes["otel_span"]["context"]["trace_id"]
            == py_span.trace_id
        )
        assert (
            start_call.attributes["otel_span"]["context"]["span_id"] == py_span.span_id
        )

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
        from datetime import datetime

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
