from __future__ import annotations

import json
from enum import Enum

import pytest
from pydantic import BaseModel, ConfigDict, Field

from weave.trace_server.credential_redaction import REDACTED_VALUE
from weave.trace_server.errors import RequestTooLarge
from weave.trace_server.sensitive_data.detectors import redact_pii_string
from weave.trace_server.sensitive_data.walker import redact_pii_value

_EMAIL_A = '<WEAVE_REDACTED type="EMAIL_ADDRESS" hint="a***" />'
_EMAIL_E = '<WEAVE_REDACTED type="EMAIL_ADDRESS" hint="e***" />'
_EMAIL_F = '<WEAVE_REDACTED type="EMAIL_ADDRESS" hint="f***" />'
_EMAIL_G = '<WEAVE_REDACTED type="EMAIL_ADDRESS" hint="g***" />'
_EMAIL_J = '<WEAVE_REDACTED type="EMAIL_ADDRESS" hint="j***" />'
_EMAIL_L = '<WEAVE_REDACTED type="EMAIL_ADDRESS" hint="l***" />'
_EMAIL_O = '<WEAVE_REDACTED type="EMAIL_ADDRESS" hint="o***" />'
_EMAIL_P = '<WEAVE_REDACTED type="EMAIL_ADDRESS" hint="p***" />'
_PHONE_1 = '<WEAVE_REDACTED type="PHONE_NUMBER" hint="1***" />'
_PHONE_4 = '<WEAVE_REDACTED type="PHONE_NUMBER" hint="4***" />'
_SSN_1 = '<WEAVE_REDACTED type="US_SSN" hint="1***" />'
_CARD_4 = '<WEAVE_REDACTED type="CREDIT_CARD" hint="4***" />'


class _StructuralLabel(str, Enum):
    EMAIL_SHAPED = "ada@example.com"


class _PayloadModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    values: tuple[object, ...]
    excluded: str = Field(exclude=True)


class _NestedPayload(BaseModel):
    value: object


def _assert_nesting_rejected(value: object) -> None:
    with pytest.raises(RequestTooLarge) as exc_info:
        redact_pii_value(value)

    assert str(exc_info.value) == "Sensitive-data nesting limit exceeded"


def test_redacts_supported_pii_with_typed_markers_and_hints() -> None:
    text = (
        "Email ada.lovelace@example.com, phone (415) 555-2671, SSN 123-45-6789, "
        "card 4111 1111 1111 1111, international +44 20 7946 0958."
    )

    assert redact_pii_string(text) == (
        f"Email {_EMAIL_A}, phone {_PHONE_4}, SSN {_SSN_1}, "
        f"card {_CARD_4}, international {_PHONE_4}."
    )


def test_redacts_compact_luhn_valid_card() -> None:
    assert redact_pii_string("4111111111111111") == _CARD_4


def test_redacts_compact_e164_phone() -> None:
    assert redact_pii_string("Call +14155552671") == f"Call {_PHONE_1}"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("界ada@example.com界", f"界{_EMAIL_A}界"),
        ("界(415) 555-2671界", f"界{_PHONE_4}界"),
        ("界123-45-6789界", f"界{_SSN_1}界"),
        ("界4111 1111 1111 1111界", f"界{_CARD_4}界"),
    ],
)
def test_unicode_neighbors_cannot_hide_ascii_pii(text: str, expected: str) -> None:
    assert redact_pii_string(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("jane.doe@example.com", _EMAIL_J),
        ("a.b@x.co", _EMAIL_A),
        ("first.middle.last@sub.example.com", _EMAIL_F),
        ("Contact jane.doe@example.com today", f"Contact {_EMAIL_J} today"),
        (
            "!tag@example.com",
            '<WEAVE_REDACTED type="EMAIL_ADDRESS" hint="t***" />',
        ),
        ("!@example.com", '<WEAVE_REDACTED type="EMAIL_ADDRESS" hint="***" />'),
    ],
)
def test_redacts_emails_with_bounded_local_part_hints(text: str, expected: str) -> None:
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
        "contact": _EMAIL_A,
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
            {"contact": _EMAIL_G},
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
        '"contact":"<WEAVE_REDACTED type=\\"EMAIL_ADDRESS\\" hint=\\"a***\\" />",'
        '"phone":"<WEAVE_REDACTED type=\\"PHONE_NUMBER\\" hint=\\"4***\\" />"}'
    )


