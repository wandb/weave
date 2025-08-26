"""
Direct test of retrieving evaluations from refs
"""
import asyncio
import weave
from weave.flow.scorer import Scorer
from weave.dataset.dataset import Dataset
from weave.evaluation.eval import Evaluation

# Initialize Weave
weave.init(project_name="test-scorer-issue")

# Define a class-based scorer without @register_object
class ClassScorer(Scorer):
    @weave.op
    def score(self, *, output: str, **kwargs) -> dict:
        return {"length": len(output)}

# Define a function-based scorer
@weave.op
def function_scorer(*, output: str, **kwargs) -> dict:
    return {"length": len(output)}

# Create a simple dataset
dataset = Dataset(rows=[
    {"input": "hello"},
    {"input": "world"}
])

# Create a simple model
@weave.op
def my_model(input: str) -> str:
    return input.upper()

async def test_class_scorer():
    print("=" * 60)
    print("Testing CLASS-BASED scorer...")
    print("=" * 60)
    
    # Create evaluation with class-based scorer
    scorer = ClassScorer()
    evaluation = Evaluation(
        dataset=dataset,
        scorers=[scorer],
        name="eval-class-scorer"
    )
    
    # Publish the evaluation before running it
    published_ref = weave.publish(evaluation, name="published-class-eval")
    print(f"Published evaluation URI: {published_ref.uri()}")
    
    # Try to retrieve it immediately after publishing
    try:
        retrieved = weave.ref(published_ref.uri()).get()
        print(f"✅ Retrieved published evaluation successfully")
        print(f"  Type: {type(retrieved)}")
        print(f"  Scorers: {retrieved.scorers}")
        for s in retrieved.scorers:
            print(f"    Scorer type: {type(s)}")
    except Exception as e:
        print(f"❌ Failed to retrieve: {e}")
        import traceback
        traceback.print_exc()

async def test_function_scorer():
    print("\n" + "=" * 60)
    print("Testing FUNCTION-BASED scorer...")
    print("=" * 60)
    
    # Create evaluation with function-based scorer
    evaluation = Evaluation(
        dataset=dataset,
        scorers=[function_scorer],
        name="eval-function-scorer"
    )
    
    # Publish the evaluation before running it
    published_ref = weave.publish(evaluation, name="published-func-eval")
    print(f"Published evaluation URI: {published_ref.uri()}")
    
    # Try to retrieve it immediately after publishing
    try:
        retrieved = weave.ref(published_ref.uri()).get()
        print(f"✅ Retrieved published evaluation successfully")
        print(f"  Type: {type(retrieved)}")
        print(f"  Scorers: {retrieved.scorers}")
        for s in retrieved.scorers:
            print(f"    Scorer type: {type(s)}")
    except Exception as e:
        print(f"❌ Failed to retrieve: {e}")
        import traceback
        traceback.print_exc()

async def main():
    await test_class_scorer()
    await test_function_scorer()

# Run the tests
asyncio.run(main())