"""Tests for usage utility helpers."""

from datetime import datetime, timezone

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server import usage_utils


def make_call_schema(
    call_id: str,
    trace_id: str,
    parent_id: str | None,
    usage: dict | None = None,
    costs: dict | None = None,
) -> tsi.CallSchema:
    """Helper to create a CallSchema for testing."""
    summary: tsi.SummaryMap | None = None
    if usage or costs:
        summary = {}
        if usage:
            summary["usage"] = usage
        if costs:
            summary["weave"] = {"costs": costs}

    return tsi.CallSchema(
        id=call_id,
        project_id="test_project",
        op_name="test_op",
        trace_id=trace_id,
        parent_id=parent_id,
        started_at=datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        attributes={},
        inputs={},
        output=None,
        summary=summary,
    )


class TestUsageUtils:
    """Tests for usage extraction helpers."""

    def test_single_call_with_usage(self):
        """Test extraction from a single call."""
        call = make_call_schema(
            call_id="call1",
            trace_id="trace1",
            parent_id=None,
            usage={
                "gpt-4": {
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "total_tokens": 150,
                    "requests": 1,
                }
            },
        )

        result = usage_utils.extract_usage_from_call(call, include_costs=False)

        assert "gpt-4" in result
        assert result["gpt-4"].prompt_tokens == 100
        assert result["gpt-4"].completion_tokens == 50
        assert result["gpt-4"].total_tokens == 150
        assert result["gpt-4"].requests == 1

    def test_input_output_tokens_alias(self):
        """Test that input_tokens/output_tokens are handled as aliases."""
        call = make_call_schema(
            call_id="call1",
            trace_id="trace1",
            parent_id=None,
            usage={
                "gpt-4": {
                    "input_tokens": 100,
                    "output_tokens": 50,
                }
            },
        )

        result = usage_utils.extract_usage_from_call(call, include_costs=False)

        assert result["gpt-4"].prompt_tokens == 100
        assert result["gpt-4"].completion_tokens == 50