def test_walker_drops_shadowed_duplicate_json_keys() -> None:
    assert redact_pii_value('{"x":"ada@example.com","x":"safe"}') == '{"x":"safe"}'
    assert redact_pii_value(
        '{"nested":[{"x":"ada@example.com","x":"safe"}],"count":1}'
    ) == ('{"nested":[{"x":"safe"}],"count":1}')


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
    assert redacted.values == (clean_list, _EMAIL_A)
    assert redacted.values is not payload.values
    assert redacted.values[0] is clean_list
    assert redacted.excluded == "grace@example.com"
    assert redacted.model_extra == {"extra_contact": _EMAIL_L}
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
        f"{prefix}text/plain,{_EMAIL_A}"
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            "weave:///not-a-complete-ref ada@example.com",
            f"weave:///not-a-complete-ref {_EMAIL_A}",
        ),
        (
            "weave-trace-internal:///missing-kind ada@example.com",
            f"weave-trace-internal:///missing-kind {_EMAIL_A}",
        ),
        (
            "weave-private:///not-canonical ada@example.com",
            f"weave-private:///not-canonical {_EMAIL_A}",
        ),
    ],
)
def test_walker_scans_malformed_ref_prefixes(value: str, expected: str) -> None:
    assert redact_pii_value(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            "weave:///entity/project/object/ada@example.com:",
            f"weave:{_EMAIL_E}:",
        ),
        (
            "weave-trace-internal:///project/object/ada@example.com:",
            f"weave-trace-internal:{_EMAIL_P}:",
        ),
        (
            "weave-private://///object/ada@example.com:",
            f"weave-private:{_EMAIL_O}:",
        ),
    ],
)
def test_walker_scans_refs_with_missing_required_parts(
    value: str, expected: str
) -> None:
    redacted = redact_pii_value(value)

    assert redacted == expected


@pytest.mark.parametrize(
    ("value", "expected_prefix"),
    [
        (
            "data: not a URL; email ada@example.com",
            f"data: not a URL; email {_EMAIL_A}",
        ),
        (
            "data:image/png;base64,ada@example.comA",
            f"data:image/png;base64,{_EMAIL_A}",
        ),
        ("/4111111111111111/" + "A" * (8192 - 18), f"/{_CARD_4}/"),
        ("/4111111111111111/" + "A" * (8193 - 18), f"/{_CARD_4}/"),
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


@pytest.mark.parametrize("container", ["dict", "list", "tuple", "model"])
def test_walker_rejects_deeply_nested_structures(container: str) -> None:
    value: object = "ada@example.com"
    for _ in range(800):
        if container == "dict":
            value = {"value": value}
        elif container == "list":
            value = [value]
        elif container == "tuple":
            value = (value,)
        else:
            value = _NestedPayload(value=value)

    _assert_nesting_rejected(value)


def test_walker_rejects_deeply_nested_json_string() -> None:
    value: object = "ada@example.com"
    for _ in range(800):
        value = [value]

    _assert_nesting_rejected(json.dumps(value))


def test_walker_rejects_cyclic_input_without_recursion_error() -> None:
    payload: dict[str, object] = {}
    payload["self"] = payload

    _assert_nesting_rejected(payload)

    assert payload["self"] is payload


def test_numeric_run_without_minimum_digits_is_unchanged() -> None:
    value = "1" + "-" * 600 + "2"

    assert redact_pii_value(value) is value
