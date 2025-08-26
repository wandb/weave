import asyncio
import weave
from weave.dataset.dataset import Dataset
from weave.evaluation.eval import Evaluation
from weave.trace.ref_util import get_ref

# Initialize Weave
weave.init(project_name="test-scorer-issue")

# Define a function-based scorer
@weave.op
def example_scorer(*, output: str, **kwargs) -> dict:
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
    # Run evaluation with function-based scorer
    evaluation = Evaluation(
        dataset=dataset,
        scorers=[example_scorer],
        name="test-function-scorer"
    )
    
    # Run the evaluation
    eval_result = await evaluation.evaluate(simple_model)
    
    # Get the URI of the evaluation object
    eval_ref = get_ref(evaluation)
    if eval_ref:
        uri = str(eval_ref)
        print(f"URI: {uri}")
        
        # Try to dereference it
        try:
            retrieved_eval = weave.ref(uri).get()
            print("✅ Successfully retrieved evaluation with function-based scorer")
        except TypeError as e:
            print(f"❌ Failed to retrieve evaluation: {e}")
    else:
        print("No ref found for evaluation")

# Run the async function
asyncio.run(main())