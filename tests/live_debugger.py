"""
Weave Wizard - A Hackweek Demo for the Debugger Feature

This example showcases a multi-op, multi-step LLM application that can:
1. Answer questions about Weave
2. Generate Weave code examples
3. Review and "roast" code (humorously)
4. Create a full tutorial on any topic

Run with: python tests/live_debugger.py
Then open the debugger UI to interact with these ops!
"""

import weave
from openai import OpenAI
from pydantic import BaseModel, Field
from typing import Literal

# Initialize OpenAI client
client = OpenAI()

# System prompts for our different "experts"
WEAVE_EXPERT_SYSTEM = """You are the Weave Wizard 🧙‍♂️, an expert on Weights & Biases Weave.
Weave is a toolkit for developing and monitoring AI applications. Key features:
- @weave.op decorator for tracing function calls
- weave.init() to start tracing to a project
- Automatic logging of inputs, outputs, and timing
- Integration with OpenAI, Anthropic, and other LLM providers
- Dataset and Evaluation tools for testing

Be helpful, concise, and sprinkle in some wizard-themed humor! ✨"""

CODE_GENERATOR_SYSTEM = """You are a code generation wizard specializing in Weave.
Generate clean, well-documented Python code that uses Weave best practices.
Always include:
- Proper type hints
- The @weave.op decorator on functions that should be traced
- weave.init() call when appropriate
- Helpful comments

Keep examples practical and runnable."""

CODE_ROASTER_SYSTEM = """You are the Code Roast Master 🔥, a comedic code reviewer.
Your job is to humorously critique code while actually providing useful feedback.
Be funny but not mean - think "friendly roast" not "brutal takedown".
Point out real issues but wrap them in humor.
End with a genuine compliment or encouragement.
Use emojis liberally! 🎭"""

TUTORIAL_PLANNER_SYSTEM = """You are a technical curriculum designer.
Given a topic, create a structured learning plan with 3-5 steps.
Each step should build on the previous one.
Return a JSON-like structure with steps, each having a title and description.
Focus on practical, hands-on learning."""

INTENT_CLASSIFIER_SYSTEM = """You are an intent classifier for the Weave Wizard assistant.
Analyze the user's message and determine which capability they need.

Available modes:
- "expert": Questions about Weave, how things work, conceptual questions, troubleshooting
- "code": Requests to generate, write, or create code
- "roast": Requests to review, critique, or roast code (user will provide code)
- "tutorial": Requests for tutorials, learning paths, or comprehensive guides on topics

Respond with ONLY the mode name, nothing else. Just one word: expert, code, roast, or tutorial."""


@weave.op()
def ask_weave_expert(question: str) -> str:
    """Ask the Weave Wizard a question about Weave.
    
    Args:
        question: Your question about Weave, tracing, or ML observability.
        
    Returns:
        The Wizard's helpful (and slightly magical) response.
    """
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": WEAVE_EXPERT_SYSTEM},
            {"role": "user", "content": question}
        ],
        temperature=0.7,
        max_tokens=500
    )
    return response.choices[0].message.content


@weave.op()
def generate_weave_code(task_description: str) -> str:
    """Generate Weave code for a specific task.
    
    Args:
        task_description: What you want the code to do (e.g., "trace an OpenAI chat call")
        
    Returns:
        Generated Python code using Weave.
    """
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": CODE_GENERATOR_SYSTEM},
            {"role": "user", "content": f"Generate Weave code for: {task_description}"}
        ],
        temperature=0.3,
        max_tokens=800
    )
    return response.choices[0].message.content


@weave.op()
def roast_my_code(code: str) -> str:
    """Get a humorous code review from the Roast Master.
    
    Args:
        code: The Python code you want roasted (and actually reviewed).
        
    Returns:
        A funny but useful code review.
    """
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": CODE_ROASTER_SYSTEM},
            {"role": "user", "content": f"Please roast this code:\n\n```python\n{code}\n```"}
        ],
        temperature=0.9,
        max_tokens=600
    )
    return response.choices[0].message.content


@weave.op()
def plan_tutorial(topic: str) -> str:
    """Create a structured learning plan for a topic.
    
    Args:
        topic: The topic to create a tutorial plan for.
        
    Returns:
        A structured learning plan with steps.
    """
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": TUTORIAL_PLANNER_SYSTEM},
            {"role": "user", "content": f"Create a tutorial plan for: {topic}"}
        ],
        temperature=0.5,
        max_tokens=500
    )
    return response.choices[0].message.content


@weave.op()
def generate_tutorial_step(topic: str, step_number: int, step_title: str) -> str:
    """Generate detailed content for a single tutorial step.
    
    Args:
        topic: The overall tutorial topic.
        step_number: Which step this is (1-indexed).
        step_title: The title of this step.
        
    Returns:
        Detailed tutorial content with code examples.
    """
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": CODE_GENERATOR_SYSTEM},
            {"role": "user", "content": f"""Create detailed tutorial content for:
Topic: {topic}
Step {step_number}: {step_title}

Include:
- Explanation of concepts
- Code examples using Weave
- Tips and best practices"""}
        ],
        temperature=0.4,
        max_tokens=800
    )
    return response.choices[0].message.content


