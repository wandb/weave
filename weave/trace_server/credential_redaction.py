"""Replace credential-shaped values in client-authored call data at ingest.

The server receives call data already serialized, so it cannot ask a value what
kind of object it came from -- the field name is the only signal left, which is
why the policy here is a name policy.

The policy is a conservative denylist: broad, common names are left out because
redaction is irreversible, so a matched field is destroyed. It is narrow, not
infallible -- a legitimate field can still carry a matching name.

Applied by the ClickHouse schema converters to the client-authored call columns:
`inputs_dump`, `attributes_dump`, and `otel_dump`, which is a raw copy of the
client's span and so carries the same attribute values a second time.

The agents OTel ingest and the completions span builder apply it to the
client-authored parts of an agent span.
"""

from __future__ import annotations

from collections.abc import Sequence
from functools import lru_cache
from typing import Any, TypeVar, cast

T = TypeVar("T")

# `redact_sensitive_keys` and `should_redact` mirror the client-side names in
# `weave/trace/weave_client.py` and `weave/utils/sanitize.py` on purpose, but the
# semantics differ (normalization, suffix matching, non-empty strings only) and
# the two cannot be shared: an import-linter contract forbids
# `weave.trace_server` from importing `weave.utils`. Hence a local marker, whose
# value matches what the client writes.
REDACTED_VALUE = "REDACTED"

_STRIP_FROM_KEY = str.maketrans("", "", "_-")

# Policy entries the suffixes below do not reach.
_CREDENTIAL_NAMES = frozenset(
    {
        "authheaders",
        "authorization",
        "authtoken",
        "awsaccesskey",
        "awsaccesskeyid",
        "bearertoken",
        "vertexcredentials",
        "webhookkey",
        "webhooksecret",
    }
)

# The `<vendor>_<credential>` family (`openai_api_key`, `aws_secret_access_key`,
# `api_token`) is open-ended, so it is matched by suffix rather than by adding a
# name per vendor forever. Substring matching is not an option -- `"key" in name`
# hits `monkey` and `keywords`.
_CREDENTIAL_SUFFIXES = (
    "accesstoken",
    "apikey",
    "apitoken",
    "clientsecret",
    "privatekey",
    "refreshtoken",
    "secretaccesskey",
    "secretkey",
    "sessiontoken",
)

# Cache keys are client-controlled strings, so only plausible field names are
# memoized: 8192 cached names of a megabyte each would be gigabytes held for the
# life of the process. Real field names are far shorter than 64 characters.
_MAX_MEMOIZED_KEY_LEN = 64


def _normalize_key(key: str) -> str:
    """Collapse the spellings of one field name: `apiKey`, `api_key`, `X-API-Key`."""
    return key.translate(_STRIP_FROM_KEY).lower()


def _matches_credential_name(normalized_key: str) -> bool:
    return normalized_key in _CREDENTIAL_NAMES or normalized_key.endswith(
        _CREDENTIAL_SUFFIXES
    )


@lru_cache(maxsize=8192)
def _should_redact_memoized(key: str) -> bool:
    return _matches_credential_name(_normalize_key(key))


def should_redact(key: str) -> bool:
    """Whether a field named `key` holds a credential.

    Memoized, because this runs on every string-valued field of every ingested
    call.
    """
    if len(key) <= _MAX_MEMOIZED_KEY_LEN:
        return _should_redact_memoized(key)
    return _matches_credential_name(_normalize_key(key))


def redact_sensitive_keys(value: T) -> T:
    """Replace credential-shaped string values anywhere inside `value`.

    Only non-empty strings are replaced, and that restriction is what keeps the
    pass from corrupting data: a JSON schema under `apiKey` stays a dict, a
    `has_api_key: true` flag stays a bool, and no consumer doing `.get()` on a
    subtree finds a string where a container used to be.

    Copy-on-write, like `sanitize_invalid_utf8_surrogates` in this package: a
    subtree with nothing to redact comes back by identity, so payloads the policy
    does not name re-serialize byte for byte -- which is what keeps eval-result
    row digests stable.
    """
    if isinstance(value, dict):
        redacted_fields: dict[Any, Any] | None = None
        for key, item in value.items():
            new_item = _redact_field(key, item)
            if new_item is item:
                continue
            if redacted_fields is None:
                redacted_fields = dict(value)
            redacted_fields[key] = new_item
        return value if redacted_fields is None else cast(T, redacted_fields)
    if isinstance(value, list):
        redacted_items = _redact_items(value)
        return value if redacted_items is None else cast(T, redacted_items)
    if isinstance(value, tuple):
        # `json.dumps` writes a tuple as an array, so tuples reach the stored
        # column: server-built inputs come from `model_dump()`, which keeps
        # tuple fields as tuples.
        redacted_items = _redact_items(value)
        return value if redacted_items is None else cast(T, tuple(redacted_items))
    return value


def _redact_field(key: Any, value: Any) -> Any:
    """Replace `value` when `key` names a credential, otherwise recurse into it.

    Non-string keys are not checked as names -- `isinstance` rather than an exact
    type check, because the repo has `str` subclasses (`weave/shared/refs_internal.py`).

    Values the Python client already redacted arrive holding the marker; skipping
    those saves copying every such payload.
    """
    if isinstance(key, str) and isinstance(value, str):
        if value and value != REDACTED_VALUE and should_redact(key):
            return REDACTED_VALUE
        return value
    return redact_sensitive_keys(value)


def _redact_items(value: Sequence[Any]) -> list[Any] | None:
    """A redacted copy of a sequence's items, or None when nothing changed."""
    redacted: list[Any] | None = None
    for index, item in enumerate(value):
        new_item = redact_sensitive_keys(item)
        if new_item is item:
            continue
        if redacted is None:
            redacted = list(value)
        redacted[index] = new_item
    return redacted
