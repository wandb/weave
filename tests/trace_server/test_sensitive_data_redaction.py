from __future__ import annotations

from enum import Enum

import pytest
from pydantic import BaseModel, ConfigDict, Field

from weave.trace_server.credential_redaction import REDACTED_VALUE
from weave.trace_server.sensitive_data.detectors import redact_pii_string
from weave.trace_server.sensitive_data.walker import redact_pii_value


class _StructuralLabel(str, Enum):
    EMAIL_SHAPED = "ada@example.com"


class _PayloadModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    values: tuple[object, ...]
    excluded: str = Field(exclude=True)


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
