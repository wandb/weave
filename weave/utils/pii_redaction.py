"""PII redaction — used by both @op tracer and Session SDK.

Two layers:

- ``redact_pii`` / ``redact_pii_string`` are the recursive primitives that
  walk dicts, lists, and dataclasses applying Presidio.
- ``redact_string`` / ``redact_messages`` / ``redact_system_instructions``
  are the Session SDK helpers shaped for typed Message payloads (dump →
  redact → restore Literal discriminators → revalidate).

``presidio`` is an optional dependency gated by ``WEAVE_REDACT_PII``.
Presidio is imported lazily inside the redaction functions so the module
loads without it — same pattern as ``weave/scorers/presidio_guardrail.py``.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any, cast

from weave.session.types import Message
from weave.telemetry import trace_sentry
from weave.trace.settings import redact_pii_exclude_fields, redact_pii_fields
from weave.utils.sanitize import REDACTED_VALUE, redact_dataclass_fields, should_redact

if TYPE_CHECKING:
    from presidio_analyzer import AnalyzerEngine
    from presidio_anonymizer import AnonymizerEngine

_PRESIDIO_INSTALL_HINT = (
    "presidio is required for PII redaction. "
    "Install with `pip install 'weave[presidio]'`."
)


def _get_engines() -> tuple[AnalyzerEngine, AnonymizerEngine]:
    """Lazy-load presidio engines, re-raising with a friendly install hint."""
    try:
        from presidio_analyzer import AnalyzerEngine
        from presidio_anonymizer import AnonymizerEngine
    except ImportError as e:
        raise ImportError(_PRESIDIO_INSTALL_HINT) from e
    return AnalyzerEngine(), AnonymizerEngine()


DEFAULT_REDACTED_FIELDS = [
    "CREDIT_CARD",
    "CRYPTO",
    "EMAIL_ADDRESS",
    "IBAN_CODE",
    "IP_ADDRESS",
    "LOCATION",
    "PERSON",
    "PHONE_NUMBER",
    "US_SSN",
    "US_BANK_NUMBER",
    "US_DRIVER_LICENSE",
    "US_PASSPORT",
    "UK_NHS",
    "UK_NINO",
    "ES_NIF",
    "IN_AADHAAR",
    "IN_PAN",
    "FI_PERSONAL_IDENTITY_CODE",
]


def _get_redaction_entities() -> list[str]:
    fields = redact_pii_fields() or DEFAULT_REDACTED_FIELDS
    exclude = redact_pii_exclude_fields()
    return [e for e in fields if e not in exclude]


def redact_pii(
    data: dict[str, Any] | str,
) -> dict[str, Any] | str:
    analyzer, anonymizer = _get_engines()
    entities = _get_redaction_entities()

    def redact_recursive(value: Any) -> Any:
        if isinstance(value, str):
            results = analyzer.analyze(text=value, language="en", entities=entities)
            redacted = anonymizer.anonymize(text=value, analyzer_results=results)
            return redacted.text
        elif isinstance(value, dict):
            result = {}
            for k, v in value.items():
                # Check if this key should be redacted based on custom redact keys
                if isinstance(k, str) and should_redact(k):
                    result[k] = REDACTED_VALUE
                else:
                    result[k] = redact_recursive(v)
            return result
        elif isinstance(value, list):
            return [redact_recursive(item) for item in value]
        elif dataclasses.is_dataclass(value):
            return redact_dataclass_fields(value, redact_recursive)
        else:
            return value

    if isinstance(data, str):
        return redact_pii_string(data)

    return redact_recursive(data)


def redact_pii_string(data: str) -> str:
    analyzer, anonymizer = _get_engines()
    entities = _get_redaction_entities()
    results = analyzer.analyze(text=data, language="en", entities=entities)
    redacted = anonymizer.anonymize(text=data, analyzer_results=results)
    return redacted.text


def redact_string(s: str) -> str:
    """Redact PII in a single string. Empty in → empty out (skips Presidio)."""
    if not s:
        return s
    return cast(str, redact_pii(s))


def _restore_literals(redacted: dict[str, Any], original: dict[str, Any]) -> None:
    """Restore structural Literal-typed fields from the original dump.

    The recursive redactor walks every string in the dict, which would
    corrupt fields whose values are constrained by Pydantic ``Literal``
    annotations (``role``, part ``type`` discriminators). In production
    with Presidio, none of those values are detected as PII so this is
    a no-op. We restore them anyway so the revalidate step is robust to
    custom recognizers and to keep the redactor focused on user content.
    """
    if "role" in original:
        redacted["role"] = original["role"]
    orig_parts = original.get("parts") or []
    red_parts = redacted.get("parts") or []
    for orig_p, red_p in zip(orig_parts, red_parts, strict=False):
        if isinstance(orig_p, dict) and isinstance(red_p, dict) and "type" in orig_p:
            red_p["type"] = orig_p["type"]


def redact_messages(msgs: list[Message] | None) -> list[Message] | None:
    """Redact PII in each Message via dump → redact → revalidate.

    Uses ``Message.model_dump`` / ``model_validate`` so the dict shape
    walks through the same recursive redactor ``@op`` uses. Preserves
    discriminated-union parts (TextPart, ToolCallPart, etc.) by
    restoring ``role`` and part ``type`` from the original dump before
    revalidation — those are Pydantic ``Literal`` fields and would fail
    validation if a recognizer happened to alter them.
    """
    if not msgs:
        return msgs
    out: list[Message] = []
    for m in msgs:
        dumped = m.model_dump()
        redacted = cast(dict[str, Any], redact_pii(dumped))
        _restore_literals(redacted, dumped)
        out.append(Message.model_validate(redacted))
    return out


def redact_system_instructions(insts: list[str] | None) -> list[str] | None:
    """Redact each system instruction. None/empty in → same out."""
    if not insts:
        return insts
    return [redact_string(s) for s in insts]


def track_pii_redaction_enabled(
    username: str, entity_name: str, project_name: str
) -> None:
    trace_sentry.global_trace_sentry.track_event(
        "pii_redaction_enabled",
        {
            "entity_name": entity_name,
            "project_name": project_name,
        },
        username,
    )
