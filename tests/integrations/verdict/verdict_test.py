import pytest

from weave.integrations.integration_utilities import (
    filter_body,
    flatten_calls,
    op_name_from_ref,
)
from weave.trace.call import Call
from weave.trace.weave_client import WeaveClient
from weave.trace_server import trace_server_interface as tsi


def assert_ends_and_errors(calls: list[tuple[Call, int]]) -> None:
    """Helper function to check that all calls ended without errors."""
    for call, _ in calls:
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
    calls = list(client.get_calls(filter=tsi.CallsFilter(trace_roots_only=True)))

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


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
    before_record_request=filter_body,
)
def test_verdict_layer_tracing(client: WeaveClient) -> None:
    """Test that Verdict layers with multiple units are properly traced."""
    try:
        from verdict import Layer, Pipeline
        from verdict.common.judge import JudgeUnit
        from verdict.schema import Schema
        from verdict.transform import MeanPoolUnit
    except ImportError:
        pytest.skip("verdict not available")

    # Create a pipeline with a layer containing multiple judges (ensemble)
    pipeline = Pipeline(name="LayerTestPipeline")
    pipeline = (
        pipeline
        >> Layer([JudgeUnit().prompt("Rate this: {source.text}")], repeat=3)
        >> MeanPoolUnit()
    )

    # Create test data
    test_data = Schema.of(text="This is a test message for layer tracing")

    # Run the pipeline
    response = pipeline.run(test_data)

    # Get calls from Weave client
    calls = list(client.get_calls(filter=tsi.CallsFilter(trace_roots_only=True)))
    assert len(calls) > 0

    flattened = flatten_calls(calls)
    assert_ends_and_errors(flattened)

    # Check that we have multiple judge calls within the layer
    got = [(op_name_from_ref(c.op_name), d) for (c, d) in flattened]

    # Should have pipeline, layer, multiple judges, and mean pool unit
    pipeline_calls = [call for call in got if "LayerTestPipeline" in call[0]]
    judge_calls = [call for call in got if "Judge" in call[0]]
    meanpool_calls = [call for call in got if "MeanPool" in call[0]]

    assert len(pipeline_calls) >= 1  # At least one pipeline call
    assert len(judge_calls) >= 3  # At least 3 judge calls from the layer
    assert len(meanpool_calls) >= 1  # At least one mean pool call


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
    before_record_request=filter_body,
)
def test_verdict_custom_unit_tracing(client: WeaveClient) -> None:
    """Test that custom Verdict units are properly traced."""
    try:
        from verdict import Pipeline, Unit
        from verdict.prompt import Prompt
        from verdict.schema import Schema
    except ImportError:
        pytest.skip("verdict not available")

    # Define a custom unit
    class CustomTestUnit(Unit):
        _char = "CustomTest"

        class ResponseSchema(Schema):
            result: str

        _prompt = Prompt.from_template("Respond with 'tested': {source.input}")

        def process(self, input_data, response):
            return self.ResponseSchema(result=f"Processed: {response.result}")

    # Create pipeline with custom unit
    pipeline = Pipeline(name="CustomUnitPipeline")
    pipeline = pipeline >> CustomTestUnit()

    # Create test data
    test_data = Schema.of(input="custom unit test")

    # Run the pipeline
    response = pipeline.run(test_data)

    # Get calls from Weave client
    calls = list(client.get_calls(filter=tsi.CallsFilter(trace_roots_only=True)))
    assert len(calls) > 0

    flattened = flatten_calls(calls)
    assert_ends_and_errors(flattened)

    # Check for custom unit traces
    got = [(op_name_from_ref(c.op_name), d) for (c, d) in flattened]
    custom_calls = [call for call in got if "CustomTest" in call[0]]

    assert len(custom_calls) >= 1  # Should have custom unit call


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
    before_record_request=filter_body,
)
def test_verdict_block_tracing(client: WeaveClient) -> None:
    """Test that Verdict blocks are properly traced."""
    try:
        from verdict import Block, Pipeline
        from verdict.common.judge import JudgeUnit
        from verdict.schema import Schema
    except ImportError:
        pytest.skip("verdict not available")

    # Create a complex block structure
    judge1 = JudgeUnit(name="FirstJudge").prompt("Rate this: {source.text}")
    judge2 = JudgeUnit(name="SecondJudge").prompt(
        "Verify: {previous.score}, Text: {source.text}"
    )

    block = Block() >> judge1 >> judge2

    pipeline = Pipeline(name="BlockTestPipeline")
    pipeline = pipeline >> block

    # Create test data
    test_data = Schema.of(text="This is a test for block tracing")

    # Run the pipeline
    response = pipeline.run(test_data)

    # Get calls from Weave client
    calls = list(client.get_calls(filter=tsi.CallsFilter(trace_roots_only=True)))
    assert len(calls) > 0

    flattened = flatten_calls(calls)
    assert_ends_and_errors(flattened)

    # Check for proper hierarchical tracing
    got = [(op_name_from_ref(c.op_name), d) for (c, d) in flattened]

    # Should have pipeline and both judges
    pipeline_calls = [call for call in got if "BlockTestPipeline" in call[0]]
    judge_calls = [call for call in got if "Judge" in call[0]]

    assert len(pipeline_calls) >= 1
    assert len(judge_calls) >= 2  # Should have both judges


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
    before_record_request=filter_body,
)
def test_verdict_dataset_execution_tracing(client: WeaveClient) -> None:
    """Test that Verdict dataset execution is properly traced."""
    try:
        from datasets import Dataset
        from verdict import Pipeline
        from verdict.common.judge import JudgeUnit
        from verdict.dataset import DatasetWrapper
    except ImportError:
        pytest.skip("verdict or datasets not available")

    # Create a simple pipeline
    pipeline = Pipeline(name="DatasetTestPipeline")
    pipeline = pipeline >> JudgeUnit().prompt("Rate this: {source.text}")

    # Create test dataset
    test_dataset = Dataset.from_list(
        [{"text": "First test message"}, {"text": "Second test message"}]
    )
    dataset_wrapper = DatasetWrapper(test_dataset)

    # Run the pipeline on dataset
    response, leaf_prefixes = pipeline.run_from_dataset(
        dataset_wrapper, max_workers=2, graceful=True
    )

    # Get calls from Weave client
    calls = list(client.get_calls(filter=tsi.CallsFilter(trace_roots_only=True)))
    assert len(calls) > 0

    flattened = flatten_calls(calls)
    assert_ends_and_errors(flattened)

    # Check for dataset execution traces
    got = [(op_name_from_ref(c.op_name), d) for (c, d) in flattened]

    pipeline_calls = [call for call in got if "DatasetTestPipeline" in call[0]]
    judge_calls = [call for call in got if "Judge" in call[0]]

    assert len(pipeline_calls) >= 1
    # Should have multiple judge calls (one per dataset item)
    assert len(judge_calls) >= 2


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
    before_record_request=filter_body,
)
def test_verdict_layer_configurations_tracing(client: WeaveClient) -> None:
    """Test different layer configurations are properly traced."""
    try:
        from verdict import Layer, Pipeline
        from verdict.common.judge import JudgeUnit
        from verdict.schema import Schema
    except ImportError:
        pytest.skip("verdict not available")

    # Test chain configuration (sequential execution)
    pipeline = Pipeline(name="ChainTestPipeline")
    pipeline = pipeline >> Layer(
        [
            JudgeUnit(name="ChainJudge1").prompt("Rate: {source.text}"),
            JudgeUnit(name="ChainJudge2").prompt("Refine: {previous.score}"),
        ],
        inner="chain",
    )

    # Create test data
    test_data = Schema.of(text="Test message for chain tracing")

    # Run the pipeline
    response = pipeline.run(test_data)

    # Get calls from Weave client
    calls = list(client.get_calls(filter=tsi.CallsFilter(trace_roots_only=True)))
    assert len(calls) > 0

    flattened = flatten_calls(calls)
    assert_ends_and_errors(flattened)

    # Check for chain execution traces
    got = [(op_name_from_ref(c.op_name), d) for (c, d) in flattened]

    pipeline_calls = [call for call in got if "ChainTestPipeline" in call[0]]
    judge_calls = [call for call in got if "Judge" in call[0]]

    assert len(pipeline_calls) >= 1
    assert len(judge_calls) >= 2  # Should have both chain judges


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
    before_record_request=filter_body,
)
def test_verdict_complex_pipeline_tracing(client: WeaveClient) -> None:
    """Test complex nested pipeline structures are properly traced."""
    try:
        from verdict import Block, Layer, Pipeline
        from verdict.common.judge import JudgeUnit
        from verdict.schema import Schema
        from verdict.transform import MeanPoolUnit
    except ImportError:
        pytest.skip("verdict not available")

    # Create a complex nested structure
    # Layer of judges -> hierarchical verification -> aggregation
    judge_layer = Layer([JudgeUnit().prompt("Rate: {source.text}")], repeat=2)
    verifier = JudgeUnit(name="Verifier").prompt("Verify: {previous.judge[0].score}")
    aggregator = MeanPoolUnit()

    # Complex block structure
    complex_block = Block() >> judge_layer >> verifier >> aggregator

    pipeline = Pipeline(name="ComplexPipeline")
    pipeline = pipeline >> complex_block

    # Create test data
    test_data = Schema.of(text="Complex pipeline test message")

    # Run the pipeline
    response = pipeline.run(test_data)

    # Get calls from Weave client
    calls = list(client.get_calls(filter=tsi.CallsFilter(trace_roots_only=True)))
    assert len(calls) > 0

    flattened = flatten_calls(calls)
    assert_ends_and_errors(flattened)

    # Check for complex structure traces
    got = [(op_name_from_ref(c.op_name), d) for (c, d) in flattened]

    pipeline_calls = [call for call in got if "ComplexPipeline" in call[0]]
    judge_calls = [call for call in got if "Judge" in call[0]]
    meanpool_calls = [call for call in got if "MeanPool" in call[0]]

    assert len(pipeline_calls) >= 1
    assert len(judge_calls) >= 2  # Multiple judges in layer
    assert len(meanpool_calls) >= 1  # Aggregator


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
    before_record_request=filter_body,
)
def test_verdict_error_handling_tracing(client: WeaveClient) -> None:
    """Test that errors in Verdict units are properly traced."""
    try:
        from verdict import Pipeline, Unit
        from verdict.prompt import Prompt
        from verdict.schema import Schema
    except ImportError:
        pytest.skip("verdict not available")

    # Define a unit that will raise an error
    class ErrorUnit(Unit):
        _char = "ErrorTest"

        class ResponseSchema(Schema):
            result: str

        _prompt = Prompt.from_template("Test prompt: {source.input}")

        def process(self, input_data, response):
            # Intentionally raise an error to test error tracing
            raise ValueError("Test error for tracing")

    pipeline = Pipeline(name="ErrorTestPipeline")
    pipeline = pipeline >> ErrorUnit()

    test_data = Schema.of(input="error test")

    # Run the pipeline - expect it to fail gracefully
    try:
        response = pipeline.run(test_data, graceful=True)
    except Exception:
        pass  # Expected to fail

    # Get calls from Weave client
    calls = list(client.get_calls(filter=tsi.CallsFilter(trace_roots_only=True)))

    # Even with errors, we should have trace calls
    assert len(calls) > 0

    flattened = flatten_calls(calls)

    # Check that we have calls, some might have exceptions
    got = [(op_name_from_ref(c.op_name), d) for (c, d) in flattened]
    pipeline_calls = [call for call in got if "ErrorTestPipeline" in call[0]]

    assert len(pipeline_calls) >= 1  # Should still have pipeline call


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
    before_record_request=filter_body,
)
def test_verdict_tracer_inheritance(client: WeaveClient) -> None:
    """Test that tracer context is properly inherited through pipeline execution."""
    try:
        from verdict import Pipeline
        from verdict.common.judge import JudgeUnit
        from verdict.schema import Schema
    except ImportError:
        pytest.skip("verdict not available")

    # Create pipeline with multiple tracers (including console tracer)
    pipeline = Pipeline(name="TracerInheritancePipeline")
    pipeline = pipeline >> JudgeUnit().prompt("Rate this: {source.text}")

    # Create test data
    test_data = Schema.of(text="Tracer inheritance test")

    # Run the pipeline
    response = pipeline.run(test_data)

    # Get calls from Weave client
    calls = list(client.get_calls(filter=tsi.CallsFilter(trace_roots_only=True)))
    assert len(calls) > 0

    flattened = flatten_calls(calls)
    assert_ends_and_errors(flattened)

    # Verify trace context inheritance
    got = [(op_name_from_ref(c.op_name), d) for (c, d) in flattened]

    # Should have hierarchical structure with proper parent-child relationships
    pipeline_calls = [call for call in got if "TracerInheritancePipeline" in call[0]]
    judge_calls = [call for call in got if "Judge" in call[0]]

    assert len(pipeline_calls) >= 1
    assert len(judge_calls) >= 1

    # Judge calls should have greater depth than pipeline calls (child relationship)
    pipeline_depth = min(d for name, d in got if "TracerInheritancePipeline" in name)
    judge_depth = min(d for name, d in got if "Judge" in name)
    assert judge_depth > pipeline_depth
