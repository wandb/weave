import weave
from weave.flow.scorer import prepare_scorer_op_args


class TestPreparerScorerOpArgs:
    """Test the prepare_scorer_op_args function behavior."""

    def test_skips_kwargs_parameter(self):
        """
        Test that prepare_scorer_op_args correctly skips the 'kwargs' parameter
        when building score arguments, just like it skips 'output' and 'model_output'.

        This tests the specific change that adds "kwargs" to the list of
        parameters to skip: if arg in ("output", "model_output", "kwargs")
        """

        @weave.op
        def scorer_with_kwargs(input_text: str, target: str, output: str, **kwargs):
            """A scorer function that accepts kwargs."""
            return len(input_text) - len(target)

        # Test data
        example = {
            "input_text": "Hello world",
            "target": "Hello",
            "kwargs": {"some": "value"},  # This should be skipped
            "extra_field": "ignored",  # This should also not appear
        }
        model_output = "some output"

        # Call the function
        score_op, score_args = prepare_scorer_op_args(
            scorer_with_kwargs, example, model_output
        )

        # Verify that kwargs is not in the score_args
        assert "kwargs" not in score_args

        # Verify that the expected arguments are included
        assert "input_text" in score_args
        assert "target" in score_args
        assert score_args["input_text"] == "Hello world"
        assert score_args["target"] == "Hello"

        # Verify that extra_field is not included (not in scorer signature)
        assert "extra_field" not in score_args

        # Verify the op is correct
        assert score_op == scorer_with_kwargs

    def test_skips_output_and_model_output_parameters(self):
        """
        Test that prepare_scorer_op_args continues to correctly skip
        'output' and 'model_output' parameters as before.
        """

        @weave.op
        def scorer_with_output_params(input_text: str, output: str, model_output: str):
            """A scorer function that has output and model_output parameters."""
            return len(input_text)

        example = {
            "input_text": "Hello world",
            "output": "should be skipped",
            "model_output": "should also be skipped",
        }
        model_output = "actual model output"

        _, score_args = prepare_scorer_op_args(
            scorer_with_output_params, example, model_output
        )

        # Verify that output and model_output are not in score_args
        assert "output" not in score_args
        assert "model_output" not in score_args

        # Verify that input_text is included
        assert "input_text" in score_args
        assert score_args["input_text"] == "Hello world"

    def test_all_skipped_parameters_together(self):
        """
        Test that all three parameters (output, model_output, kwargs)
        are correctly skipped when they appear together.
        """

        @weave.op
        def comprehensive_scorer(
            input_text: str, target: str, output: str, model_output: str, **kwargs
        ):
            """A scorer with all the parameters that should be skipped."""
            return 0.5

        example = {
            "input_text": "test input",
            "target": "test target",
            "output": "skip this",
            "model_output": "skip this too",
            "kwargs": {"skip": "this as well"},
        }
        model_output = "actual output"

        _, score_args = prepare_scorer_op_args(
            comprehensive_scorer, example, model_output
        )

        # Verify all skipped parameters are absent
        assert "output" not in score_args
        assert "model_output" not in score_args
        assert "kwargs" not in score_args

        # Verify expected parameters are present
        assert "input_text" in score_args
        assert "target" in score_args
        assert score_args["input_text"] == "test input"
        assert score_args["target"] == "test target"
