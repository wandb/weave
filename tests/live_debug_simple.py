"""
Weave Wizard - A Hackweek Demo for the Debugger Feature

This example showcases a multi-op, multi-step LLM application that can:
1. Answer questions about Weave
2. Generate Weave code examples
3. Review and "roast" code (humorously)
4. Create a full tutorial on any topic

Run locally:  python tests/live_debugger.py
Deploy to Modal: modal deploy tests/live_debugger.py

The same code works for both - no changes needed!
"""

import weave
from openai import OpenAI
from pydantic import BaseModel, Field
from typing import Literal

from weave.trace.debugger import create_debugger


# =============================================================================
# Hello World Demo: Generate and Critique Pattern
# =============================================================================

CONTENT_WRITER_SYSTEM = """You are a skilled content writer. 
Write clear, engaging, and informative content on the requested topic.
Match the requested word count as closely as possible."""

CONTENT_CRITIC_SYSTEM = """You are a thoughtful editor and critic.
Review the provided content and give constructive feedback including:
- What works well
- Areas for improvement  
- A quality score from 1-10
Keep your critique concise and actionable."""


@weave.op()
def generate_content(topic: str, word_count: int) -> str:
    """Generate content on a topic with a target word count.
    
    Args:
        topic: The subject to write about.
        word_count: Target number of words.
        
    Returns:
        Generated content as a string.
    """
    # Initialize OpenAI client
    client = OpenAI()

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": CONTENT_WRITER_SYSTEM},
            {"role": "user", "content": f"Write about '{topic}' in approximately {word_count} words."}
        ],
        temperature=0.7,
        max_tokens=word_count * 2  # Rough token estimate
    )
    return response.choices[0].message.content


@weave.op()
def critique_content(content: str) -> str:
    """Critique a piece of content and provide feedback.
    
    Args:
        content: The content to review.
        
    Returns:
        Constructive critique with a quality score.
    """
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": CONTENT_CRITIC_SYSTEM},
            {"role": "user", "content": f"Please critique this content:\n\n{content}"}
        ],
        temperature=0.5,
        max_tokens=400
    )
    return response.choices[0].message.content


@weave.op()
def create_and_critique(topic: str, word_count: int) -> dict:
    """Generate content and critique it - a 2-step LLM pipeline demo.
    
    This demonstrates a foundational pattern for LLM applications and agents:
    1. Generate initial content with one LLM call
    2. Critique/evaluate with a second LLM call
    
    This pattern is the basis for self-improving agents, content pipelines,
    and any system that needs to generate-then-evaluate.
    
    Args:
        topic: The subject to write about (e.g., "machine learning basics").
        word_count: Target word count for the generated content.
        
    Returns:
        Dict containing the topic, generated content, and critique.
        
    Examples:
        >>> create_and_critique("why observability matters for AI", 100)
        >>> create_and_critique("introduction to neural networks", 200)
    """
    # Step 1: Generate content
    content = generate_content(topic, word_count)
    
    # Step 2: Critique the generated content
    critique = critique_content(content)
    
    return {
        "content": content,
        "critique": critique
    }


# =============================================================================
# Create deployable debugger - works for both local and Modal!
# =============================================================================


# Create the deployable debugger
# This works for BOTH local and Modal deployment!
debugger, app = create_debugger(
    ops=[create_and_critique],
    weave_project="weave-wizard-hackweek",
    app_name="weave-wizard",
    modal_secrets=["wandb-api-key", "openai-api-key"],  # Modal secrets for deployment
)


# =============================================================================
# Entry point - same code runs locally or deploys to Modal
# =============================================================================

if __name__ == "__main__":
    # This runs locally - Modal deployment uses the `app` variable directly
    debugger.serve()
