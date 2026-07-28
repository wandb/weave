"""Replace credential-shaped values in client-authored call data at ingest.

The server receives call data already serialized, so it cannot ask a value what
kind of object it came from -- the field name is the only signal left. That is
why the policy here is about names, and why it is deliberately narrow: ordinary
words (`secret`, `password`, `token`) are left out because they show up as
legitimate dataset columns.

Applied by the ClickHouse schema converters to the two client-authored call
columns, `inputs_dump` and `attributes_dump`.
"""

from __future__ import annotations

from collections.abc import Sequence
from functools import lru_cache
from typing import Any, TypeVar, cast

from weave.trace_server.datadog import _db_insert_path, emit_counter

T = TypeVar("T")

REDACTION_METRIC = "weave_trace_server.credential_redactions"

# The same marker the Python client writes client-side. Declared here rather
# than imported: an import-linter contract forbids `weave.trace_server` from
# importing `weave.utils`.
REDACTED_VALUE = "REDACTED"

_STRIP_FROM_KEY = str.maketrans("", "", "_-")

# Normalized names that only ever carry a credential.
_CREDENTIAL_NAMES = frozenset(
    {
        "adminapikey",
        "apikey",
        "authheaders",
        "authorization",
        "authtoken",
        "awsaccesskey",
        "awsaccesskeyid",
        "awssecretaccesskey",
        "awssecretkey",
        "awssessiontoken",
        "bearertoken",
        "vertexcredentials",
        "webhookkey",
        "webhooksecret",
        "xapikey",
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
# memoized: 8191 cached names of a megabyte each would be gigabytes held for the
# life of the process. Real field names are far shorter than this.
_MAX_MEMOIZED_KEY_LEN = 64


def normalize_key(key: str) -> str:
    """Collapse the spellings of one field name: `apiKey`, `api_key`, `X-API-Key`."""
    return key.translate(_STRIP_FROM_KEY).lower()


def _matches_credential_name(normalized_key: str) -> bool:
    return normalized_key in _CREDENTIAL_NAMES or normalized_key.endswith(
        _CREDENTIAL_SUFFIXES
    )


@lru_cache(maxsize=8192)
def _should_redact_memoized(key: str) -> bool:
    return _matches_credential_name(normalize_key(key))


def should_redact(key: str) -> bool:
    """Whether a field named `key` holds a credential.

    Memoized, because this runs on every string-valued field of every ingested
    call: ~260ns uncached against ~30ns from the cache.
    """
    if len(key) <= _MAX_MEMOIZED_KEY_LEN:
        return _should_redact_memoized(key)
    return _matches_credential_name(normalize_key(key))


def redact_sensitive_keys(value: T) -> tuple[T, dict[str, int]]:
    """Replace credential-shaped string values, returning the result and a tally.

    Only non-empty strings are replaced, and that restriction is what keeps the
    pass from corrupting data: a JSON schema under `apiKey` stays a dict, a
    `has_api_key: true` flag stays a bool, and no consumer doing `.get()` on a
    subtree finds a string where a container used to be.

    Copy-on-write, so a subtree with nothing to redact comes back by identity and
    payloads the policy does not touch re-serialize byte for byte -- which is
    what keeps eval-result row digests stable.

    The tally maps normalized field name to how many values were replaced.
    """
    tally: dict[str, int] = {}
    return _redact(value, tally), tally


def _redact(value: T, tally: dict[str, int]) -> T:
    if isinstance(value, dict):
        redacted_fields: dict[Any, Any] | None = None
        for key, item in value.items():
            new_item = _redact_field(key, item, tally)
            if new_item is item:
                continue
            if redacted_fields is None:
                redacted_fields = dict(value)
            redacted_fields[key] = new_item
        return value if redacted_fields is None else cast(T, redacted_fields)
    if isinstance(value, list):
        redacted_items = _redact_items(value, tally)
        return value if redacted_items is None else cast(T, redacted_items)
    if isinstance(value, tuple):
        # `json.dumps` writes a tuple as an array, so tuples reach the stored
        # column: server-built inputs come from `model_dump()`, which keeps
        # tuple fields as tuples.
        redacted_items = _redact_items(value, tally)
        return value if redacted_items is None else cast(T, tuple(redacted_items))
    return value


def _redact_field(key: Any, value: Any, tally: dict[str, int]) -> Any:
    """Replace `value` when `key` names a credential, otherwise recurse into it.

    Non-string keys are not checked as names -- `isinstance` rather than an exact
    type check, because the repo has `str` subclasses used as keys.
    """
    if isinstance(key, str) and isinstance(value, str):
        if value and value != REDACTED_VALUE and should_redact(key):
            normalized = normalize_key(key)
            tally[normalized] = tally.get(normalized, 0) + 1
            return REDACTED_VALUE
        return value
    return _redact(value, tally)


def _redact_items(value: Sequence[Any], tally: dict[str, int]) -> list[Any] | None:
    """A redacted copy of a sequence's items, or None when nothing changed."""
    redacted: list[Any] | None = None
    for index, item in enumerate(value):
        new_item = _redact(item, tally)
        if new_item is item:
            continue
        if redacted is None:
            redacted = list(value)
        redacted[index] = new_item
    return redacted


def record_redactions(*tallies: dict[str, int]) -> None:
    """Emit one counter per redacted field name, tagged with the insert path.

    The tallies of a whole call are summed before emitting so a name hit in
    several columns costs one packet: a single dogstatsd send is more expensive
    than the traversal that produced the tally. `weave_trace_server.db_inserts`
    carries the same `path` tag and is the denominator.
    """
    totals: dict[str, int] = {}
    for tally in tallies:
        for name, count in tally.items():
            totals[name] = totals.get(name, 0) + count
    if not totals:
        return
    path = _db_insert_path.get()
    for name, count in totals.items():
        emit_counter(REDACTION_METRIC, count, [f"name:{name}", f"path:{path}"])
