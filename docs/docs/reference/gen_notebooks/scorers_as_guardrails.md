---
title: Scorers as Guardrails
---


:::tip[This is a notebook]

<a href="https://colab.research.google.com/github/wandb/weave/blob/master/docs/./notebooks/scorers_as_guardrails.ipynb" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/archive/d/d0/20221103151430%21Google_Colaboratory_SVG_Logo.svg" alt="Open In Colab" height="20px" /><div>Open in Colab</div></div></a>

<a href="https://github.com/wandb/weave/blob/master/docs/./notebooks/scorers_as_guardrails.ipynb" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/9/91/Octicons-mark-github.svg" alt="View in Github" height="15px" /><div>View in Github</div></div></a>

:::



<!--- @wandbcode{prompt-optim-notebook} -->

# Scorers as Guardrails

Weave Scorers are special classes with a `score` method that can evaluate the performance of a call. They can range from quite simple rules to complex LLMs as judges. 

In this notebook, we will explore how to use Scorers as guardrails to prevent your LLM from generating harmful or inappropriate content.



```python
%pip install weave --quiet
```


```python
"""
Example demonstrating how to implement guardrails in Weave.
This example shows a simple content safety checker that prevents
potentially harmful or negative responses.
"""

import weave

# Initialize Weave with a descriptive project name
weave.init("content-safety-guardrails")


class ContentSafetyScorer(weave.Scorer):
    """A scorer that evaluates content safety based on presence of specified phrases."""

    unsafe_phrases: list[str]
    case_sensitive: bool = False

    @weave.op
    def score(self, output: str) -> bool:
        """
        Evaluate output safety based on presence of unsafe phrases.

        Args:
            output: The text output to evaluate

        Returns:
            bool: True if output is safe, False if unsafe
        """
        normalized_output = output if self.case_sensitive else output.lower()

        for phrase in self.unsafe_phrases:
            normalized_phrase = phrase if self.case_sensitive else phrase.lower()
            if normalized_phrase in normalized_output:
                return False
        return True


@weave.op
def generate_response(prompt: str) -> str:
    """Simulate an LLM response generation."""
    if "test" in prompt.lower():
        return "I'm sorry, I cannot process that request."
    elif "help" in prompt.lower():
        return "I'd be happy to help you with that!"
    else:
        return "Here's what you requested: " + prompt


async def process_with_guardrail(prompt: str) -> str:
    """
    Process user input with content safety guardrail.
    Returns the response if safe, or a fallback message if unsafe.
    """
    # Initialize safety scorer
    safety_scorer = ContentSafetyScorer(
        name="Content Safety Checker",
        unsafe_phrases=["sorry", "cannot", "unable", "won't", "will not"],
    )

    # Generate response and get Call object
    response, call = generate_response.call(prompt)

    # Apply safety scoring
    evaluation = await call.apply_scorer(safety_scorer)

    # Return response or fallback based on safety check
    if evaluation.result:
        return response
    else:
        return "I cannot provide that response."
```


```python
"""Example usage of the guardrail system."""
test_prompts = [
    "Please help me with my homework",
    "Can you run a test for me?",
    "Tell me a joke",
]

print("Testing content safety guardrails:\n")

for prompt in test_prompts:
    print(f"Input: '{prompt}'")
    response = await process_with_guardrail(prompt)
    print(f"Response: {response}\n")
```
