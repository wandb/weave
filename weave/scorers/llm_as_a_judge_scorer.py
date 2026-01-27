from typing import Any

from pydantic import AliasChoices, ConfigDict, Field, field_validator

from weave.flow.scorer import Scorer
from weave.prompt.prompt import MessagesPrompt
from weave.trace.context.weave_client_context import get_weave_client
from weave.trace.objectify import maybe_objectify, register_object
from weave.trace.op import op
from weave.trace.vals import make_trace_obj
from weave.trace_server.interface.builtin_object_classes.llm_structured_model import (
    LLMStructuredCompletionModel,
)


@register_object
class LLMAsAJudgeScorer(Scorer):
    """LLM as a judge scorer that uses a prompt to score outputs.

    Attributes:
        model: The LLM model to use for scoring.
        scoring_prompt: Either a string template with {variable} placeholders,
            or a MessagesPrompt object (can be passed via weave.ref()).
        enable_audio_input_scoring: Specifies whether the scorer should score audio input.
        media_scoring_json_paths: Specifies the JSON paths to use to extract media content from the input
    """

    model_config = ConfigDict(populate_by_name=True)

    model: LLMStructuredCompletionModel
    scoring_prompt: str | MessagesPrompt
    enable_audio_input_scoring: bool = False
    media_scoring_json_paths: list[str] | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "media_scoring_json_paths", "audio_input_scoring_json_paths"
        ),
    )

    @field_validator("scoring_prompt", mode="before")
    @classmethod
    def validate_scoring_prompt(cls, v: Any) -> str | MessagesPrompt:
        """Convert ObjectRecord to MessagesPrompt if needed."""
        if isinstance(v, (str, MessagesPrompt)):
            return v
        # Handle ObjectRecord from deserialization
        client = get_weave_client()
        if client is None:
            return v
        trace_obj = make_trace_obj(v, None, client.server, None)
        result = maybe_objectify(trace_obj)
        if isinstance(result, MessagesPrompt):
            return result
        return v

    @op
    def score(self, *, output: str, **kwargs: Any) -> Any:
        """Score the output using the scoring_prompt."""
        if isinstance(self.scoring_prompt, MessagesPrompt):
            model_input = self.scoring_prompt.format(output=output, **kwargs)
        else:
            scoring_prompt = self.scoring_prompt.format(output=output, **kwargs)
            model_input = [{"role": "user", "content": scoring_prompt}]
        return self.model.predict(model_input)
