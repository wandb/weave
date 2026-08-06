"""PII redaction — used by both @op tracer and Conversation SDK.

Two layers:

- ``redact_pii`` / ``redact_pii_string`` are the primitives that walk
  dicts, lists, and dataclasses applying Presidio.
- ``redact_messages`` / ``redact_system_instructions`` are the Conversation
  SDK helpers shaped for typed Message payloads. Message protocol fields are
  preserved while textual payload fields are passed to Presidio.

``presidio`` is an optional dependency gated by ``WEAVE_REDACT_PII``.
Imports happen inside ``_get_engines`` so the module loads without it —
matches the pattern in ``weave/scorers/presidio_guardrail.py``. Lets
tests ``mock.patch`` the redaction functions without installing the
NLP stack, and lets users who never enable redaction skip the install.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from weave.conversation.types import (
    Message,
    MessagePart,
    ReasoningPart,
    TextPart,
    ToolCallPart,
    ToolCallResponsePart,
)
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


def _redact_pii_string_with_engines(
    data: str,
    analyzer: AnalyzerEngine,
    anonymizer: AnonymizerEngine,
    entities: list[str],
) -> str:
    if not data:
        return data
    results = analyzer.analyze(text=data, language="en", entities=entities)
    redacted = anonymizer.anonymize(text=data, analyzer_results=results)
    return redacted.text


def redact_pii(
    data: dict[str, Any] | str,
) -> dict[str, Any] | str:
    if isinstance(data, str):
        return redact_pii_string(data)

    analyzer, anonymizer = _get_engines()
    entities = _get_redaction_entities()

    def redact_recursive(value: Any) -> Any:
        if isinstance(value, str):
            return _redact_pii_string_with_engines(
                value, analyzer, anonymizer, entities
            )
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

    return redact_recursive(data)


def redact_pii_string(data: str) -> str:
    """Redact PII in a single string."""
    if not data:
        # Short-circuit empty input — _get_engines() is uncached and traces
        # commonly contain empty strings, so loading Presidio every call is costly.
        return data
    analyzer, anonymizer = _get_engines()
    entities = _get_redaction_entities()
    return _redact_pii_string_with_engines(data, analyzer, anonymizer, entities)


def _redact_message_part(
    part: MessagePart, redact_string: Callable[[str, str], str]
) -> MessagePart:
    if isinstance(part, (TextPart, ReasoningPart)):
        return part.model_copy(
            update={"content": redact_string("content", part.content)}, deep=True
        )
    if isinstance(part, ToolCallPart):
        return part.model_copy(
            update={"arguments": redact_string("arguments", part.arguments)},
            deep=True,
        )
    if isinstance(part, ToolCallResponsePart):
        return part.model_copy(
            update={"response": redact_string("response", part.response)}, deep=True
        )
    return part.model_copy(deep=True)


def redact_messages(messages: list[Message]) -> list[Message]:
    """Redact textual payloads without sending protocol fields to Presidio.

    Roles, part discriminators, tool identifiers, MIME metadata, blob data,
    URIs, and file identifiers are structural values and remain byte-for-byte
    stable. Flat message content, text/reasoning content, tool arguments, and
    tool responses use the same Presidio engines and configured redact keys as
    ``redact_pii``.
    """
    if not messages:
        return messages

    analyzer, anonymizer = _get_engines()
    entities = _get_redaction_entities()

    def redact_string(field_name: str, value: str) -> str:
        if should_redact(field_name):
            return REDACTED_VALUE
        return _redact_pii_string_with_engines(value, analyzer, anonymizer, entities)

    return [
        message.model_copy(
            update={
                "content": redact_string("content", message.content),
                "parts": [
                    _redact_message_part(part, redact_string) for part in message.parts
                ],
            },
            deep=True,
        )
        for message in messages
    ]


def redact_system_instructions(instructions: list[str]) -> list[str]:
    """Redact each system instruction. Empty in → same out."""
    if not instructions:
        return instructions
    return [redact_pii_string(instruction) for instruction in instructions]


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
