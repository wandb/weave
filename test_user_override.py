#!/usr/bin/env python
"""
Test script to verify the username override functionality.

This script demonstrates how to use the WEAVE_USER_ID environment variable
to override the username associated with an API key.

Usage:
    # Set the environment variable before running
    export WEAVE_USER_ID="custom_user_123"
    python test_user_override.py

For OTEL traces, pass the wb_user_id attribute:
    Set attribute "wandb.wb_user_id" to override the username in OTEL spans
"""

import os
import weave

# Test with environment variable override
def test_env_override():
    """Test that WEAVE_USER_ID environment variable overrides the API key user."""
    
    # Set the environment variable (normally this would be set before running)
    os.environ["WEAVE_USER_ID"] = "test_override_user"
    
    # Initialize Weave (replace with your project name)
    # weave.init("my-project")
    
    @weave.op
    def sample_operation(x: int, y: int) -> int:
        """A simple operation to test tracing."""
        return x + y
    
    # This call should be traced with the overridden user ID
    result = sample_operation(3, 4)
    print(f"Result: {result}")
    print(f"Check the Weave UI - the call should be associated with user: {os.environ['WEAVE_USER_ID']}")
    

def test_otel_override():
    """
    Example showing how OTEL traces can override username.
    
    When sending OTEL traces, include the attribute:
    "wandb.wb_user_id": "custom_user_id"
    
    This will override the wb_user_id passed in the OTEL export request.
    """
    print("\nFor OTEL traces, set the 'wandb.wb_user_id' attribute in your span")
    print("Example in OpenTelemetry Python:")
    print("""
    from opentelemetry import trace
    
    tracer = trace.get_tracer(__name__)
    
    with tracer.start_as_current_span(
        "my_operation",
        attributes={
            "wandb.wb_user_id": "custom_user_for_this_trace"
        }
    ) as span:
        # Your code here
        pass
    """)


if __name__ == "__main__":
    print("=" * 60)
    print("Weave User ID Override Test")
    print("=" * 60)
    
    # Test environment variable override
    print("\n1. Testing environment variable override:")
    print("-" * 40)
    test_env_override()
    
    # Show OTEL example
    print("\n2. OTEL trace override example:")
    print("-" * 40)
    test_otel_override()
    
    print("\n" + "=" * 60)
    print("Test complete. Check the Weave UI to verify the username.")
    print("=" * 60)