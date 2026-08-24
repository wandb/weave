from __future__ import annotations

import datetime

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.opentelemetry.python_spans import (
    Event,
    Link,
    Span,
    Status,
    StatusCode,
)
from weave.trace_server.opentelemetry.python_spans import (
    Resource as SpanResource,
)
from weave.trace_server.sensitive_data.call_redaction import (
    redact_call_batch,
    redact_call_end,
    redact_call_start,
    redact_call_update,
    redact_calls_complete,
)
from weave.trace_server.sensitive_data.policy import SensitiveDataPolicy
from weave.trace_server.sensitive_data.span_redaction import redact_pii_from_span

NOW = datetime.datetime(2026, 8, 12, tzinfo=datetime.timezone.utc)


def test_call_start_redacts_content_but_not_structural_fields() -> None:
    req = _call_start_req()

    redacted = redact_call_start(req, SensitiveDataPolicy.PII_V1)

    assert isinstance(redacted, tsi.CallStartReq)
    assert redacted.start.inputs == {"email": "<EMAIL_ADDRESS>"}
    assert redacted.start.attributes == {"phone": "<PHONE_NUMBER>"}
    assert redacted.start.otel_dump == {"ssn": "<US_SSN>"}
    assert redacted.start.display_name == "Contact <EMAIL_ADDRESS>"
    assert redacted.start.op_name == "<EMAIL_ADDRESS>"
    assert redacted.start.project_id == "ada@example.com/project"
    assert req.start.inputs == {"email": "ada@example.com"}


def test_call_start_preserves_ref_op_names() -> None:
    req = _call_start_req()
    req.start.op_name = "weave:///entity/project/op/my-op:v1"

    redacted = redact_call_start(req, SensitiveDataPolicy.PII_V1)

    assert redacted.start.op_name == "weave:///entity/project/op/my-op:v1"


def test_call_end_update_complete_and_batch_redact_content() -> None:
    end_req = _call_end_req()
    update_req = tsi.CallUpdateReq(
        project_id="ada@example.com/project",
        call_id="ada@example.com",
        display_name="Email ada@example.com",
    )
    complete_req = tsi.CallsUpsertCompleteReq(batch=[_completed_call()])
    batch_req = tsi.CallCreateBatchReq(
        batch=[
            tsi.CallBatchStartMode(req=_call_start_req()),
            tsi.CallBatchEndMode(req=end_req),
        ]
    )

    redacted_end = redact_call_end(end_req, SensitiveDataPolicy.PII_V1)
    redacted_update = redact_call_update(update_req, SensitiveDataPolicy.PII_V1)
    redacted_complete = redact_calls_complete(complete_req, SensitiveDataPolicy.PII_V1)
    redacted_batch = redact_call_batch(batch_req, SensitiveDataPolicy.PII_V1)

    assert redacted_end.end.output == {"card": "<CREDIT_CARD>"}
    assert redacted_end.end.summary == {"contact": "<EMAIL_ADDRESS>"}
    assert redacted_end.end.exception == "Failed for <EMAIL_ADDRESS>"
    assert redacted_update.display_name == "Email <EMAIL_ADDRESS>"
    assert redacted_update.project_id == "ada@example.com/project"
    assert redacted_update.call_id == "ada@example.com"
    assert redacted_complete.batch[0].inputs == {"email": "<EMAIL_ADDRESS>"}
    assert redacted_complete.batch[0].output == {"card": "<CREDIT_CARD>"}
    assert redacted_complete.batch[0].op_name == "<EMAIL_ADDRESS>"
    assert redacted_batch.batch[0].req.start.inputs == {"email": "<EMAIL_ADDRESS>"}
    assert redacted_batch.batch[1].req.end.output == {"card": "<CREDIT_CARD>"}


def test_off_policy_skips_the_walker() -> None:
    req = _call_start_req()

    assert redact_call_start(req, SensitiveDataPolicy.OFF) is req


def _call_start_req() -> tsi.CallStartReq:
    return tsi.CallStartReq(
        start=tsi.StartedCallSchemaForInsert(
            project_id="ada@example.com/project",
            id="call-id",
            trace_id="trace-id",
            op_name="ada@example.com",
            display_name="Contact ada@example.com",
            started_at=NOW,
            attributes={"phone": "(415) 555-2671"},
            inputs={"email": "ada@example.com"},
            otel_dump={"ssn": "123-45-6789"},
        )
    )


def _call_end_req() -> tsi.CallEndReq:
    return tsi.CallEndReq(
        end=tsi.EndedCallSchemaForInsert(
            project_id="ada@example.com/project",
            id="call-id",
            trace_id="trace-id",
            ended_at=NOW,
            output={"card": "4111 1111 1111 1111"},
            summary={"contact": "ada@example.com"},
            exception="Failed for ada@example.com",
        )
    )


def _completed_call() -> tsi.CompletedCallSchemaForInsert:
    return tsi.CompletedCallSchemaForInsert(
        project_id="ada@example.com/project",
        id="call-id",
        trace_id="trace-id",
        op_name="ada@example.com",
        started_at=NOW,
        ended_at=NOW,
        attributes={"phone": "(415) 555-2671"},
        inputs={"email": "ada@example.com"},
        output={"card": "4111 1111 1111 1111"},
        summary={"ssn": "123-45-6789"},
    )


def _span_with_pii() -> Span:
    return Span(
        resource=SpanResource(attributes={"service.owner": "ada@example.com"}),
        name="agents_pii_surface",
        trace_id="a1" * 16,
        span_id="b2" * 8,
        start_time_unix_nano=1,
        end_time_unix_nano=2,
        attributes={
            "gen_ai.prompt": "Email ada@example.com",
            "payload": {"image": "data:image/png;base64,QUJD"},
        },
        events=[
            Event(
                name="exception",
                timestamp=1,
                attributes={"note": "call (415) 555-2671"},
            )
        ],
        links=[
            Link(
                trace_id="c3" * 16,
                span_id="d4" * 8,
                attributes={"context": "ssn 123-45-6789"},
            )
        ],
        status=Status(code=StatusCode.ERROR, message="card 4111 1111 1111 1111"),
    )


def test_redacts_pii_from_every_span_container() -> None:
    span = _span_with_pii()

    redact_pii_from_span(span, SensitiveDataPolicy.PII_V1)

    assert span.attributes == {
        "gen_ai.prompt": "Email <EMAIL_ADDRESS>",
        "payload": {"image": "data:image/png;base64,QUJD"},
    }
    assert span.resource is not None
    assert span.resource.attributes == {"service.owner": "<EMAIL_ADDRESS>"}
    assert span.events[0].attributes == {"note": "call <PHONE_NUMBER>"}
    assert span.links[0].attributes == {"context": "ssn <US_SSN>"}
    assert span.status.message == "card <CREDIT_CARD>"
    assert span.name == "agents_pii_surface"
    assert span.span_id == "b2" * 8


def test_span_redaction_off_policy_is_a_noop() -> None:
    span = _span_with_pii()
    original_attributes = span.attributes

    redact_pii_from_span(span, SensitiveDataPolicy.OFF)

    assert span.attributes is original_attributes
    assert span.status.message == "card 4111 1111 1111 1111"
