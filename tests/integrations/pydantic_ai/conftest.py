import contextlib
from unittest.mock import patch

import pytest
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
)
from opentelemetry.proto.common.v1.common_pb2 import (
    KeyValue,
    InstrumentationScope,
)
from opentelemetry.proto.resource.v1.resource_pb2 import Resource
from opentelemetry.proto.trace.v1.trace_pb2 import (
    ResourceSpans,
    ScopeSpans,
    Span,
)
from opentelemetry.sdk.trace.export import SpanExportResult

from weave.integrations.pydantic_ai.utils import PydanticAISpanExporter
from weave.trace_server import trace_server_interface as tsi


class MockOTLPExporter:
    """Mock OTLP exporter that captures spans and forwards to test server"""

    def __init__(self):
        self.exported_spans = []

    def export(self, spans):
        """Store spans for inspection"""
        self.exported_spans.extend(spans)
        return SpanExportResult.SUCCESS

    def shutdown(self):
        pass

    def force_flush(self, timeout_millis=30000):
        return True


def convert_readable_span_to_proto_span(readable_span):
    """Convert a ReadableSpan object to a protobuf Span object"""
    proto_span = Span()
    proto_span.name = readable_span.name

    # Convert hex trace_id and span_id to bytes
    if hasattr(readable_span.context, "trace_id"):
        # Handle trace_id as hex string or int
        trace_id = readable_span.context.trace_id
        if isinstance(trace_id, str):
            proto_span.trace_id = bytes.fromhex(trace_id)
        else:
            # Convert int to 16-byte array
            proto_span.trace_id = trace_id.to_bytes(16, byteorder="big")

    if hasattr(readable_span.context, "span_id"):
        # Handle span_id as hex string or int
        span_id = readable_span.context.span_id
        if isinstance(span_id, str):
            proto_span.span_id = bytes.fromhex(span_id)
        else:
            # Convert int to 8-byte array
            proto_span.span_id = span_id.to_bytes(8, byteorder="big")

    # Convert timestamps
    proto_span.start_time_unix_nano = readable_span.start_time
    proto_span.end_time_unix_nano = readable_span.end_time

    # Set span kind
    if hasattr(readable_span, "kind"):
        span_kind = getattr(readable_span, "kind")
        # If it's an enum, get its value
        if hasattr(span_kind, "value"):
            proto_span.kind = span_kind.value
        else:
            proto_span.kind = span_kind
    else:
        proto_span.kind = 1  # Default to INTERNAL

    # Convert attributes
    for key, value in readable_span.attributes.items():
        kv = KeyValue()
        kv.key = key

        # Convert the value based on its type
        if isinstance(value, str):
            kv.value.string_value = value
        elif isinstance(value, int):
            kv.value.int_value = value
        elif isinstance(value, float):
            kv.value.double_value = value
        elif isinstance(value, bool):
            kv.value.bool_value = value
        elif isinstance(value, (list, tuple)):
            # Create array value
            array_value = kv.value.array_value
            for item in value:
                val = array_value.values.add()
                if isinstance(item, str):
                    val.string_value = item
                elif isinstance(item, int):
                    val.int_value = item
                elif isinstance(item, float):
                    val.double_value = item
                elif isinstance(item, bool):
                    val.bool_value = item

        proto_span.attributes.append(kv)

    # Set status
    if hasattr(readable_span, "status"):
        status_code = getattr(readable_span.status, "code", 0)
        # If status_code is an enum, get its value
        if hasattr(status_code, "value"):
            proto_span.status.code = status_code.value
        else:
            proto_span.status.code = status_code

        # Make sure we're passing a string for the message
        status_msg = getattr(readable_span.status, "description", "")
        if status_msg is None:
            status_msg = ""
        proto_span.status.message = str(status_msg)

    return proto_span


