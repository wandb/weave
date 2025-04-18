import json
import uuid
from binascii import hexlify
from datetime import datetime
from unittest.mock import patch

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
from weave.trace_server.opentelemetry.attributes import (
    Attributes,
    AttributesFactory,
    GenericAttributes,
    OpenInferenceAttributes,
    OpenTelemetryAttributes,
    convert_numeric_keys_to_list,
    expand_attributes,
    flatten_attributes,
    get_attribute,
    to_json_serializable,
    unflatten_key_values,
)
from weave.trace_server.opentelemetry.helpers import (
    capture_parts,
    shorten_name,
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

    call_attributes = Attributes(_attributes=call.attributes)
    for kv in export_span.attributes:
        key = kv.key
        value = kv.value
        if value.HasField("string_value"):
            assert call_attributes.get_attribute_value(key) == value.string_value
        elif value.HasField("int_value"):
            assert call_attributes.get_attribute_value(key) == value.int_value
        elif value.HasField("double_value"):
            assert call_attributes.get_attribute_value(key) == value.double_value
        elif value.HasField("bool_value"):
            assert call_attributes.get_attribute_value(key) == value.bool_value
        elif value.HasField("array_value"):
            # Handle array values
            array_values = [v.string_value for v in value.array_value.values]
            assert call_attributes.get_attribute_value(key) == array_values

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


class TestSemanticConventionParsing:
    """Test the semantic convention parsing functionality in attributes.py."""

    def test_openinference_attributes_extraction(self):
        """Test extracting attributes from OpenInference attributes."""
        from openinference.semconv.trace import SpanAttributes as OISpanAttr

        # Create attribute dictionary with OpenInference attributes
        attributes = {
            "openinference": True,
            OISpanAttr.LLM_SYSTEM: "This is a system prompt",
            OISpanAttr.LLM_PROVIDER: "test-provider",
            OISpanAttr.LLM_MODEL_NAME: "test-model",
            OISpanAttr.OPENINFERENCE_SPAN_KIND: "llm",
            OISpanAttr.LLM_INVOCATION_PARAMETERS: json.dumps(
                {"temperature": 0.7, "max_tokens": 100}
            ),
        }

        # Create OpenInference attributes object
        oi_attrs = OpenInferenceAttributes(attributes)

        # Test get_weave_attributes
        extracted = oi_attrs.get_weave_attributes()
        assert extracted["system"] == "This is a system prompt"
        assert extracted["provider"] == "test-provider"
        assert extracted["model"] == "test-model"
        assert extracted["kind"] == "llm"
        assert extracted["temperature"] == "0.7"
        assert extracted["max_tokens"] == "100"

    def test_openinference_inputs_extraction(self):
        """Test extracting inputs from OpenInference attributes."""
        from openinference.semconv.trace import SpanAttributes as OISpanAttr

        # Create attribute dictionary with OpenInference input messages
        input_messages = {"0": {"role": "user", "content": "What is machine learning?"}}
        attributes = {
            "openinference": True,
            OISpanAttr.LLM_INPUT_MESSAGES: input_messages,
        }

        # Create OpenInference attributes object
        oi_attrs = OpenInferenceAttributes(attributes)

        # Test get_weave_inputs
        inputs = oi_attrs.get_weave_inputs()
        assert inputs == {"role_0": "user", "content_0": "What is machine learning?"}

        # Test with multiple messages
        input_messages_multiple = {
            "0": {"role": "system", "content": "You are an assistant"},
            "1": {"role": "user", "content": "What is machine learning?"},
        }
        attributes = {
            "openinference": True,
            OISpanAttr.LLM_INPUT_MESSAGES: input_messages_multiple,
        }
        oi_attrs = OpenInferenceAttributes(attributes)
        inputs = oi_attrs.get_weave_inputs()
        assert inputs == {
            "role_0": "system",
            "content_0": "You are an assistant",
            "role_1": "user",
            "content_1": "What is machine learning?",
        }

    def test_openinference_outputs_extraction(self):
        """Test extracting outputs from OpenInference attributes."""
        from openinference.semconv.trace import SpanAttributes as OISpanAttr

        # Create attribute dictionary with OpenInference output messages
        output_messages = {
            "0": {
                "role": "assistant",
                "content": "Machine learning is a field of AI...",
            }
        }
        attributes = {
            "openinference": True,
            OISpanAttr.LLM_OUTPUT_MESSAGES: output_messages,
        }

        # Create OpenInference attributes object
        oi_attrs = OpenInferenceAttributes(attributes)

        # Test get_weave_outputs
        outputs = oi_attrs.get_weave_outputs()
        assert outputs == {
            "role_0": "assistant",
            "content_0": "Machine learning is a field of AI...",
        }

    def test_openinference_usage_extraction(self):
        """Test extracting usage from OpenInference attributes."""
        from openinference.semconv.trace import SpanAttributes as OISpanAttr

        # Create attribute dictionary with OpenInference token counts
        attributes = {
            "openinference": True,
            OISpanAttr.LLM_TOKEN_COUNT_PROMPT: 10,
            OISpanAttr.LLM_TOKEN_COUNT_COMPLETION: 20,
            OISpanAttr.LLM_TOKEN_COUNT_TOTAL: 30,
        }

        # Create OpenInference attributes object
        oi_attrs = OpenInferenceAttributes(attributes)

        # Test get_weave_usage
        usage = oi_attrs.get_weave_usage()
        assert usage.get("prompt_tokens") == 10
        assert usage.get("completion_tokens") == 20
        assert usage.get("total_tokens") == 30

    def test_opentelemetry_attributes_extraction(self):
        """Test extracting attributes from OpenTelemetry attributes."""
        from opentelemetry.semconv_ai import SpanAttributes as OTSpanAttr

        # Create attribute dictionary with OpenTelemetry attributes
        attributes = {
            "gen_ai": True,
            OTSpanAttr.LLM_SYSTEM: "You are a helpful assistant",
            OTSpanAttr.LLM_REQUEST_MAX_TOKENS: 150,
            OTSpanAttr.TRACELOOP_SPAN_KIND: "llm",
            OTSpanAttr.LLM_RESPONSE_MODEL: "gpt-4",
        }

        # Create OpenTelemetry attributes object
        ot_attrs = OpenTelemetryAttributes(attributes)

        # Test get_weave_attributes
        extracted = ot_attrs.get_weave_attributes()
        assert extracted["system"] == "You are a helpful assistant"
        assert extracted["max_tokens"] == 150
        assert extracted["kind"] == "llm"
        assert extracted["model"] == "gpt-4"

    def test_opentelemetry_inputs_extraction(self):
        """Test extracting inputs from OpenTelemetry attributes."""
        from opentelemetry.semconv_ai import SpanAttributes as OTSpanAttr

        # Create attribute dictionary with OpenTelemetry prompts
        prompts = {"0": {"role": "user", "content": "Tell me about quantum computing"}}
        attributes = {
            "gen_ai": True,
            OTSpanAttr.LLM_PROMPTS: prompts,
        }

        # Create OpenTelemetry attributes object
        ot_attrs = OpenTelemetryAttributes(attributes)

        # Test get_weave_inputs
        inputs = ot_attrs.get_weave_inputs()
        assert inputs == {
            "0": {"role": "user", "content": "Tell me about quantum computing"}
        }

        # Test with multiple prompts
        prompts_multiple = {
            "0": {"role": "system", "content": "You are an expert in quantum physics"},
            "1": {"role": "user", "content": "Tell me about quantum computing"},
        }
        attributes = {
            "gen_ai": True,
            OTSpanAttr.LLM_PROMPTS: prompts_multiple,
        }
        ot_attrs = OpenTelemetryAttributes(attributes)
        inputs = ot_attrs.get_weave_inputs()
        assert inputs == prompts_multiple

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
        attributes = {
            "gen_ai": True,
            OTSpanAttr.LLM_COMPLETIONS: completions,
        }

        # Create OpenTelemetry attributes object
        ot_attrs = OpenTelemetryAttributes(attributes)

        # Test get_weave_outputs
        outputs = ot_attrs.get_weave_outputs()
        assert outputs == {
            "0": {
                "role": "assistant",
                "content": "Quantum computing uses quantum mechanics...",
            }
        }

    def test_opentelemetry_usage_extraction(self):
        """Test extracting usage from OpenTelemetry attributes."""
        from opentelemetry.semconv_ai import SpanAttributes as OTSpanAttr

        # Create attribute dictionary with OpenTelemetry token usage
        attributes = {
            "gen_ai": True,
            OTSpanAttr.LLM_USAGE_PROMPT_TOKENS: 15,
            OTSpanAttr.LLM_USAGE_COMPLETION_TOKENS: 25,
            OTSpanAttr.LLM_USAGE_TOTAL_TOKENS: 40,
        }

        # Create OpenTelemetry attributes object
        ot_attrs = OpenTelemetryAttributes(attributes)

        # Test get_weave_usage
        usage = ot_attrs.get_weave_usage()
        assert usage.get("prompt_tokens") == 15
        assert usage.get("completion_tokens") == 25
        assert usage.get("total_tokens") == 40

    def test_attributes_factory(self):
        """Test the AttributesFactory for creating the correct attributes object."""
        factory = AttributesFactory()

        # Test OpenInference detection
        oi_key_value = KeyValue(key="openinference", value=AnyValue(bool_value=True))
        oi_attrs = factory.from_proto([oi_key_value])
        assert isinstance(oi_attrs, OpenInferenceAttributes)

        # Test OpenTelemetry detection
        ot_key_value = KeyValue(key="gen_ai", value=AnyValue(bool_value=True))
        ot_attrs = factory.from_proto([ot_key_value])
        assert isinstance(ot_attrs, OpenTelemetryAttributes)

        # Test generic attributes (no specific convention)
        generic_key_value = KeyValue(
            key="some_key", value=AnyValue(string_value="some_value")
        )
        generic_attrs = factory.from_proto([generic_key_value])
        assert isinstance(generic_attrs, GenericAttributes)


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
        assert shorten_name("short", 10) == "short..."

        # Test a string longer than max_len with no delimiters
        long_name = "abcdefghijklmnopqrstuvwxyz"
        assert shorten_name(long_name, 10) == "abcdefg..."

    def test_shorten_name_with_delimiters(self):
        """Test shortening a name with delimiters."""
        # Test with a single delimiter
        assert shorten_name("part1.part2", 10) == "part1...."

        # Test with multiple delimiters where it fits
        assert shorten_name("a.b.c", 10) == "a.b.c"

        # Test with multiple delimiters where it needs truncation
        assert shorten_name("part1.part2.part3", 12) == "part1...."

    def test_shorten_name_first_part_too_long(self):
        """Test shortening a name where first part is already too long."""
        # First part already exceeds max_len
        assert shorten_name("verylongfirstpart.second", 10) == "verylon..."

    def test_shorten_name_custom_abbreviation(self):
        """Test shortening a name with custom abbreviation."""
        assert shorten_name("part1.part2.part3", 10, "***") == "part1.***"

        # Test with empty abbreviation
        assert shorten_name("part1.part2.part3", 10, "") == "part1."

    def test_shorten_name_different_delimiters(self):
        """Test shortening a name with different types of delimiters."""
        # Test with a space delimiter
        assert shorten_name("word1 word2 word3", 12) == "word1 ..."

        # Test with a slash delimiter
        assert shorten_name("path/to/file", 8) == "path/..."

        # Test with mixed delimiters
        assert shorten_name("user.name@example.com", 12) == "user...."

        # Test with a delimiter not in the default list
        # Note: This will be treated as having no delimiters since '-' is not in the default list
        assert shorten_name("part1-part2-part3", 10) == "part1-p..."

        # Test with a question mark delimiter
        assert shorten_name("api/endpoint?param=value", 15) == "api/..."

    def test_long_url_regression(self):
        # Test for a modified version of the URL which caused failed traces due to op_name length
        actual = shorten_name(
            "GET /api/trpc/lambda/organization.getActiveOrganization,account.getSubscription,checkout.getPrices,user.getUserToolGroupsConfig?batch=1&input=%8A%220%22%3Z%8A%22json%22%3Znull%2P%22meta%22%3Z%8A%22values%22%3Z%5X%22undefined%22%5D%8D%8D%2P%221%22%3Z%8A%22json%22%3Znull%2P%22meta%22%3Z%8A%22values%22%3Z%5X%22undefined%22%5D%8D%8D%2P%222%22%3Z%8A%22json%22%3Znull%2P%22meta%22%3Z%8A%22values%22%3Z%5X%22undefined%22%5D%8D%8D%2P%223%22%3Z%8A%22json%22%3Znull%2P%22meta%22%3Z%8A%22values%22%3Z%5X%22undefined%22%5D%8D%8D%8D",
            128,
        )
        expected = "GET /api/trpc/lambda/organization.getActiveOrganization,account.getSubscription,checkout.getPrices,user.getUserToolGroupsConfig..."
        assert actual == expected
