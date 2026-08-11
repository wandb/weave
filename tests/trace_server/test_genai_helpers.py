"""Unit tests for GenAI agent helper functions."""

import datetime
import json

import pytest

from weave.trace_server.agents.helpers import genai_span_to_row, normalize_span_row
from weave.trace_server.agents.schema import (
    ALL_SPAN_INSERT_COLUMNS,
    AgentSpanCHInsertable,
    NormalizedMessage,
)


def test_genai_span_to_row_converts_messages_to_named_tuples() -> None:
    span = AgentSpanCHInsertable(
        project_id="p1",
        trace_id="t1",
        span_id="s1",
        span_name="chat",
        started_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
        input_messages=[NormalizedMessage(role="user", content="hi")],
    )

    row = genai_span_to_row(span)

    input_messages_idx = ALL_SPAN_INSERT_COLUMNS.index("input_messages")
    assert row[input_messages_idx] == [("user", "hi", "")]


def test_normalize_span_row_returns_new_dict() -> None:
    row = {
        "input_messages": [("user", "hi", "")],
        "output_messages": [],
    }

    normalized = normalize_span_row(row)

    assert normalized is not row
    assert row["input_messages"] == [("user", "hi", "")]
    assert normalized["input_messages"] == [
        {"role": "user", "content": "hi", "finish_reason": ""}
    ]


def test_normalize_span_row_fills_error_details_from_raw_span_dump() -> None:
    normalized = normalize_span_row(
        {
            "status_code": "ERROR",
            "status_message": "",
            "error_type": "",
            "raw_span_dump": json.dumps(
                {
                    "events": [
                        {
                            "name": "exception",
                            "attributes": {
                                "exception": {
                                    "type": "asyncio.exceptions.CancelledError",
                                    "message": "stream cancelled",
                                }
                            },
                        }
                    ]
                }
            ),
        }
    )

    assert normalized["error_type"] == "asyncio.exceptions.CancelledError"
    assert normalized["status_message"] == "stream cancelled"


def test_normalize_span_row_preserves_explicit_error_details() -> None:
    normalized = normalize_span_row(
        {
            "status_code": "ERROR",
            "status_message": "rate limited",
            "error_type": "RateLimitError",
            "raw_span_dump": json.dumps(
                {
                    "events": [
                        {
                            "name": "exception",
                            "attributes": {
                                "exception": {
                                    "type": "FallbackError",
                                    "message": "fallback message",
                                }
                            },
                        }
                    ]
                }
            ),
        }
    )

    assert normalized["error_type"] == "RateLimitError"
    assert normalized["status_message"] == "rate limited"


def test_normalize_span_row_rejects_invalid_message_shape() -> None:
    with pytest.raises(ValueError, match="tuple must have 3 values"):
        normalize_span_row({"input_messages": [("user", "hi")]})

    with pytest.raises(TypeError, match="must be a tuple or dict"):
        normalize_span_row({"input_messages": ["hi"]})