@pytest.fixture
def pydantic_ai_client(client, monkeypatch):
    """
    Fixture that provides a client with mocked PydanticAISpanExporter for testing.

    This avoids making real OTLP HTTP requests during tests while preserving
    the original processing logic of the PydanticAISpanExporter.
    """
    mock_otlp_exporter = MockOTLPExporter()

    # Patch the functions we need to mock
    with patch(
        "weave.integrations.pydantic_ai.utils.get_otlp_headers_from_weave_context"
    ) as mock_get_headers:
        # Return mock headers for authentication
        mock_get_headers.return_value = {
            "Authorization": "test_auth_token",
            "project_id": "test/test-project",
        }

        # Patch the OTLPSpanExporter creation in PydanticAISpanExporter.__init__
        original_init = PydanticAISpanExporter.__init__

        def patched_init(self):
            # Skip the real OTLP exporter creation and use our mock
            self._otlp_exporter = mock_otlp_exporter

        monkeypatch.setattr(PydanticAISpanExporter, "__init__", patched_init)

        # Add process_spans method to manually convert and send spans to the server
        def process_spans(project_id=None):
            if not project_id:
                project_id = client._project_id()

            # If there are no spans, nothing to process
            if not mock_otlp_exporter.exported_spans:
                return

            # Create instrumentation scope
            scope = InstrumentationScope()
            scope.name = "pydantic_ai_test"
            scope.version = "1.0.0"

            # Create scope spans
            scope_spans = ScopeSpans()
            scope_spans.scope.CopyFrom(scope)

            # Convert ReadableSpan objects to protobuf Span objects and add them
            for readable_span in mock_otlp_exporter.exported_spans:
                proto_span = convert_readable_span_to_proto_span(readable_span)
                scope_spans.spans.append(proto_span)

            # Create resource with attributes
            resource = Resource()
            service_kv = KeyValue()
            service_kv.key = "service.name"
            service_kv.value.string_value = "pydantic_ai_test_service"
            resource.attributes.append(service_kv)

            # Create resource spans
            resource_spans = ResourceSpans()
            resource_spans.resource.CopyFrom(resource)
            resource_spans.scope_spans.append(scope_spans)

            # Create export request
            request = ExportTraceServiceRequest()
            request.resource_spans.append(resource_spans)

            # Create the OtelExportReq
            export_req = tsi.OtelExportReq(
                project_id=project_id, traces=request, wb_user_id=None
            )

            # Export the traces
            client.server.otel_export(export_req)

            # Clear the spans after processing
            mock_otlp_exporter.exported_spans = []

        # Attach the method to the client for use in tests
        client.process_otel_spans = process_spans

        yield client

        # Restore the original init method
        monkeypatch.setattr(PydanticAISpanExporter, "__init__", original_init)


@pytest.fixture
def pydantic_ai_client_creator(request, monkeypatch):
    """
    Fixture that provides a client creator function for pydantic-ai testing
    """

    @contextlib.contextmanager
    def create_client(autopatch_settings=None, global_attributes=None):
        from tests.conftest import create_client as original_create_client

        # Create a mock OTLP exporter
        mock_otlp_exporter = MockOTLPExporter()

        # Patch get_otlp_headers_from_weave_context
        with patch(
            "weave.integrations.pydantic_ai.utils.get_otlp_headers_from_weave_context"
        ) as mock_get_headers:
            mock_get_headers.return_value = {
                "Authorization": "test_auth_token",
                "project_id": "test/test-project",
            }

            # Patch the PydanticAISpanExporter.__init__
            original_init = PydanticAISpanExporter.__init__

            def patched_init(self):
                # Skip the real OTLP exporter creation and use our mock
                self._otlp_exporter = mock_otlp_exporter

            monkeypatch.setattr(PydanticAISpanExporter, "__init__", patched_init)

            # Create the client using the original creator
            inited_client = original_create_client(
                request, autopatch_settings, global_attributes
            )
            client = inited_client.client

            # Add process_spans method
            def process_spans(project_id=None):
                if not project_id:
                    project_id = client._project_id()

                # If there are no spans, nothing to process
                if not mock_otlp_exporter.exported_spans:
                    return

                # Create instrumentation scope
                scope = InstrumentationScope()
                scope.name = "pydantic_ai_test"
                scope.version = "1.0.0"

                # Create scope spans
                scope_spans = ScopeSpans()
                scope_spans.scope.CopyFrom(scope)

                # Convert ReadableSpan objects to protobuf Span objects and add them
                for readable_span in mock_otlp_exporter.exported_spans:
                    proto_span = convert_readable_span_to_proto_span(readable_span)
                    scope_spans.spans.append(proto_span)

                # Create resource with attributes
                resource = Resource()
                service_kv = KeyValue()
                service_kv.key = "service.name"
                service_kv.value.string_value = "pydantic_ai_test_service"
                resource.attributes.append(service_kv)

                # Create resource spans
                resource_spans = ResourceSpans()
                resource_spans.resource.CopyFrom(resource)
                resource_spans.scope_spans.append(scope_spans)

                # Create export request
                request = ExportTraceServiceRequest()
                request.resource_spans.append(resource_spans)

                # Create the OtelExportReq
                export_req = tsi.OtelExportReq(
                    project_id=project_id, traces=request, wb_user_id=None
                )

                # Export the traces
                client.server.otel_export(export_req)

                # Clear the spans after processing
                mock_otlp_exporter.exported_spans = []

            # Attach the method to the client for use in tests
            client.process_otel_spans = process_spans

            try:
                yield client
            finally:
                inited_client.reset()
                # Restore the original init method
                monkeypatch.setattr(PydanticAISpanExporter, "__init__", original_init)

    return create_client
