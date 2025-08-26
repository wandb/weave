"""
Test to confirm the casting issue with ObjectRef in cast_to_scorer
"""
import weave
from weave.flow.scorer import Scorer
from weave.flow.casting import cast_to_scorer
from weave.trace.refs import ObjectRef

# Initialize Weave
weave.init(project_name="test-scorer-issue")

# Define a class-based scorer 
class ClassScorer(Scorer):
    @weave.op
    def score(self, *, output: str, **kwargs) -> dict:
        return {"length": len(output)}

# Create an instance
scorer = ClassScorer()

# Publish it to get an ObjectRef
published_ref = weave.publish(scorer, name="test-scorer-object")
print(f"Published scorer URI: {published_ref.uri()}")

# Get the actual object back
retrieved_scorer = published_ref.get()
print(f"Retrieved scorer type: {type(retrieved_scorer)}")
print(f"Is it a Scorer? {isinstance(retrieved_scorer, Scorer)}")

# Now test what happens when cast_to_scorer gets an ObjectRef
print("\nTesting cast_to_scorer with different inputs:")

# Test 1: Direct scorer instance - this should work
try:
    result = cast_to_scorer(scorer)
    print(f"✅ cast_to_scorer(scorer instance): {type(result)}")
except Exception as e:
    print(f"❌ cast_to_scorer(scorer instance) failed: {e}")

# Test 2: Retrieved scorer (which might be base Scorer class) - this should work
try:
    result = cast_to_scorer(retrieved_scorer)
    print(f"✅ cast_to_scorer(retrieved scorer): {type(result)}")
except Exception as e:
    print(f"❌ cast_to_scorer(retrieved scorer) failed: {e}")

# Test 3: ObjectRef directly - this is what fails
print("\nThe critical test - passing ObjectRef directly:")
# Simulate what happens during deserialization
# When the evaluation is loaded, scorers come as ObjectRef instances
if hasattr(published_ref, '__class__') and published_ref.__class__.__name__ == 'ObjectRef':
    print(f"Published ref is an ObjectRef: {published_ref}")
    try:
        result = cast_to_scorer(published_ref)
        print(f"✅ cast_to_scorer(ObjectRef): {type(result)}")
    except TypeError as e:
        print(f"❌ cast_to_scorer(ObjectRef) failed: {e}")
        print("This is the bug! ObjectRef is not handled in cast_to_scorer")