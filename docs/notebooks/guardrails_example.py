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


async def main():
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


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
