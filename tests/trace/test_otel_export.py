from __future__ import annotations

import contextlib
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
    ExportTraceServiceResponse,
)

import weave
from weave.trace import otel_export
from weave.trace.settings import UserSettings


def _any_value_to_python(value: Any) -> Any:
    if value.HasField("string_value"):
        return value.string_value
    if value.HasField("bool_value"):
        return value.bool_value
    if value.HasField("int_value"):
        return value.int_value
    if value.HasField("double_value"):
        return value.double_value
    if value.HasField("array_value"):
        return [_any_value_to_python(item) for item in value.array_value.values]
    return None


class _OTLPReceiver:
    def __init__(self) -> None:
        self.requests: list[bytes] = []

        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                content_length = int(self.headers.get("Content-Length", "0"))
                outer.requests.append(self.rfile.read(content_length))
                response = ExportTraceServiceResponse().SerializeToString()
                self.send_response(200)
                self.send_header("Content-Type", "application/x-protobuf")
                self.send_header("Content-Length", str(len(response)))
                self.end_headers()
                self.wfile.write(response)

            def log_message(self, format: str, *args: Any) -> None:
                return None

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(
            target=self._server.serve_forever, daemon=True
        )

    @property
    def endpoint(self) -> str:
        host, port = self._server.server_address
        return f"http://{host}:{port}/v1/traces"

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)

    def export_requests(self) -> list[ExportTraceServiceRequest]:
        requests = []
        for body in self.requests:
            request = ExportTraceServiceRequest()
            request.ParseFromString(body)
            requests.append(request)
        return requests


@contextlib.contextmanager
def otlp_receiver() -> Any:
    receiver = _OTLPReceiver()
    receiver.start()
    try:
        yield receiver
    finally:
        receiver.stop()


def _flatten_exported_spans(
    export_requests: list[ExportTraceServiceRequest],
) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    for request in export_requests:
        for resource_spans in request.resource_spans:
            resource_attributes = {
                attribute.key: _any_value_to_python(attribute.value)
                for attribute in resource_spans.resource.attributes
            }
            for scope_spans in resource_spans.scope_spans:
                for span in scope_spans.spans:
                    spans.append(
                        {
                            "name": span.name,
                            "span_id": span.span_id.hex(),
                            "parent_span_id": span.parent_span_id.hex(),
                            "resource_attributes": resource_attributes,
                            "attributes": {
                                attribute.key: _any_value_to_python(attribute.value)
                                for attribute in span.attributes
                            },
                        }
                    )
    return spans


@pytest.mark.skip_clickhouse_client
def test_export_otel_routes_calls_to_otlp(client_creator, monkeypatch) -> None:
    @weave.op(name="openai.chat.completions.create")
    def chat_completion(model: str, prompt: str) -> dict[str, Any]:
        return {
            "id": "resp_123",
            "model": model,
            "choices": [
                {
                    "message": {"role": "assistant", "content": "Boston is in Massachusetts."},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 11,
                "completion_tokens": 7,
                "total_tokens": 18,
            },
        }

    @weave.op(name="workflow")
    def workflow() -> dict[str, Any]:
        return chat_completion(model="gpt-4o-mini", prompt="Where is Boston?")

    with otlp_receiver() as receiver:
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", receiver.endpoint)

        with client_creator(
            settings=UserSettings(export_otel=True, print_call_link=False)
        ) as client:
            workflow()
            client.finish(use_progress_bar=False)
            assert list(client.get_calls()) == []
            project_id = client.project_id

    spans = _flatten_exported_spans(receiver.export_requests())
    assert len(spans) == 2

    spans_by_name = {span["name"]: span for span in spans}
    workflow_span = spans_by_name["workflow"]
    chat_span = spans_by_name["openai.chat.completions.create"]

    assert chat_span["parent_span_id"] == workflow_span["span_id"]
    assert chat_span["resource_attributes"]["service.name"] == "weave"
    assert chat_span["resource_attributes"]["weave.project_id"] == project_id

    attributes = chat_span["attributes"]
    assert attributes["gen_ai.provider.name"] == "openai"
    assert attributes["gen_ai.operation.name"] == "chat"
    assert attributes["gen_ai.request.model"] == "gpt-4o-mini"
    assert attributes["gen_ai.response.id"] == "resp_123"
    assert attributes["gen_ai.response.finish_reasons"] == ["stop"]
    assert attributes["gen_ai.usage.prompt_tokens"] == 11
    assert attributes["gen_ai.usage.completion_tokens"] == 7
    assert attributes["gen_ai.usage.total_tokens"] == 18
    assert "Where is Boston?" in attributes["gen_ai.prompt"]
    assert "Boston is in Massachusetts." in attributes["gen_ai.completion"]


def test_export_otel_requires_otel_extra(monkeypatch) -> None:
    monkeypatch.setattr(otel_export, "_OTEL_DEPS_MISSING", True)

    with pytest.raises(ImportError, match=r"weave\[otel\]"):
        otel_export.OTelCallExporter("entity", "project", "project-id")
