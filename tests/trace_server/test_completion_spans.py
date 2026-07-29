"""Agent span rows built from completion requests."""

from __future__ import annotations

import datetime
import json

from weave.trace_server.agents.completion_spans import build_completion_span
from weave.trace_server.credential_redaction import REDACTED_VALUE
from weave.trace_server.trace_server_interface import CompletionsCreateRequestInputs


def test_completion_span_redacts_credential_shaped_request_fields() -> None:
    """The raw dump carries the whole request, minus one hand-excluded field.

    `vertex_credentials` is left out of the dump by name. `extra_headers` is
    client-authored and is not, so the shared name policy is what covers it.
    """
    started_at = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
    span = build_completion_span(
        project_id="p1",
        trace_id="trace",
        span_id="span",
        conversation_id="conv",
        conversation_name="conv",
        started_at=started_at,
        ended_at=started_at + datetime.timedelta(seconds=1),
        provider_name="openai",
        model_name="gpt-4o",
        request_inputs=CompletionsCreateRequestInputs(
            model="gpt-4o",
            messages=[{"role": "user", "content": "hi"}],
            extra_headers={"authorization": "value-to-redact"},
            vertex_credentials="value-to-redact",
        ),
        response=None,
        wb_user_id="u-1",
        retention_days=0,
    )

    raw_dump = json.loads(span.raw_span_dump)
    assert raw_dump == {
        "inputs": {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "hi"}],
            "extra_headers": {"authorization": REDACTED_VALUE},
        }
    }
