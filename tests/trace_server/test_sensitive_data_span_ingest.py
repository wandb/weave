"""End-to-end PII redaction on the agents OTel ingest path.

Runs the real ``genai_otel_export`` against ClickHouse via the ``ch_server``
fixture and reads the stored span details back, proving the ``pii-v1`` policy
reaches ``raw_span_dump`` and the attribute-derived columns, and that an
explicit ``off`` policy stores values unchanged.
"""

from __future__ import annotations

import json

from opentelemetry.proto.common.v1.common_pb2 import InstrumentationScope, KeyValue
from opentelemetry.proto.resource.v1.resource_pb2 import Resource as PbResource
from opentelemetry.proto.trace.v1.trace_pb2 import ResourceSpans, ScopeSpans
from opentelemetry.proto.trace.v1.trace_pb2 import Span as PbSpan

from tests.trace_server.helpers import make_project_id
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.agents.types import AgentSpansQueryReq, GenAIOTelExportReq
from weave.trace_server.sensitive_data.policy import SensitiveDataPolicy

_NOW_NS = 1_767_225_600_000_000_000
_PII_ATTR_VALUE = "Email ada@example.com"
_PII_STATUS_MESSAGE = "card 4111 1111 1111 1111"
_PII_RESOURCE_VALUE = "call (415) 555-2671"
_PII_CONVERSATION_NAME = "chat with ada@example.com"

# One PII value per derived content column, so every column is observed.
_PII_CONTENT_ATTRS = {
    "gen_ai.conversation.name": _PII_CONVERSATION_NAME,
    "gen_ai.system_instructions": json.dumps(["obey ada@example.com"]),
    "gen_ai.output.messages": json.dumps(
        [
            {
                "role": "assistant",
                "content": "reply to ada@example.com",
                "finish_reason": "stop",
            },
            {
                "role": "assistant",
                "parts": [{"type": "reasoning", "content": "think 123-45-6789"}],
                "finish_reason": "stop",
            },
        ]
    ),
    "gen_ai.tool.call.arguments": json.dumps({"query": "email ada@example.com"}),
    "gen_ai.tool.call.result": json.dumps({"answer": "call (415) 555-2671"}),
    "gen_ai.tool.definitions": json.dumps(
        [{"name": "lookup", "description": "for 4111 1111 1111 1111"}]
    ),
    "weave.compaction.summary": "card 4111 1111 1111 1111",
}


def _pii_proto_span(span_id: bytes) -> PbSpan:
    span = PbSpan()
    span.name = "agents_pii_ingest"
    span.trace_id = (77).to_bytes(16, "big")
    span.span_id = span_id
    span.start_time_unix_nano = _NOW_NS
    span.end_time_unix_nano = _NOW_NS + 1_000_000_000
    span.kind = 1  # CLIENT
    kv = KeyValue()
    kv.key = "gen_ai.prompt"
    kv.value.string_value = _PII_ATTR_VALUE
    span.attributes.append(kv)
    for key, value in _PII_CONTENT_ATTRS.items():
        item = KeyValue()
        item.key = key
        item.value.string_value = value
        span.attributes.append(item)
    span.status.code = 2  # ERROR, so the status message persists
    span.status.message = _PII_STATUS_MESSAGE
    return span


def _export_req(
    project_id: str,
    span: PbSpan,
    policy: SensitiveDataPolicy,
) -> GenAIOTelExportReq:
    scope = InstrumentationScope()
    scope.name = "test_instrumentation"
    scope_spans = ScopeSpans()
    scope_spans.scope.CopyFrom(scope)
    scope_spans.spans.append(span)
    resource = PbResource()
    kv = KeyValue()
    kv.key = "service.owner"
    kv.value.string_value = _PII_RESOURCE_VALUE
    resource.attributes.append(kv)
    resource_spans = ResourceSpans()
    resource_spans.resource.CopyFrom(resource)
    resource_spans.scope_spans.append(scope_spans)
    return GenAIOTelExportReq(
        processed_spans=[
            tsi.ProcessedResourceSpans(
                entity="test-entity",
                project="test-project",
                run_id=None,
                resource_spans=resource_spans,
            )
        ],
        project_id=project_id,
        wb_user_id="test-user",
        sensitive_data_policy=policy,
    )


def _stored_span_details(ch_server, project_id: str):
    res = ch_server.agent_spans_query(
        AgentSpansQueryReq(project_id=project_id, include_details=True)
    )
    assert len(res.spans) == 1
    return res.spans[0]


def test_pii_policy_redacts_stored_span_details(ch_server) -> None:
    project_id = make_project_id("span_pii_on")

    res = ch_server.genai_otel_export(
        _export_req(
            project_id,
            _pii_proto_span(b"\x41" * 8),
            SensitiveDataPolicy.PII_V1,
        )
    )

    assert res.rejected_spans == 0
    row = _stored_span_details(ch_server, project_id)
    dump = json.loads(row.raw_span_dump)
    assert dump["attributes"]["gen_ai"]["prompt"] == "Email <EMAIL_ADDRESS>"
    assert dump["resource"]["attributes"] == {
        "service": {"owner": "call <PHONE_NUMBER>"}
    }
    assert dump["status"]["message"] == "card <CREDIT_CARD>"
    assert row.status_message == "card <CREDIT_CARD>"
    assert row.conversation_name == "chat with <EMAIL_ADDRESS>"
    assert row.system_instructions == ["obey <EMAIL_ADDRESS>"]
    assert row.output_messages[0].content == "reply to <EMAIL_ADDRESS>"
    assert row.reasoning_content == "think <US_SSN>"
    assert row.tool_call_arguments == '{"query": "email <EMAIL_ADDRESS>"}'
    assert row.tool_call_result == '{"answer": "call <PHONE_NUMBER>"}'
    assert (
        row.tool_definitions
        == '[{"name": "lookup", "description": "for <CREDIT_CARD>"}]'
    )
    assert row.compaction_summary == "card <CREDIT_CARD>"


def test_off_policy_stores_span_values_unchanged(ch_server) -> None:
    project_id = make_project_id("span_pii_off")

    res = ch_server.genai_otel_export(
        _export_req(
            project_id,
            _pii_proto_span(b"\x42" * 8),
            SensitiveDataPolicy.OFF,
        )
    )

    assert res.rejected_spans == 0
    row = _stored_span_details(ch_server, project_id)
    dump = json.loads(row.raw_span_dump)
    assert dump["attributes"]["gen_ai"]["prompt"] == _PII_ATTR_VALUE
    assert dump["status"]["message"] == _PII_STATUS_MESSAGE
    assert dump["resource"]["attributes"] == {"service": {"owner": _PII_RESOURCE_VALUE}}
    assert row.conversation_name == _PII_CONVERSATION_NAME
    assert row.reasoning_content == "think 123-45-6789"
