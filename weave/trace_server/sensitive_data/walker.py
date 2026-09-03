"""Copy-on-write credential and PII traversal of trace values."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Sequence
from enum import Enum
from typing import Any, TypeVar, cast

from pydantic import BaseModel

from weave.shared import refs_internal as ri
from weave.trace_server.credential_redaction import REDACTED_VALUE, should_redact
from weave.trace_server.errors import RequestTooLarge
from weave.trace_server.sensitive_data.detectors import redact_pii_string

T = TypeVar("T")

# Keep these aligned with the standalone-base64 gate in
# ``base64_content_conversion``. That path considers only strings strictly
# larger than 8 KiB and validates the encoding before offloading it.
_INLINE_BASE64_MIN_CHARACTERS = 8192
_INLINE_BASE64_RE = re.compile(r"[A-Za-z0-9+/]+={0,2}", re.ASCII)
_DATA_URL_RE = re.compile(
    r"data:(?:[\w/+.-]+)?(?:;[\w-]+=[\w.-]+)*"
    r"(?P<base64>;base64)?,(?P<data>[^\r\n]*)",
    re.ASCII | re.IGNORECASE,
)
# Shared with the call and span adapters' RecursionError translation.
NESTING_LIMIT_MESSAGE = "Sensitive-data nesting limit exceeded"
_EXTERNAL_REF_PREFIX = f"{ri.WEAVE_SCHEME}:///"
_INTERNAL_REF_PREFIX = f"{ri.WEAVE_INTERNAL_SCHEME}:///"
_PRIVATE_REF_PREFIX = f"{ri.WEAVE_PRIVATE_SCHEME}://///"
_SYNTHETIC_PROJECT_ID = "cHJvamVjdA=="


def redact_pii_value(value: T) -> T:
    """Redact credential-shaped fields and PII while reusing clean subtrees."""
    if isinstance(value, Enum):
        return value
    if isinstance(value, str):
        if _preserve_string(value):
            return value
        if _is_json_candidate(value):
            return cast(T, _redact_json_string(value))
        return cast(T, redact_pii_string(value))
    if isinstance(value, BaseModel):
        return cast(T, _redact_model(value))
    if isinstance(value, dict):
        return cast(T, _redact_mapping(value))
    if isinstance(value, list):
        return cast(T, _redact_sequence(value, list))
    if isinstance(value, tuple):
        return cast(T, _redact_sequence(value, tuple))
    return value


def _is_json_candidate(value: str) -> bool:
    stripped = value.strip()
    if len(stripped) < 2 or (stripped[0], stripped[-1]) not in {
        ("{", "}"),
        ("[", "]"),
        ('"', '"'),
    }:
        return False
    return "@" in stripped or any("0" <= character <= "9" for character in stripped)


def _redact_json_string(value: str) -> str:
    saw_duplicate_key = False

    def _build_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        nonlocal saw_duplicate_key
        mapping = dict(pairs)
        if len(mapping) != len(pairs):
            saw_duplicate_key = True
        return mapping

    try:
        parsed = json.loads(value, object_pairs_hook=_build_object)
    except ValueError:
        return redact_pii_string(value)
    except RecursionError as error:
        raise RequestTooLarge(NESTING_LIMIT_MESSAGE) from error
    if not isinstance(parsed, (dict, list, str)):
        return redact_pii_string(value)
    redacted = redact_pii_value(parsed)
    # A duplicate key shadows a value the walk never saw; reserialize to drop it.
    if redacted is parsed and not saw_duplicate_key:
        return value
    return json.dumps(redacted, separators=(",", ":"))


def _preserve_string(value: str) -> bool:
    if _is_complete_weave_ref(value):
        return True
    if value[:5].lower() == "data:" and _is_base64_data_url(value):
        return True
    return (
        len(value) > _INLINE_BASE64_MIN_CHARACTERS
        and len(value) % 4 == 0
        and _INLINE_BASE64_RE.fullmatch(value) is not None
    )


def _is_complete_weave_ref(value: str) -> bool:
    if value.startswith(_INTERNAL_REF_PREFIX):
        return _internal_ref_round_trips(value)
    if value.startswith(_EXTERNAL_REF_PREFIX):
        parts = value[len(_EXTERNAL_REF_PREFIX) :].split("/", 2)
        if len(parts) != 3 or not all(parts):
            return False
        return _ref_tail_round_trips(parts[2])
    if value.startswith(_PRIVATE_REF_PREFIX):
        tail = value[len(_PRIVATE_REF_PREFIX) :]
        return bool(tail) and _ref_tail_round_trips(tail)
    return False


def _ref_tail_round_trips(tail: str) -> bool:
    return _internal_ref_round_trips(
        f"{_INTERNAL_REF_PREFIX}{_SYNTHETIC_PROJECT_ID}/{tail}"
    )


def _internal_ref_round_trips(value: str) -> bool:
    try:
        parsed = ri.parse_internal_uri(value)
    except (IndexError, ValueError):
        return False
    else:
        return _has_complete_ref_parts(parsed) and parsed.uri == value


def _has_complete_ref_parts(ref: ri.InternalRef) -> bool:
    if not ref.project_id:
        return False
    if isinstance(ref, ri.InternalTableRef):
        return bool(ref.digest)
    if isinstance(ref, ri.InternalObjectRef):
        return bool(ref.name and ref.version)
    if isinstance(ref, ri.InternalCallRef):
        return bool(ref.id)
    if isinstance(ref, ri.InternalArtifactRef):
        return bool(ref.id)
    if isinstance(ref, ri.InternalAgentTurnRef):
        return bool(ref.trace_id)
    if isinstance(ref, ri.InternalAgentConversationRef):
        return bool(ref.conversation_id)
    if isinstance(ref, ri.InternalAgentSpanRef):
        return bool(ref.span_id)
    return False


def _is_base64_data_url(value: str) -> bool:
    match = _DATA_URL_RE.fullmatch(value)
    if match is None or match.group("base64") is None:
        return False
    data_start, data_end = match.span("data")
    data_length = data_end - data_start
    return data_length == 0 or (
        data_length % 4 == 0
        and _INLINE_BASE64_RE.fullmatch(value, data_start, data_end) is not None
    )


def _redact_model(model: BaseModel) -> BaseModel:
    updates: dict[str, Any] = {}
    for field_name, field_info in model.__class__.model_fields.items():
        if field_info.exclude is True:
            continue
        original = getattr(model, field_name)
        redacted = _redact_named_value(field_name, original)
        if redacted is not original:
            updates[field_name] = redacted
    for field_name, original in (model.model_extra or {}).items():
        redacted = _redact_named_value(field_name, original)
        if redacted is not original:
            updates[field_name] = redacted
    return model if not updates else model.model_copy(update=updates)


def _redact_mapping(value: dict[Any, Any]) -> dict[Any, Any]:
    redacted: dict[Any, Any] | None = None
    for key, original in value.items():
        item = _redact_named_value(key, original)
        if item is original:
            continue
        if redacted is None:
            redacted = dict(value)
        redacted[key] = item
    return value if redacted is None else redacted


def _redact_named_value(name: Any, value: Any) -> Any:
    if (
        isinstance(name, str)
        and isinstance(value, str)
        and value
        and value != REDACTED_VALUE
        and should_redact(name)
    ):
        return REDACTED_VALUE
    return redact_pii_value(value)


def _redact_sequence(
    value: Sequence[Any],
    rebuild: Callable[[list[Any]], Sequence[Any]],
) -> Sequence[Any]:
    redacted: list[Any] | None = None
    for index, original in enumerate(value):
        item = redact_pii_value(original)
        if item is original:
            continue
        if redacted is None:
            redacted = list(value)
        redacted[index] = item
    return value if redacted is None else rebuild(redacted)
