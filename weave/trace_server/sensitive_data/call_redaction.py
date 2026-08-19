"""Field-selective credential and PII redaction for call writes."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, TypeVar, cast

from pydantic import BaseModel

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.sensitive_data.budget import ScanBudget
from weave.trace_server.sensitive_data.policy import SensitiveDataPolicy, pii_enabled
from weave.trace_server.sensitive_data.walker import redact_pii_value

TModel = TypeVar("TModel", bound=BaseModel)


def redact_call_start(
    req: tsi.CallStartReq | tsi.CallStartV2Req,
    policy: SensitiveDataPolicy,
    budget: ScanBudget | None = None,
) -> tsi.CallStartReq | tsi.CallStartV2Req:
    """Redact customer-authored fields on a v1 or v2 call start."""
    if not pii_enabled(policy):
        return req
    scan_budget = budget or ScanBudget()
    start = _redact_fields(
        req.start, ("inputs", "attributes", "otel_dump", "display_name"), scan_budget
    )
    return req if start is req.start else req.model_copy(update={"start": start})


def redact_call_end(
    req: tsi.CallEndReq | tsi.CallEndV2Req,
    policy: SensitiveDataPolicy,
    budget: ScanBudget | None = None,
) -> tsi.CallEndReq | tsi.CallEndV2Req:
    """Redact customer-authored fields on a v1 or v2 call end."""
    if not pii_enabled(policy):
        return req
    scan_budget = budget or ScanBudget()
    end = _redact_fields(req.end, ("output", "summary", "exception"), scan_budget)
    return req if end is req.end else req.model_copy(update={"end": end})


def redact_call_batch(
    req: tsi.CallCreateBatchReq,
    policy: SensitiveDataPolicy,
    budget: ScanBudget | None = None,
) -> tsi.CallCreateBatchReq:
    """Redact every item using one request-wide scan budget."""
    if not pii_enabled(policy):
        return req
    scan_budget = budget or ScanBudget()

    def redact_item(
        item: tsi.CallBatchStartMode | tsi.CallBatchEndMode,
    ) -> tsi.CallBatchStartMode | tsi.CallBatchEndMode:
        redacted_req: (
            tsi.CallStartReq | tsi.CallStartV2Req | tsi.CallEndReq | tsi.CallEndV2Req
        )
        if isinstance(item, tsi.CallBatchStartMode):
            redacted_req = redact_call_start(item.req, policy, scan_budget)
        elif isinstance(item, tsi.CallBatchEndMode):
            redacted_req = redact_call_end(item.req, policy, scan_budget)
        else:
            raise TypeError(f"Unknown call batch item type: {type(item).__name__}")
        return (
            item
            if redacted_req is item.req
            else item.model_copy(update={"req": redacted_req})
        )

    batch = _redact_sequence(req.batch, redact_item)
    return req if batch is req.batch else req.model_copy(update={"batch": batch})


def redact_calls_complete(
    req: tsi.CallsUpsertCompleteReq,
    policy: SensitiveDataPolicy,
    budget: ScanBudget | None = None,
) -> tsi.CallsUpsertCompleteReq:
    """Redact every completed call using one request-wide scan budget."""
    if not pii_enabled(policy):
        return req
    scan_budget = budget or ScanBudget()

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
                "output",
                "summary",
                "exception",
            ),
            scan_budget,
        )

    batch = _redact_sequence(req.batch, redact_item)
    return req if batch is req.batch else req.model_copy(update={"batch": batch})


def redact_call_update(
    req: tsi.CallUpdateReq,
    policy: SensitiveDataPolicy,
    budget: ScanBudget | None = None,
) -> tsi.CallUpdateReq:
    """Redact the customer-authored display name on a call update."""
    if not pii_enabled(policy):
        return req
    return _redact_fields(req, ("display_name",), budget or ScanBudget())


def _redact_fields(
    model: TModel, field_names: tuple[str, ...], budget: ScanBudget
) -> TModel:
    updates: dict[str, Any] = {}
    for field_name in field_names:
        original = getattr(model, field_name)
        redacted = redact_pii_value(original, budget)
        if redacted is not original:
            updates[field_name] = redacted
    return model if not updates else cast(TModel, model.model_copy(update=updates))


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