@weave.op()
def create_full_tutorial(topic: str) -> dict:
    """Create a complete tutorial on a topic (multi-step pipeline).
    
    This demonstrates a multi-op workflow:
    1. First plans the tutorial structure
    2. Then generates content for each step
    
    Args:
        topic: What to create a tutorial about.
        
    Returns:
        A dictionary with the plan and all generated steps.
    """
    # Step 1: Plan the tutorial
    plan = plan_tutorial(topic)
    
    # Step 2: Generate a sample first step (to keep it quick for demo)
    first_step_content = generate_tutorial_step(
        topic=topic,
        step_number=1,
        step_title="Getting Started"
    )
    
    return {
        "topic": topic,
        "plan": plan,
        "step_1_content": first_step_content,
        "note": "Full tutorial would generate all steps - truncated for demo speed!"
    }


@weave.op()
def classify_intent(message: str) -> str:
    """Classify the user's intent to route to the right capability.
    
    Args:
        message: The user's message to classify.
        
    Returns:
        One of: "expert", "code", "roast", or "tutorial"
    """
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": INTENT_CLASSIFIER_SYSTEM},
            {"role": "user", "content": message}
        ],
        temperature=0.0,  # Deterministic for classification
        max_tokens=10
    )
    mode = response.choices[0].message.content.strip().lower()
    
    # Validate the mode
    valid_modes = {"expert", "code", "roast", "tutorial"}
    if mode not in valid_modes:
        return "expert"  # Default fallback
    return mode


@weave.op()
def weave_wizard_chat(message: str) -> dict:
    """The main Weave Wizard interface - automatically routes to the right capability.
    
    This is a multi-step pipeline that:
    1. Classifies your intent using an LLM
    2. Routes to the appropriate specialist (expert, code gen, roast, or tutorial)
    
    Args:
        message: Your message or question - just ask naturally!
        
    Returns:
        A dict with the detected intent and the response.
        
    Examples:
        - "How do I trace async functions?" → expert mode
        - "Write me a RAG pipeline with Weave" → code mode  
        - "Roast this: def f(x): return x" → roast mode
        - "Create a tutorial on LLM observability" → tutorial mode
    """
    # Step 1: Classify the intent
    mode = classify_intent(message)
    
    # Step 2: Route to the appropriate handler
    if mode == "expert":
        response = ask_weave_expert(message)
    elif mode == "code":
        response = generate_weave_code(message)
    elif mode == "roast":
        response = roast_my_code(message)
    elif mode == "tutorial":
        response = create_full_tutorial(message)
    else:
        response = ask_weave_expert(message)  # Fallback
    
    return {
        "detected_intent": mode,
        "response": response
    }


# Simple helper ops for basic demo
@weave.op()
def adder(a: float, b: float) -> float:
    """Add two numbers (simple demo op)."""
    return a + b


@weave.op()
def multiplier(a: float, b: float) -> float:
    """Multiply two numbers (simple demo op)."""
    return a * b

@weave.op()
def line(m: float, b: float, x: float) -> float:
    """Multiply two numbers (simple demo op)."""
    return adder(multiplier(m, x), b)


@weave.op()
def matrix_multiplier(m: list[list[float]], x: list[float]) -> list[float]:
    """Multiply two matrices."""
    return [sum(m[i][j] * x[j] for j in range(len(x))) for i in range(len(m))]

class StoryConfig(BaseModel):
    n: int = Field(..., ge=1, le=10, description="The number of stories to generate")
    story_type: Literal["short", "medium", "long"] = Field(..., description="The type of story to generate")

@weave.op()
def tell_me_n_stories(config: StoryConfig) -> list[str]:
    return [f"Story {i}" for i in range(config.n)]


if __name__ == "__main__":
    print("🧙‍♂️ Starting the Weave Wizard Debugger...")
    print("=" * 60)
    print("Available ops:")
    print()
    print("  🌟 MAIN INTERFACE (auto-routes based on your message):")
    print("     weave_wizard_chat - Just ask anything naturally!")
    print()
    print("  🎯 SPECIALIST OPS (use directly if you prefer):")
    print("     ask_weave_expert   - Questions about Weave")
    print("     generate_weave_code - Generate code examples")
    print("     roast_my_code      - Humorous code review 🔥")
    print("     plan_tutorial      - Create a learning plan")
    print("     create_full_tutorial - Multi-step tutorial gen")
    print()
    print("  🔧 INTERNAL OPS (used by pipelines):")
    print("     classify_intent    - LLM-powered intent detection")
    print("     generate_tutorial_step - Single tutorial step")
    print()
    print("  ➕ SIMPLE TEST OPS:")
    print("     adder, multiplier  - Basic math for testing")
    print("=" * 60)
    
    weave.init("weave-wizard-hackweek-2")
    
    debugger = weave.Debugger()
    
    # Main chat interface (recommended!)
    debugger.add_callable(weave_wizard_chat)
    
    # Specialist ops
    debugger.add_callable(ask_weave_expert)
    debugger.add_callable(generate_weave_code)
    debugger.add_callable(roast_my_code)
    debugger.add_callable(plan_tutorial)
    debugger.add_callable(create_full_tutorial)
    
    # Internal/helper ops
    debugger.add_callable(classify_intent)
    debugger.add_callable(generate_tutorial_step)
    
    # Simple math ops for basic testing
    debugger.add_callable(adder)
    debugger.add_callable(multiplier)
    debugger.add_callable(matrix_multiplier)
    debugger.add_callable(line)


    debugger.add_callable(tell_me_n_stories)
    
    print("\n✨ Debugger starting on http://0.0.0.0:8000")
    print("\nTry weave_wizard_chat with messages like:")
    print('  • "How do I trace async functions in Weave?"')
    print('  • "Write a RAG pipeline with Weave tracing"')
    print('  • "Roast this code: def f(x): return x+1"')
    print('  • "Create a tutorial on building LLM apps"')
    print()
    
    debugger.start()
