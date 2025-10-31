from typing import Any

from weave.flow.scorer import Scorer
from weave.prompt.prompt import MessagesPrompt
from weave.trace.context.weave_client_context import get_weave_client
from weave.trace.objectify import register_object
from weave.trace.op import op
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
    scoring_prompt: str | None = None
    scoring_prompt_ref: str | None = None

    @op
    def score(self, *, output: str, **kwargs: Any) -> Any:
        """Score the output using the scoring_prompt.

        Args:
            output: The model output to score
            **kwargs: Additional template variables for the prompt

        Returns:
            The model's prediction/score
        """
        # Combine output with kwargs for template variables
        template_vars = {"output": output, **kwargs}

        if self.scoring_prompt_ref:
            client = get_weave_client()
            if client is None:
                raise ValueError(
                    "Weave client not initialized. Call weave.init() first."
                )
            scoring_prompt = client.get(self.scoring_prompt_ref)
            if not isinstance(scoring_prompt, MessagesPrompt):
                raise ValueError(
                    f"Prompt object at {self.scoring_prompt_ref} is not a MessagesPrompt"
                )
            formatted_messages = scoring_prompt.format(**template_vars)
            return self.model.predict(formatted_messages)
        elif isinstance(self.scoring_prompt, str):
            # Fall back to scoring_prompt
            scoring_prompt = self.scoring_prompt.format(**template_vars)
            model_input = [
                {"role": "user", "content": scoring_prompt},
            ]
            return self.model.predict(model_input)
        else:
            raise ValueError(
                "Either scoring_prompt or scoring_prompt_ref must be provided to LLMAsAJudgeScorer"
            )
