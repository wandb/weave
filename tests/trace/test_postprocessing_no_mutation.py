"""Test that postprocessing functions don't mutate user objects."""

import weave
from weave.trace import api


def test_op_postprocess_inputs_no_mutation(client):
    """Test that op.postprocess_inputs doesn't mutate user's original input objects."""
    
    # Track whether the mutating postprocess was called
    postprocess_called = False
    
    def mutating_postprocess_inputs(inputs):
        """A postprocess function that tries to mutate the inputs."""
        nonlocal postprocess_called
        postprocess_called = True
        # This should NOT affect the original user data
        if isinstance(inputs, dict):
            for key in inputs:
                if key == "test_key":
                    inputs[key] = "MUTATED"
        return inputs
    
    @weave.op(postprocess_inputs=mutating_postprocess_inputs)
    def my_function(test_key, other_key):
        return f"test_key={test_key}, other_key={other_key}"
    
    # Original user data
    original_data = {"test_key": "original_value", "other_key": "other_value"}
    
    # Call the function with kwargs unpacking
    result = my_function(**original_data)
    
    # Verify postprocess was called
    assert postprocess_called, "Postprocess function was not called"
    
    # Verify the original data was NOT mutated
    assert original_data["test_key"] == "original_value", f"Original data was mutated! Got: {original_data}"
    assert original_data["other_key"] == "other_value", f"Original data was mutated! Got: {original_data}"


def test_op_postprocess_output_no_mutation(client):
    """Test that op.postprocess_output doesn't mutate user's original output objects."""
    
    # Track whether the mutating postprocess was called
    postprocess_called = False
    
    def mutating_postprocess_output(output):
        """A postprocess function that tries to mutate the output."""
        nonlocal postprocess_called  
        postprocess_called = True
        # This should NOT affect the original output
        if isinstance(output, dict):
            output["mutated"] = True
        return output
    
    @weave.op(postprocess_output=mutating_postprocess_output)
    def my_function():
        output = {"key": "value", "mutated": False}
        return output
    
    # Call the function
    result = my_function()
    
    # Verify postprocess was called
    assert postprocess_called, "Postprocess function was not called"
    
    # The function's return value should be unmutated
    assert result["mutated"] == False, f"Output was mutated! Got: {result}"


def test_global_postprocess_inputs_no_mutation(client):
    """Test that global postprocess_inputs doesn't mutate user objects."""
    
    # Save original globals
    original_postprocess_inputs = api._global_postprocess_inputs
    
    try:
        def global_mutating_inputs(inputs):
            """Global postprocess that tries to mutate inputs."""
            if isinstance(inputs, dict):
                for key in inputs:
                    if key == "data":
                        inputs[key] = "GLOBALLY_MUTATED"
            return inputs
        
        api._global_postprocess_inputs = global_mutating_inputs
        
        @weave.op
        def my_function(data):
            return {"result": data}
        
        # Original user data
        original_input = {"data": "test"}
        
        # Call the function
        result = my_function(**original_input)
        
        # Verify the original input was NOT mutated
        assert original_input["data"] == "test", f"Original input was mutated! Got: {original_input}"
        
    finally:
        # Restore original globals
        api._global_postprocess_inputs = original_postprocess_inputs


def test_global_postprocess_output_no_mutation(client):
    """Test that global postprocess_output doesn't mutate user objects."""
    
    # Save original globals
    original_postprocess_output = api._global_postprocess_output
    
    try:
        def global_mutating_output(output):
            """Global postprocess that tries to mutate output."""  
            if isinstance(output, dict):
                output["global_mutated"] = True
            return output
        
        api._global_postprocess_output = global_mutating_output
        
        @weave.op
        def my_function():
            return {"result": "test"}
        
        # Call the function
        result = my_function()
        
        # The result should be unmutated
        assert "global_mutated" not in result, f"Result was mutated! Got: {result}"
        
    finally:
        # Restore original globals
        api._global_postprocess_output = original_postprocess_output