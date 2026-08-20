from __future__ import annotations

import datetime
from enum import Enum

import pytest
from pydantic import BaseModel, ConfigDict, Field

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.credential_redaction import REDACTED_VALUE
from weave.trace_server.environment import (
    SENSITIVE_DATA_POLICY_ENV,
    sensitive_data_policy,
)
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
from weave.trace_server.sensitive_data.detectors import redact_pii_string
from weave.trace_server.sensitive_data.policy import SensitiveDataPolicy
from weave.trace_server.sensitive_data.span_redaction import redact_pii_from_span
from weave.trace_server.sensitive_data.walker import redact_pii_value

NOW = datetime.datetime(2026, 8, 12, tzinfo=datetime.timezone.utc)


class _StructuralLabel(str, Enum):
    EMAIL_SHAPED = "ada@example.com"


class _PayloadModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    values: tuple[object, ...]
    excluded: str = Field(exclude=True)


def test_sensitive_data_policy_defaults_to_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(SENSITIVE_DATA_POLICY_ENV, raising=False)

    assert sensitive_data_policy() is SensitiveDataPolicy.OFF


def test_sensitive_data_policy_parses_pii_v1(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(SENSITIVE_DATA_POLICY_ENV, "pii-v1")

    assert sensitive_data_policy() is SensitiveDataPolicy.PII_V1


def test_sensitive_data_policy_rejects_unknown_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(SENSITIVE_DATA_POLICY_ENV, "unknown")

    with pytest.raises(ValueError, match="must be 'off' or 'pii-v1'") as exc_info:
        sensitive_data_policy()
    assert "unknown" not in str(exc_info.value)


def test_redacts_supported_pii_with_typed_markers() -> None:
    text = (
        "Email ada.lovelace@example.com, phone (415) 555-2671, SSN 123-45-6789, "
        "card 4111 1111 1111 1111, international +44 20 7946 0958."
    )

    assert redact_pii_string(text) == (
        "Email <EMAIL_ADDRESS>, phone <PHONE_NUMBER>, SSN <US_SSN>, "
        "card <CREDIT_CARD>, international <PHONE_NUMBER>."
    )


def test_redacts_compact_luhn_valid_card() -> None:
    assert redact_pii_string("4111111111111111") == "<CREDIT_CARD>"


def test_redacts_compact_e164_phone() -> None:
    assert redact_pii_string("Call +14155552671") == ("Call <PHONE_NUMBER>")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("界ada@example.com界", "界<EMAIL_ADDRESS>界"),
        ("界(415) 555-2671界", "界<PHONE_NUMBER>界"),
        ("界123-45-6789界", "界<US_SSN>界"),
        ("界4111 1111 1111 1111界", "界<CREDIT_CARD>界"),
    ],
)
def test_unicode_neighbors_cannot_hide_ascii_pii(text: str, expected: str) -> None:
    assert redact_pii_string(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("jane.doe@example.com", "<EMAIL_ADDRESS>"),
        ("a.b@x.co", "<EMAIL_ADDRESS>"),
        ("first.middle.last@sub.example.com", "<EMAIL_ADDRESS>"),
        ("Contact jane.doe@example.com today", "Contact <EMAIL_ADDRESS> today"),
    ],
)
def test_redacts_emails_with_dotted_local_parts(text: str, expected: str) -> None:
    assert redact_pii_string(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "not-an-email@localhost",
        "000-12-3456",
        "666-12-3456",
        "900-12-3456",
        "123-00-6789",
        "123-45-0000",
        "123456789",
        "0000 0000 0000 0000",
        "4111 1111 1111 1112",
        "abc4111111111111111xyz",
        "4155552671",
        "+141555526",
        "prefix+14155552671",
        "+14155552671suffix",
        "++14155552671",
        "12345-6789",
        "123-456789",
        "123e4567-e89b-12d3-a456-426614174000",
        "192.168.1.1",
        "2026-08-12 10:57:57",
        "user@" + "a" * 64 + ".com",
        "a" * 65 + "@example.com",
        ".user@example.com",
        "user.@example.com",
        "first..last@example.com",
        "user@example.com_suffix",
        "user@example.com-extra",
    ],
)
def test_leaves_common_numeric_non_matches_unchanged(text: str) -> None:
    assert redact_pii_string(text) == text


def test_walker_is_copy_on_write_and_does_not_scan_keys() -> None:
    clean_subtree = {"message": "hello"}
    payload = {
        "ada@example.com": "dictionary key",
        "contact": "ada@example.com",
        "clean": clean_subtree,
    }

    redacted = redact_pii_value(payload)

    assert redacted == {
        "ada@example.com": "dictionary key",
        "contact": "<EMAIL_ADDRESS>",
        "clean": {"message": "hello"},
    }
    assert redacted is not payload
    assert redacted["clean"] is clean_subtree
    assert payload["contact"] == "ada@example.com"


