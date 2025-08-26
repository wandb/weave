import asyncio
import weave
from weave.flow.scorer import Scorer
from weave.dataset.dataset import Dataset
from weave.evaluation.eval import Evaluation
from weave.trace.objectify import register_object

# Initialize Weave
weave.init(project_name="test-scorer-issue")

# Define a class-based scorer with proper registration
@register_object
class ExampleScorer(Scorer):
    @weave.op
    def score(self, *, output: str, **kwargs) -> dict:
        return {"score": len(output)}

# Create a simple dataset
dataset = Dataset(rows=[
    {"input": "hello", "expected": "world"},
    {"input": "foo", "expected": "bar"}
])

# Create a simple model
@weave.op
def simple_model(input: str) -> str:
    return input.upper()

async def main():
    # Create scorer and evaluation
    scorer = ExampleScorer()
    evaluation = Evaluation(
        dataset=dataset,
        scorers=[scorer],
        name="test-class-scorer"
    )
    
    # Publish the evaluation
    published_eval_ref = weave.publish(evaluation)
    print(f"Published evaluation URI: {published_eval_ref.uri()}")
    
    # Try to retrieve it
    try:
        retrieved_eval = weave.get(published_eval_ref.uri())
        print("✅ Successfully retrieved evaluation with class-based scorer")
        print(f"  Retrieved evaluation type: {type(retrieved_eval)}")
        print(f"  Scorers in retrieved eval: {retrieved_eval.scorers}")
        for i, scorer in enumerate(retrieved_eval.scorers):
            print(f"    Scorer {i}: {type(scorer)}")
    except TypeError as e:
        print(f"❌ Failed to retrieve evaluation: {e}")
        import traceback
        traceback.print_exc()

# Run the async function
asyncio.run(main())