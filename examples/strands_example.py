"""
Example demonstrating Weave integration with Strands Agents.

This example shows how to use Weave to trace Strands Agent execution
for observability and debugging.
"""

import weave

# Initialize Weave for tracing
weave.init("strands-example")

try:
    from strands import Agent
    
    # Create a Strands agent
    agent = Agent()
    
    # The agent calls will be automatically traced by Weave
    response1 = agent("What is artificial intelligence?")
    print(f"Response 1: {response1}")
    
    response2 = agent("How do neural networks work?")
    print(f"Response 2: {response2}")
    
    # You can also use other agent methods if they exist
    if hasattr(agent, 'run'):
        response3 = agent.run("Explain machine learning")
        print(f"Response 3: {response3}")
    
    print("\nCheck your Weave dashboard to see the traced agent calls!")
    
except ImportError:
    print("Strands agents library not installed. Install with: pip install strands-agents")
    print("This is just an example - the integration will work when Strands is available.")