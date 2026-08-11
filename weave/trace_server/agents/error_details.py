"""Extract displayable error details from OTel exception events."""

import json
from typing import Any

from weave.trace_server.opentelemetry.helpers import get_attribute


def exception_event_details(
    events: list[dict[str, Any]],
) -> tuple[str, str]:
    """Return the latest exception event's type and message."""
    for event in reversed(events):
        if event.get("name") != "exception":
            continue
        attributes = event.get("attributes")
        if not isinstance(attributes, dict):
            continue
        exception_type = get_attribute(attributes, "exception.type")
        exception_message = get_attribute(attributes, "exception.message")
        type_text = str(exception_type) if exception_type is not None else ""
        message_text = str(exception_message) if exception_message is not None else ""
        if type_text or message_text:
            return type_text, message_text
    return "", ""


def exception_event_details_from_span_dump(
    raw_span_dump: object,
) -> tuple[str, str]:
    """Extract exception details from a stored raw OTel span dump."""
    if not isinstance(raw_span_dump, str) or not raw_span_dump:
        return "", ""
    try:
        raw_span = json.loads(raw_span_dump)
    except (json.JSONDecodeError, TypeError):
        return "", ""
    if not isinstance(raw_span, dict):
        return "", ""
    events = raw_span.get("events")
    if not isinstance(events, list):
        return "", ""
    return exception_event_details(
        [event for event in events if isinstance(event, dict)]
    )
