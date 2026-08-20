"""PII redaction for parsed OTel spans on the trace-ingest write path."""

from __future__ import annotations

from typing import TYPE_CHECKING

from weave.trace_server.sensitive_data.policy import SensitiveDataPolicy, pii_enabled
from weave.trace_server.sensitive_data.walker import redact_pii_value

if TYPE_CHECKING:
    from weave.trace_server.opentelemetry.python_spans import Span


def redact_pii_from_span(span: Span, policy: SensitiveDataPolicy) -> None:
    """Redact supported PII in a span's customer-authored string values.

    Mirrors ``redact_credentials_from_span``: covers all four attribute
    containers a span carries (its own, its resource's, its events' and its
    links') plus the status message, because ``raw_span_dump`` and every
    attribute-derived column read from them. Must run before
    ``strip_inline_blobs_from_span`` so values are scanned while still inline,
    and before extraction so derived columns read the redacted span. Span and
    event names, IDs, trace state, and timestamps are structural and stay
    unchanged.
    """
    if not pii_enabled(policy):
        return
    span.attributes = redact_pii_value(span.attributes)
    if span.resource is not None:
        span.resource.attributes = redact_pii_value(span.resource.attributes)
    for event in span.events:
        event.attributes = redact_pii_value(event.attributes)
    for link in span.links:
        link.attributes = redact_pii_value(link.attributes)
    span.status.message = redact_pii_value(span.status.message)
