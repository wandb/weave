"""
This script reproduces the issue mentioned in the GitHub issue.
The evaluation runs successfully, but retrieving it via URI fails for class-based scorers.
"""
import asyncio
import weave
from weave.flow.scorer import Scorer
from weave.dataset.dataset import Dataset
from weave.evaluation.eval import Evaluation
from weave.trace.objectify import register_object

# Initialize Weave
weave.init(project_name="test-scorer-issue")

# Define a class-based scorer - NOTE: intentionally NOT using @register_object
# to simulate normal user behavior
class ClassScorer(Scorer):
    @weave.op
    def score(self, *, output: str, **kwargs) -> dict:
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
    print("Testing CLASS-BASED scorer...")
    
    # Create and run evaluation with class-based scorer
    scorer = ClassScorer()
    evaluation = Evaluation(
        dataset=dataset,
        scorers=[scorer],
        name="eval-class-scorer"
    )
    
    # Run the evaluation
    result = await evaluation.evaluate(my_model)
    print(f"Evaluation completed successfully")
    
    # Get the evaluation calls (this is what users typically do after evaluation)
    eval_calls = evaluation.get_evaluate_calls()
    for call in eval_calls:
        print(f"Call ID: {call.id}")
        
        # Try to get the evaluation object from the call inputs
        if 'self' in call.inputs:
            eval_ref_str = call.inputs['self']
            print(f"Evaluation ref from call: {eval_ref_str}")
            
            # This is where the issue occurs - trying to retrieve the evaluation
            try:
                retrieved_eval = weave.ref(eval_ref_str).get()
                print("✅ Successfully retrieved evaluation with class-based scorer")
            except TypeError as e:
                print(f"❌ Failed to retrieve evaluation: {e}")
                import traceback
                traceback.print_exc()
        break

async def test_function_scorer():
    print("\nTesting FUNCTION-BASED scorer...")
    
    # Define a function-based scorer
    @weave.op
    def function_scorer(*, output: str, **kwargs) -> dict:
        return {"length": len(output)}
    
    # Create and run evaluation with function-based scorer
    evaluation = Evaluation(
        dataset=dataset,
        scorers=[function_scorer],
        name="eval-function-scorer"
    )
    
    # Run the evaluation
    result = await evaluation.evaluate(my_model)
    print(f"Evaluation completed successfully")
    
    # Get the evaluation calls
    eval_calls = evaluation.get_evaluate_calls()
    for call in eval_calls:
        print(f"Call ID: {call.id}")
        
        # Try to get the evaluation object from the call inputs
        if 'self' in call.inputs:
            eval_ref_str = call.inputs['self']
            print(f"Evaluation ref from call: {eval_ref_str}")
            
            # This should work without error
            try:
                retrieved_eval = weave.ref(eval_ref_str).get()
                print("✅ Successfully retrieved evaluation with function-based scorer")
            except TypeError as e:
                print(f"❌ Failed to retrieve evaluation: {e}")
                import traceback
                traceback.print_exc()
        break

async def main():
    await test_class_scorer()
    await test_function_scorer()

# Run the tests
asyncio.run(main())