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

    @op
    def score(self, *, output: str, **kwargs: Any) -> Any:
        scoring_prompt = self.scoring_prompt.format(output=output, **kwargs)
        model_input = [
            {"role": "user", "content": scoring_prompt},
        ]
        return self.model.predict(model_input)