def test_walker_fuses_credential_key_and_pii_redaction() -> None:
    payload = {
        "api_key": "ada@example.com",
        "nested": [
            {"secret_access_key": "secret-value"},
            {"contact": "grace@example.com"},
        ],
    }

    redacted = redact_pii_value(payload)

    assert redacted == {
        "api_key": REDACTED_VALUE,
        "nested": [
            {"secret_access_key": REDACTED_VALUE},
            {"contact": "<EMAIL_ADDRESS>"},
        ],
    }
    assert payload == {
        "api_key": "ada@example.com",
        "nested": [
            {"secret_access_key": "secret-value"},
            {"contact": "grace@example.com"},
        ],
    }


def test_walker_redacts_json_escaped_values_without_scanning_keys() -> None:
    value = (
        r'{"ada@example.com":"dictionary key",'
        r'"contact":"ada\u0040example.com",'
        r'"phone":"\u0028415\u0029 555-2671"}'
    )

    assert redact_pii_value(value) == (
        '{"ada@example.com":"dictionary key",'
        '"contact":"<EMAIL_ADDRESS>",'
        '"phone":"<PHONE_NUMBER>"}'
    )


def test_walker_does_not_rewrite_string_enum_discriminators() -> None:
    assert (
        redact_pii_value(_StructuralLabel.EMAIL_SHAPED) is _StructuralLabel.EMAIL_SHAPED
    )


def test_walker_copies_models_and_tuples_only_along_changed_paths() -> None:
    clean_list = ["hello"]
    payload = _PayloadModel(
        values=(clean_list, "ada@example.com"),
        excluded="grace@example.com",
        extra_contact="linus@example.com",
    )

    redacted = redact_pii_value(payload)

    assert redacted is not payload
    assert redacted.values == (clean_list, "<EMAIL_ADDRESS>")
    assert redacted.values is not payload.values
    assert redacted.values[0] is clean_list
    assert redacted.excluded == "grace@example.com"
    assert redacted.model_extra == {"extra_contact": "<EMAIL_ADDRESS>"}
    assert payload.model_extra == {"extra_contact": "linus@example.com"}


def test_walker_preserves_refs_base64_data_urls_and_inline_base64() -> None:
    base64_value = "A" * 8200
    payload = {
        "external_ref": "weave:///entity/project/object/ada@example.com:latest",
        "internal_ref": (
            "weave-trace-internal:///cHJvamVjdA==/object/ada@example.com:latest"
        ),
        "private_ref": "weave-private://///object/ada@example.com:latest",
        "base64_data": "data:text/plain;base64,YWRhQGV4YW1wbGUuY29t",
        "base64": base64_value,
    }

    assert redact_pii_value(payload) is payload


@pytest.mark.parametrize("prefix", ["data:", "DATA:"])
def test_walker_scans_plaintext_data_urls(prefix: str) -> None:
    assert redact_pii_value(f"{prefix}text/plain,ada@example.com") == (
        f"{prefix}text/plain,<EMAIL_ADDRESS>"
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            "weave:///not-a-complete-ref ada@example.com",
            "weave:///not-a-complete-ref <EMAIL_ADDRESS>",
        ),
        (
            "weave-trace-internal:///missing-kind ada@example.com",
            "weave-trace-internal:///missing-kind <EMAIL_ADDRESS>",
        ),
        (
            "weave-private:///not-canonical ada@example.com",
            "weave-private:///not-canonical <EMAIL_ADDRESS>",
        ),
    ],
)
def test_walker_scans_malformed_ref_prefixes(value: str, expected: str) -> None:
    assert redact_pii_value(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "weave:///entity/project/object/ada@example.com:",
        "weave-trace-internal:///project/object/ada@example.com:",
        "weave-private://///object/ada@example.com:",
    ],
)
def test_walker_scans_refs_with_missing_required_parts(value: str) -> None:
    redacted = redact_pii_value(value)

    assert "ada@example.com" not in redacted
    assert "<EMAIL_ADDRESS>" in redacted


@pytest.mark.parametrize(
    ("value", "expected_prefix"),
    [
        (
            "data: not a URL; email ada@example.com",
            "data: not a URL; email <EMAIL_ADDRESS>",
        ),
        (
            "data:image/png;base64,ada@example.comA",
            "data:image/png;base64,<EMAIL_ADDRESS>",
        ),
        ("/4111111111111111/" + "A" * (8192 - 18), "/<CREDIT_CARD>/"),
        ("/4111111111111111/" + "A" * (8193 - 18), "/<CREDIT_CARD>/"),
    ],
    ids=[
        "invalid-data-url",
        "invalid-base64-data-url",
        "base64-at-threshold",
        "malformed-base64",
    ],
)
def test_walker_does_not_preserve_invalid_encoded_content(
    value: str, expected_prefix: str
) -> None:
    assert redact_pii_value(value).startswith(expected_prefix)


def test_walker_fails_loudly_on_cyclic_input() -> None:
    payload: dict[str, object] = {}
    payload["self"] = payload

    with pytest.raises(RecursionError):
        redact_pii_value(payload)

    assert payload["self"] is payload


def test_numeric_run_without_minimum_digits_is_unchanged() -> None:
    value = "1" + "-" * 600 + "2"

    assert redact_pii_value(value) is value


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
