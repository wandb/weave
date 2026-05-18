"""PII redaction helpers for the Session SDK.

Routes through ``weave.utils.pii_redaction.redact_pii`` so output is
byte-identical to the @op tracer for the same input. Kept in its own
module so ``session.py`` stays focused on span lifecycle and the pure
attribute builders in ``session_otel.py`` stay decoupled from settings.

Each helper returns new objects — callers' inputs are never mutated.
"""

from __future__ import annotations

from typing import Any, cast

from weave.session.types import Message
from weave.utils.pii_redaction import redact_pii


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
