# PydanticAI Integration Testing

## Overview

This directory contains tests for the PydanticAI integration with Weave. The integration uses OpenTelemetry (OTEL) to send spans to the Weave trace server, which creates unique testing challenges.

## The Testing Challenge

Testing the PydanticAI integration has several challenges:

1. **Auto-patching at Client Creation**: The PydanticAI integration is [auto-patched when the Weave client is created](../../../tests/conftest.py#L603-L612), which means it tries to create a `PydanticAISpanExporter` immediately. This happens in the [create_client function](../../../tests/conftest.py#L385-L395) that calls `autopatch.autopatch()`.

2. **Authentication Requirements**: The [`PydanticAISpanExporter` tries to send OTEL spans](../../../weave/integrations/pydantic_ai/utils.py#L151-L152) to an external trace server endpoint, requiring W&B API authentication credentials. The authentication issue occurs in [get_otlp_headers_from_weave_context](../../../weave/integrations/pydantic_ai/utils.py#L130-L140) which needs a valid API key that is not available in the test environment.

3. **Span Format Mismatch**: The test trace server expects a different format than what the OpenTelemetry SDK provides. The SDK uses `ReadableSpan` objects, but the trace server needs [protobuf Span objects](../../../tests/trace_server/test_opentelemetry.py#L53-L97).

4. **Client vs. Tracer**: Unlike other integrations, the spans are sent directly to the trace server, not through the Weave client. The [OTLPSpanExporter](../../../weave/integrations/pydantic_ai/utils.py#L152) makes HTTP calls to the trace server.

## Solution Approach

Our testing approach is inspired by:
- [`tests/trace_server/test_opentelemetry.py`](../../../tests/trace_server/test_opentelemetry.py): How to create and convert OTEL spans
- [`tests/trace_server/test_remote_http_trace_server.py`](../../../tests/trace_server/test_remote_http_trace_server.py): How to intercept network requests
- [`tests/conftest.py`](../../../tests/conftest.py): How to create test clients and fixtures

### Key Components of the Solution

1. **Custom Client Creator Fixture**: We created a special [`pydantic_ai_client_creator` fixture](./conftest.py#L96-L176) that patches the necessary components *before* the client is created:

   ```python
   @pytest.fixture
   def pydantic_ai_client_creator(request, monkeypatch):
       @contextlib.contextmanager
       def create_client(autopatch_settings=None, global_attributes=None):
           # Mock components before client creation
           ...
           yield client
   ```

2. **Mock OTLP Exporter**: We created a [`MockOTLPExporter`](./conftest.py#L14-L29) that captures spans instead of sending them to the real trace server:

   ```python
   class MockOTLPExporter:
       def __init__(self):
           self.exported_spans = []

       def export(self, spans):
           self.exported_spans.extend(spans)
           return SpanExportResult.SUCCESS
   ```

3. **Span Conversion**: We implemented a function to [convert SDK `ReadableSpan` objects to protobuf `Span` objects](./conftest.py#L32-L91):

   ```python
   def convert_readable_span_to_proto_span(readable_span):
       proto_span = Span()
       # Convert span data from SDK format to protobuf format
       ...
       return proto_span
   ```

4. **Direct Export to Trace Server**: We added a [`process_otel_spans` method](./conftest.py#L132-L171) to construct a valid `OtelExportReq` and send it directly to the test trace server, similar to how it's done in [test_otel_export_clickhouse](../../../tests/trace_server/test_opentelemetry.py#L144-L147):

   ```python
   def process_spans(project_id=None):
       # Create an OTEL export request from captured spans
       ...
       # Send directly to the test trace server
       client.server.otel_export(export_req)
   ```

## Using the Testing Utilities

To test the PydanticAI integration:

1. Use the `pydantic_ai_client_creator` fixture in your test as shown in [test_pydantic_ai_agent_patching](./test_pydantic_ai_sdk.py#L13-L16):

   ```python
   def test_pydantic_ai_agent_patching(pydantic_ai_client_creator):
       with pydantic_ai_client_creator() as client:
           # Your test code here
   ```

2. After executing operations that would generate OTEL spans, call [`process_otel_spans`](./test_pydantic_ai_sdk.py#L31) to process and export them:

   ```python
   # Run a query that would generate spans
   result = agent.run_sync("What is the capital of France?")
   
   # Process OTEL spans into the trace server
   client.process_otel_spans()
   
   # Now you can check that the traces were recorded
   res = client.server.calls_query(...)
   ```

## Common Issues and Solutions

1. **Type Mismatch Errors**: The protobuf format requires careful type handling, especially for [enums](./conftest.py#L54-L61) and [message fields](./conftest.py#L87-L91).

2. **Authentication Errors**: We bypass authentication by [mocking the `get_otlp_headers_from_weave_context` function](./conftest.py#L108-L115).

3. **Span Conversion Issues**: Converting between SDK and protobuf formats requires handling [different attribute types](./conftest.py#L68-L85).

## Future Improvements

Potential enhancements to this testing approach:

1. Add more robust error handling for different span attribute types
2. Improve debugging capabilities with detailed logging
3. Create utilities to make creating test spans easier, similar to [`create_test_span`](../../../tests/trace_server/test_opentelemetry.py#L53-L97)
4. Add more comprehensive attribute conversion for complex data types 