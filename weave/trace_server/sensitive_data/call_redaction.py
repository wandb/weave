"""Field-selective credential and PII redaction for call writes."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, TypeVar

from pydantic import BaseModel

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.errors import RequestTooLarge
from weave.trace_server.sensitive_data.policy import SensitiveDataPolicy, pii_enabled
from weave.trace_server.sensitive_data.walker import (
    NESTING_LIMIT_MESSAGE,
    redact_pii_value,
)

TModel = TypeVar("TModel", bound=BaseModel)
# Constrained so v1 and v2 requests keep their exact type for consumers.
TCallStartReq = TypeVar("TCallStartReq", tsi.CallStartReq, tsi.CallStartV2Req)
TCallEndReq = TypeVar("TCallEndReq", tsi.CallEndReq, tsi.CallEndV2Req)


def redact_call_start(
    req: TCallStartReq,
    policy: SensitiveDataPolicy,
) -> TCallStartReq:
    """Redact customer-authored fields on a v1 or v2 call start.

    ``op_name`` is scanned as content: SDK-written op refs pass through the
    walker's ref-preservation rule unchanged, so only free-string op names
    from direct writers can be rewritten.
    """
    if not pii_enabled(policy):
        return req
    start = _redact_fields(
        req.start,
        ("inputs", "attributes", "otel_dump", "display_name", "op_name"),
    )
    return req if start is req.start else req.model_copy(update={"start": start})


def redact_call_end(
    req: TCallEndReq,
    policy: SensitiveDataPolicy,
) -> TCallEndReq:
    """Redact customer-authored fields on a v1 or v2 call end."""
    if not pii_enabled(policy):
        return req
    end = _redact_fields(req.end, ("output", "summary", "exception"))
    return req if end is req.end else req.model_copy(update={"end": end})


def redact_calls_complete(
    req: tsi.CallsUpsertCompleteReq,
    policy: SensitiveDataPolicy,
) -> tsi.CallsUpsertCompleteReq:
    """Redact every completed call in the batch."""
    if not pii_enabled(policy):
        return req

    def redact_item(
        item: tsi.CompletedCallSchemaForInsert,
    ) -> tsi.CompletedCallSchemaForInsert:
        return _redact_fields(
            item,
            (
                "inputs",
                "attributes",
                "otel_dump",
                "display_name",
                "op_name",
                "output",
                "summary",
                "exception",
            ),
        )

    batch = _redact_sequence(req.batch, redact_item)
    return req if batch is req.batch else req.model_copy(update={"batch": batch})


def redact_call_update(
    req: tsi.CallUpdateReq,
    policy: SensitiveDataPolicy,
) -> tsi.CallUpdateReq:
    """Redact the customer-authored display name on a call update."""
    if not pii_enabled(policy):
        return req
    return _redact_fields(req, ("display_name",))


def _redact_fields(model: TModel, field_names: tuple[str, ...]) -> TModel:
    updates: dict[str, Any] = {}
    try:
        for field_name in field_names:
            original = getattr(model, field_name)
            redacted = redact_pii_value(original)
            if redacted is not original:
                updates[field_name] = redacted
    except RecursionError as error:
        raise RequestTooLarge(NESTING_LIMIT_MESSAGE) from error
    return model if not updates else model.model_copy(update=updates)


TItem = TypeVar("TItem")


def _redact_sequence(
    values: Sequence[TItem], redact: Callable[[TItem], TItem]
) -> Sequence[TItem]:
    redacted: list[TItem] | None = None
    for index, original in enumerate(values):
        item = redact(original)
        if item is original:
            continue
        if redacted is None:
            redacted = list(values)
        redacted[index] = item
    return values if redacted is None else redacted
