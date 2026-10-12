"""PII redaction for parsed OTel spans on the trace-ingest write path."""

from __future__ import annotations

from typing import TYPE_CHECKING

from weave.trace_server.errors import RequestTooLarge
from weave.trace_server.sensitive_data.policy import SensitiveDataPolicy, pii_enabled
from weave.trace_server.sensitive_data.walker import (
    NESTING_LIMIT_MESSAGE,
    redact_pii_value,
)

if TYPE_CHECKING:
    from weave.trace_server.opentelemetry.python_spans import Resource, Span


def redact_pii_from_span(span: Span, policy: SensitiveDataPolicy) -> None:
    """Redact supported PII in a span's customer-authored string values.

    Mirrors ``redact_credentials_from_span`` for the containers each span
    owns: its own, its events' and its links' attributes, plus the status
    message, because ``raw_span_dump`` and every attribute-derived column
    read from them. The shared ``Resource`` is redacted once per
    resource-spans group by ``redact_pii_from_resource``, not per span. Must
    run before ``strip_inline_blobs_from_span`` so values are scanned while
    still inline, and before extraction so derived columns read the redacted
    span. Span and event names are scanned like content, so a PII-bearing
    name is rewritten even though names feed the ``span_name``,
    ``operation_name``, and ``agent_name`` grouping columns. IDs, trace
    state, and timestamps are structural and stay unchanged. Non-string
    leaves (numbers, bools, bytes) pass through: ``pii-v1`` scans strings and
    never decodes payloads.

    Raises ``RequestTooLarge`` for values nested too deeply to scan.
    """
    if not pii_enabled(policy):
        return
    try:
        span.name = redact_pii_value(span.name)
        span.attributes = redact_pii_value(span.attributes)
        for event in span.events:
            event.name = redact_pii_value(event.name)
            event.attributes = redact_pii_value(event.attributes)
        for link in span.links:
            link.attributes = redact_pii_value(link.attributes)
        span.status.message = redact_pii_value(span.status.message)
    except RecursionError as error:
        raise RequestTooLarge(NESTING_LIMIT_MESSAGE) from error


def redact_pii_from_resource(
    resource: Resource | None, policy: SensitiveDataPolicy
) -> None:
    """Redact the shared ``Resource`` once per resource-spans group.

    Every span parsed from one ``ResourceSpans`` holds the same ``Resource``
    object, so one pass here avoids rescanning it for every span.

    Raises ``RequestTooLarge`` for values nested too deeply to scan.
    """
    if resource is None or not pii_enabled(policy):
        return
    try:
        resource.attributes = redact_pii_value(resource.attributes)
    except RecursionError as error:
        raise RequestTooLarge(NESTING_LIMIT_MESSAGE) from error
