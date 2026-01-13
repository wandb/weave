from typing import Any

from weave.flow.scorer import Scorer
from weave.trace.objectify import register_object
from weave.trace.op import op
from weave.trace_server.interface.builtin_object_classes.llm_structured_model import (
    LLMStructuredCompletionModel,
)


@register_object
class LLMAsAJudgeScorer(Scorer):
    model: LLMStructuredCompletionModel
    scoring_prompt: str
    # Specifies whether the scorer should use audio
    enable_audio_input_scoring: bool = False
    # Specifies the JSON paths to use to extract audio content from the input
    audio_input_scoring_json_paths: list[str] | None = None

    @op
    def score(self, *, output: str, **kwargs: Any) -> Any:
        scoring_prompt = self.scoring_prompt.format(output=output, **kwargs)
        model_input = [
            {"role": "user", "content": scoring_prompt},
        ]
        return self.model.predict(model_input)
