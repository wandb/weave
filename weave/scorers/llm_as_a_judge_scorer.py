from typing import Any, Optional

from weave.flow.scorer import Scorer
from weave.trace.context.weave_client_context import get_weave_client
from weave.trace.objectify import register_object
from weave.trace.op import op
from weave.trace_server.interface.builtin_object_classes import base_object_def
from weave.trace_server.interface.builtin_object_classes.llm_structured_model import (
    LLMStructuredCompletionModel,
)


@register_object
class LLMAsAJudgeScorer(Scorer):
    """LLM as a judge scorer that can use either a prompt string or a prompt reference.

    Attributes:
        model: The LLM model to use for scoring
        scoring_prompt: A prompt string template with {variable} placeholders (optional if prompt_ref is provided)
        prompt_ref: A reference to a MessagesPrompt object (optional, takes precedence over scoring_prompt)
    """

    model: LLMStructuredCompletionModel
    scoring_prompt: Optional[str] = None
    prompt_ref: Optional[base_object_def.RefStr] = None

    @op
    def score(self, *, output: str, **kwargs: Any) -> Any:
        """Score the output using either prompt_ref or scoring_prompt.

        Args:
            output: The model output to score
            **kwargs: Additional template variables for the prompt

        Returns:
            The model's prediction/score
        """
        # Combine output with kwargs for template variables
        template_vars = {"output": output, **kwargs}

        if self.prompt_ref:
            # Use prompt_ref - resolve it and format with template vars
            client = get_weave_client()
            if client is None:
                raise ValueError(
                    "Weave client not initialized. Call weave.init() first."
                )

            # Get the prompt object
            prompt_obj = client.get(self.prompt_ref)

            # Format the prompt with template variables
            if hasattr(prompt_obj, "format"):
                formatted_messages = prompt_obj.format(**template_vars)
            else:
                raise ValueError(
                    f"Prompt object at {self.prompt_ref} does not have a format method"
                )

            # Use the formatted messages directly
            return self.model.predict(formatted_messages)
        elif self.scoring_prompt:
            # Fall back to scoring_prompt
            scoring_prompt = self.scoring_prompt.format(**template_vars)
            model_input = [
                {"role": "user", "content": scoring_prompt},
            ]
            return self.model.predict(model_input)
        else:
            raise ValueError(
                "Either scoring_prompt or prompt_ref must be provided to LLMAsAJudgeScorer"
            )
