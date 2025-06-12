import os
import pytest

import weave
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


def assert_correct_calls_for_simple_pipeline(calls: list[Call]) -> None:
    """Assert the expected call structure for a simple Verdict pipeline."""
    flattened = flatten_calls(calls)
    assert len(flattened) >= 1  # At least one call should be created
    assert_ends_and_errors(flattened)

    # Check that we have the expected call names
    got = [(op_name_from_ref(c.op_name), d) for (c, d) in flattened]

    # The first call should be the Pipeline
    assert got[0][0] == "Pipeline"
    assert got[0][1] == 0  # Root level


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
    before_record_request=filter_body,
)
def test_simple_verdict_pipeline(client: WeaveClient) -> None:
    """Test that a simple Verdict pipeline is traced to Weave."""
    try:
        import verdict
        from verdict import Pipeline
        from verdict.schema import Schema
        from verdict.common.judge import JudgeUnit
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

    # Check the call structure
    assert_correct_calls_for_simple_pipeline(calls)

    # Verify the first call is our pipeline
    pipeline_call = calls[0]
    assert (
        "Pipeline" in pipeline_call.op_name or "TestPipeline" in pipeline_call.op_name
    )


@pytest.mark.skip_clickhouse_client
def test_verdict_pipeline_without_client() -> None:
    """Test that Verdict pipeline doesn't crash when no Weave client is available."""
    try:
        import verdict
        from verdict import Pipeline
        from verdict.schema import Schema
        from verdict.common.judge import JudgeUnit
    except ImportError:
        pytest.skip("verdict not available")

    # Create pipeline without a client context
    pipeline = Pipeline(name="TestPipeline")
    pipeline = pipeline >> JudgeUnit().prompt("Rate this text: {source.text}")

    test_data = Schema.of(text="This is a test message")

    # This should not crash even without a client
    response = pipeline.run(test_data)

    # If we get here without an exception, the test passes
    assert response is not None


@pytest.mark.skip_clickhouse_client
def test_verdict_with_weave_op(client: WeaveClient) -> None:
    """Test Verdict pipeline inside a Weave op to verify nested tracing."""
    try:
        import verdict
        from verdict import Pipeline
        from verdict.schema import Schema
        from verdict.common.judge import JudgeUnit
    except ImportError:
        pytest.skip("verdict not available")

    @weave.op()
    def run_verdict_pipeline(text: str):
        pipeline = Pipeline(name="NestedPipeline")
        pipeline = pipeline >> JudgeUnit().prompt("Analyze: {source.text}")

        test_data = Schema.of(text=text)
        return pipeline.run(test_data)

    # Run the nested pipeline
    result = run_verdict_pipeline("Test input for nested pipeline")

    # Get calls from Weave client
    calls = list(client.calls(filter=tsi.CallsFilter(trace_roots_only=True)))

    # Should have at least the weave op call
    assert len(calls) > 0

    # The root call should be our Weave op
    root_call = calls[0]
    assert "run_verdict_pipeline" in root_call.op_name

    # Should have child calls from the Verdict pipeline
    children = root_call.children()
    assert len(children) > 0
