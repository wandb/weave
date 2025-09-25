from typing import ClassVar

import weave
from weave.flow.scorer import Scorer, prepare_scorer_op_args


def test_skips_kwargs_parameter_with_column_map():
    """Test that prepare_scorer_op_args correctly skips the 'kwargs' parameter
    when building score arguments with column mapping.

    This tests the specific change that adds "kwargs" to the list of
    parameters to skip: if arg in ("output", "model_output", "kwargs")
    """

    class TestScorer(Scorer):
        column_map: ClassVar[dict] = {"input_text": "question", "target": "answer"}

        @weave.op
        def score(self, *, input_text: str, target: str, output: str, **kwargs):
            """A scorer function that accepts kwargs."""
            return {"score": len(input_text) - len(target)}

    scorer = TestScorer()
    example = {
        "question": "Hello world",  # Maps to input_text
        "answer": "Hello",  # Maps to target
        "kwargs": {"some": "value"},  # Should be skipped
        "extra_field": "ignored",  # Should be skipped
    }
    model_output = "some output"

    _, score_args = prepare_scorer_op_args(scorer, example, model_output)

    # Should be mapped
    assert "input_text" in score_args
    assert "target" in score_args
    assert score_args["input_text"] == "Hello world"  # From the mapped "question"
    assert score_args["target"] == "Hello"  # From the mapped "answer"

    # Should be skipped
    assert "kwargs" not in score_args
    assert "extra_field" not in score_args

    # Verify that output is included (added separately for model output)
    assert "output" in score_args
    assert score_args["output"] == "some output"


def test_skips_output_and_model_output_parameters():
    """Test that prepare_scorer_op_args continues to correctly skip
    'output' and 'model_output' parameters as before.
    """

    @weave.op
    def scorer_with_output_params(input_text: str, output: str, model_output: str):
        """A scorer function that has output and model_output parameters."""
        return {"score": len(input_text)}

    example = {
        "input_text": "Hello world",
        "output": "should be skipped",
        "model_output": "should also be skipped",
    }
    model_output = "actual model output"

    _, score_args = prepare_scorer_op_args(
        scorer_with_output_params, example, model_output
    )

    # Should be mapped
    assert "input_text" in score_args
    assert score_args["input_text"] == "Hello world"

    # Should be skipped
    assert "output" not in score_args
    assert "model_output" not in score_args


def test_all_skipped_parameters_together():
    """Test that all three parameters (output, model_output, kwargs)
    are correctly skipped when they appear together.
    """

    @weave.op
    def comprehensive_scorer(
        input_text: str, target: str, output: str, model_output: str, **kwargs
    ):
        """A scorer with all the parameters that should be skipped."""
        return {"score": 0.5}

    example = {
        "input_text": "test input",
        "target": "test target",
        "output": "skip this",
        "model_output": "skip this too",
        "kwargs": {"skip": "this as well"},
    }
    model_output = "actual output"

    _, score_args = prepare_scorer_op_args(comprehensive_scorer, example, model_output)

    # Should be mapped
    assert "input_text" in score_args
    assert "target" in score_args
    assert score_args["input_text"] == "test input"
    assert score_args["target"] == "test target"

    # Should be skipped
    assert "output" not in score_args
    assert "model_output" not in score_args
    assert "kwargs" not in score_args
