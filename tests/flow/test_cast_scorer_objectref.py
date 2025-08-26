"""Test that ObjectRef instances can be properly cast to Scorer objects.

This test ensures that the fix for https://github.com/wandb/weave/issues/XXXX
works correctly. The issue was that when an Evaluation containing a class-based
scorer was saved and retrieved, the casting would fail with "Unable to cast to Scorer"
because ObjectRef was not handled in cast_to_scorer.
"""

import weave
from weave.dataset.dataset import Dataset
from weave.evaluation.eval import Evaluation
from weave.flow.casting import cast_to_scorer
from weave.flow.scorer import Scorer


class CustomScorer(Scorer):
    """A simple custom scorer for testing."""
    
    @weave.op
    def score(self, *, output: str, **kwargs) -> dict:
        return {"length": len(output)}


def test_cast_scorer_from_objectref(client):
    """Test that ObjectRef can be cast to Scorer."""
    # Create a custom scorer instance
    scorer = CustomScorer()
    
    # Publish the scorer to get an ObjectRef
    published_ref = weave.publish(scorer, name="test-scorer-objectref")
    
    # The published_ref is an ObjectRef - test that cast_to_scorer handles it
    casted_scorer = cast_to_scorer(published_ref)
    
    # Verify the casted scorer is a Scorer instance
    assert isinstance(casted_scorer, Scorer)
    
    # Verify it can score properly
    result = casted_scorer.score(output="test")
    assert result == {"length": 4}


def test_evaluation_with_class_scorer_roundtrip(client):
    """Test that an Evaluation with a class-based scorer can be saved and retrieved."""
    # Create a custom scorer instance
    scorer = CustomScorer()
    
    # Create a dataset
    dataset = Dataset(rows=[
        {"input": "hello"},
        {"input": "world"}
    ])
    
    # Create an evaluation with the class-based scorer
    evaluation = Evaluation(
        dataset=dataset,
        scorers=[scorer],
        name="test-class-scorer-eval"
    )
    
    # Publish the evaluation
    published_ref = weave.publish(evaluation, name="test-eval-class-scorer")
    
    # Retrieve the evaluation - this should not raise TypeError
    retrieved_eval = weave.get(published_ref.uri())
    
    # Verify the retrieved evaluation is correct
    assert isinstance(retrieved_eval, Evaluation)
    assert len(retrieved_eval.scorers) == 1
    assert isinstance(retrieved_eval.scorers[0], Scorer)
    
    # Verify the scorer still works
    test_result = retrieved_eval.scorers[0].score(output="testing")
    assert test_result == {"length": 7}


def test_evaluation_with_function_scorer_roundtrip(client):
    """Test that an Evaluation with a function-based scorer can be saved and retrieved."""
    # Create a function-based scorer
    @weave.op
    def function_scorer(*, output: str, **kwargs) -> dict:
        return {"length": len(output)}
    
    # Create a dataset
    dataset = Dataset(rows=[
        {"input": "hello"},
        {"input": "world"}
    ])
    
    # Create an evaluation with the function-based scorer
    evaluation = Evaluation(
        dataset=dataset,
        scorers=[function_scorer],
        name="test-function-scorer-eval"
    )
    
    # Publish the evaluation
    published_ref = weave.publish(evaluation, name="test-eval-function-scorer")
    
    # Retrieve the evaluation - this should work (and already did before the fix)
    retrieved_eval = weave.get(published_ref.uri())
    
    # Verify the retrieved evaluation is correct
    assert isinstance(retrieved_eval, Evaluation)
    assert len(retrieved_eval.scorers) == 1
    assert callable(retrieved_eval.scorers[0])
    
    # Verify the scorer still works
    test_result = retrieved_eval.scorers[0](output="testing")
    assert test_result == {"length": 7}


def test_cast_scorer_preserves_weaveobject_scorers(client):
    """Test that cast_to_scorer properly handles WeaveObject scorers."""
    # Create a custom scorer
    scorer = CustomScorer()
    
    # Publish and retrieve to get a WeaveObject
    published_ref = weave.publish(scorer, name="test-weaveobject-scorer")
    weave_obj_scorer = published_ref.get()
    
    # Cast the WeaveObject - should use Scorer.from_obj
    casted = cast_to_scorer(weave_obj_scorer)
    
    # Verify it's a proper Scorer instance
    assert isinstance(casted, Scorer)
    
    # Verify functionality is preserved
    result = casted.score(output="hello")
    assert result == {"length": 5}