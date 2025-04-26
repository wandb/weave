from typing import Any, Optional, Union

from pydantic import Field, validate_call

import weave
from weave.flow.scorer import WeaveScorerResult
from weave.scorers.default_models import MODEL_PATHS
from weave.scorers.scorer_types import HuggingFacePipelineScorer
from weave.scorers.utils import load_hf_model_weights


class WeaveCoherenceScorerV1(HuggingFacePipelineScorer):
    """
    The scorer that assesses if the model output is coherent using a fine-tuned
    deberta-small-long-nli model from tasksource, https://huggingface.co/tasksource/deberta-small-long-nli
    Use wandb/coherence_scorer to check if the model output is coherent.
    Args:
        model_name: The name of the coherence scorer model to use. Defaults to `wandb/coherence_scorer`.
        model_max_length: The maximum length of the model output. Defaults to 1024.

    Example:
    >>> scorer = WeaveCoherenceScorerV1()
    >>> result = scorer.score(output="I am feeling sad", query="Hey how are you")
    >>> print(result)
    WeaveScorerResult(
      passed=True,
      metadata={
        'coherence_label': 'Perfectly Coherent',
        'coherence_id': 4, 'score': 0.8576799035072327}
    )
    """

    task: str = "sentiment-analysis"
    model_max_length: int = Field(
        default=1024, description="The maximum length of the model output."
    )

    def load_pipeline(self) -> None:
        from transformers import pipeline

        self._local_model_path = load_hf_model_weights(
            self.model_name_or_path, MODEL_PATHS["coherence_scorer"]
        )
        self._pipeline = pipeline(
            task=self.task,
            model=self._local_model_path,
            device=self.device,
            max_length=self.model_max_length,
            truncation=True,
        )

    def _score_messages(self, prompt: str, output: str) -> WeaveScorerResult:
        """Score a prompt response pair."""
        assert self._pipeline is not None
        coherence_output = self._pipeline(inputs={"text": prompt, "text_pair": output})
        passed = True
        if "incoherent" in coherence_output["label"].lower():
            passed = False
        label = coherence_output["label"]
        id = self._pipeline.model.config.label2id[label]

        return WeaveScorerResult(
            passed=passed,
            metadata={
                "coherence_label": label,
                "coherence_id": id,
                "score": coherence_output["score"],
            },
        )

    def _format_chat_history(self, chat_history: list[dict[str, str]]) -> str:
        """Format the chat history for the prompt."""
        formatted_chat_history = ""
        for turn in chat_history:
            if turn["role"] == "user":
                formatted_chat_history += f"{turn['content']}\n<extra_id_1>Assistant\n"
            else:
                formatted_chat_history += f"{turn['content']}\n<extra_id_1>User\n"
        return formatted_chat_history

    @validate_call
    @weave.op
    def score(
        self,
        *,
        query: str,
        output: str,
        chat_history: Optional[list[dict[str, str]]] = None,
        context: Optional[Union[str, list[str]]] = None,
        **kwargs: Any,
    ) -> WeaveScorerResult:
        """
        Score the Coherence of the query and output.
        Args:
            query: text to score, must be a string
            output: text to score, must be a string
            chat_history: [optional] chat history to score, must be a list of dictionaries with keys `role` and `content`
            context: [optional] context to score, must be a string
        """
        prompt = query
        if chat_history is not None and context is not None:
            raise ValueError("Cannot provide both `chat_history` and `context`")
        if chat_history:
            history = self._format_chat_history(chat_history)
            prompt = f"{history}{query}"
        if context:
            if isinstance(context, list):
                context = "\n\n".join(context)
            prompt = f"{query}\n\n{context}"
        return self._score_messages(prompt, output)
