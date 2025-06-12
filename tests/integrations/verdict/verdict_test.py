import pytest

from weave.integrations.integration_utilities import (
    filter_body,
    flatten_calls,
    op_name_from_ref,
)
from weave.trace.weave_client import Call, WeaveClient
from weave.trace_server import trace_server_interface as tsi


def assert_ends_and_errors(calls: list[tuple[Call, int]]) -> None:
    """Helper function to check that all calls ended without errors."""
    for call, depth in calls:
        assert call.ended_at is not None
        assert call.exception is None


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
    before_record_request=filter_body,
)
def test_simple_verdict_pipeline(client: WeaveClient) -> None:
    """Test that a simple Verdict pipeline is traced to Weave."""
    try:
        from verdict import Pipeline
        from verdict.common.judge import JudgeUnit
        from verdict.schema import Schema
    except ImportError:
        pytest.skip("verdict not available")

    # Create a simple pipeline with a JudgeUnit
    pipeline = Pipeline(name="TestPipeline")
    pipeline = pipeline >> JudgeUnit().prompt("Rate this text: {source.text}")

    # Create test data
    test_data = Schema.of(text="This is a test message")

    # Run the pipeline - this should create Weave traces
    response = pipeline.run(test_data)

    # Get calls from Weave client
    calls = list(client.calls(filter=tsi.CallsFilter(trace_roots_only=True)))

    # Assert that we got some calls
    assert len(calls) > 0

    # Verify the first call is our pipeline
    pipeline_call = calls[0]
    assert (
        "Pipeline" in pipeline_call.op_name or "TestPipeline" in pipeline_call.op_name
    )

    flattened = flatten_calls(calls)
    assert len(flattened) >= 1  # At least one call should be created
    assert_ends_and_errors(flattened)

    # Check that we have the expected call names
    got = [(op_name_from_ref(c.op_name), d) for (c, d) in flattened]

    # The first call should be the Pipeline
    assert got[0][0] == "TestPipeline"
    assert got[0][1] == 0  # Root level
