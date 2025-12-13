"""Tests for EvaluationLoggerV2."""

import weave


def test_evaluation_logger_v2_basic(client):
    """Test basic EvaluationLoggerV2 functionality."""
    # Create a simple dataset
    dataset = weave.Dataset(
        name="test_dataset",
        rows=[
            {"question": "What is 2+2?", "expected": "4"},
            {"question": "What is 3+3?", "expected": "6"},
        ],
    )

    # Create a simple model
    model = weave.Model(name="test_model")

    # Create evaluation logger
    ev = weave.EvaluationLoggerV2(
        name="test_evaluation",
        dataset=dataset,
        model=model,
        description="A test evaluation",
    )

    # Log some predictions
    pred1 = ev.log_prediction(inputs={"question": "What is 2+2?"}, output="4")
    pred1.log_score("correctness", 1.0)
    pred1.finish()

    pred2 = ev.log_prediction(inputs={"question": "What is 3+3?"}, output="6")
    pred2.log_score("correctness", 1.0)
    pred2.finish()

    # Finish the evaluation
    ev.log_summary({"average_correctness": 1.0})

    # Verify calls were created
    calls = client.get_calls()
    assert len(calls) > 0

    # Find the evaluation run call
    eval_run_call = None
    for call in calls:
        if call.id == ev._eval_run_id:
            eval_run_call = call
            break

    assert eval_run_call is not None
    assert eval_run_call.ended_at is not None


def test_evaluation_logger_v2_with_scorer_objects(client):
    """Test EvaluationLoggerV2 with Scorer objects."""
    # Create a dataset
    dataset = weave.Dataset(
        name="test_dataset_scorers",
        rows=[{"input": "test"}],
    )

    # Create a scorer (just a simple named scorer for metadata)
    scorer = weave.Scorer(name="accuracy")

    # Create evaluation logger with scorers
    ev = weave.EvaluationLoggerV2(
        name="test_evaluation_with_scorers",
        dataset=dataset,
        model="test_model",
        scorers=[scorer],
    )

    # Log a prediction
    pred = ev.log_prediction(
        inputs={"input": "test", "expected": "test"}, output="test"
    )
    pred.log_score("accuracy", 1.0)
    pred.finish()

    # Finish evaluation
    ev.log_summary()

    # Verify the evaluation was created
    assert ev._evaluation_ref is not None
    assert ev._eval_run_id is not None


def test_evaluation_logger_v2_auto_summarize(client):
    """Test EvaluationLoggerV2 with auto-summarization."""
    dataset = weave.Dataset(
        name="test_auto_summarize",
        rows=[{"q": "test"}],
    )

    ev = weave.EvaluationLoggerV2(
        name="test_auto_summarize",
        dataset=dataset,
        model="test_model",
    )

    # Log predictions with scores
    for i in range(5):
        pred = ev.log_prediction(inputs={"q": f"question_{i}"}, output=f"answer_{i}")
        pred.log_score("accuracy", 0.8 + i * 0.05)
        pred.finish()

    # Finish with auto-summarization
    ev.log_summary(auto_summarize=True)

    # Verify the evaluation run was finalized
    assert ev._is_finalized


def test_evaluation_logger_v2_string_refs(client):
    """Test EvaluationLoggerV2 with string references."""
    # Use string references instead of objects
    ev = weave.EvaluationLoggerV2(
        name="test_string_refs",
        dataset="my-dataset",
        model="my-model",
    )

    # Log a prediction
    pred = ev.log_prediction(inputs={"test": "input"}, output="result")
    pred.log_score("score", 0.9)
    pred.finish()

    # Finish
    ev.log_summary()

    assert ev._is_finalized
    assert ev._evaluation_ref is not None


def test_evaluation_logger_v2_ui_url(client):
    """Test that EvaluationLoggerV2 generates a UI URL."""
    dataset = weave.Dataset(name="test_ui_url", rows=[{"x": 1}])

    ev = weave.EvaluationLoggerV2(
        name="test_ui_url_eval",
        dataset=dataset,
        model="test_model",
    )

    # UI URL should be available after initialization
    ui_url = ev.ui_url
    assert ui_url is not None
    assert "weave/calls" in ui_url
    assert ev._eval_run_id in ui_url


def test_evaluation_logger_v2_finish_without_summary(client):
    """Test that finish() works without calling log_summary()."""
    dataset = weave.Dataset(name="test_finish", rows=[{"x": 1}])

    ev = weave.EvaluationLoggerV2(
        name="test_finish_eval",
        dataset=dataset,
        model="test_model",
    )

    # Log a prediction
    pred = ev.log_prediction(inputs={"x": 1}, output=2)
    pred.finish()

    # Call finish directly without log_summary
    ev.finish()

    assert ev._is_finalized


def test_evaluation_logger_v2_multiple_scores_per_prediction(client):
    """Test logging multiple scores for a single prediction."""
    dataset = weave.Dataset(name="test_multi_scores", rows=[{"x": 1}])

    ev = weave.EvaluationLoggerV2(
        name="test_multi_scores_eval",
        dataset=dataset,
        model="test_model",
    )

    # Log a prediction with multiple scores
    pred = ev.log_prediction(inputs={"x": 1}, output=2)
    pred.log_score("accuracy", 0.9)
    pred.log_score("precision", 0.85)
    pred.log_score("recall", 0.95)
    pred.finish()

    # Verify scores were captured
    assert len(pred._captured_scores) == 3
    assert pred._captured_scores["accuracy"] == 0.9
    assert pred._captured_scores["precision"] == 0.85
    assert pred._captured_scores["recall"] == 0.95

    ev.log_summary()
