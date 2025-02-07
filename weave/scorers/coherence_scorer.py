from typing import Optional, Union

import weave
from weave.scorers.llm_scorer import HuggingFacePipelineScorer
from weave.scorers.utils import (
    MODEL_PATHS,
    ScorerResult,
    check_score_param_type,
    ensure_hf_imports,
    load_hf_model_weights,
)


class WeaveCoherenceScorer(HuggingFacePipelineScorer):
    """
    The scorer that assesses if the model output is coherent using a fine-tuned
    deberta-small-long-nli model from tasksource, https://huggingface.co/tasksource/deberta-small-long-nli

    Use wandb/coherence_scorer to check if the model output is coherent.

    Args:
        model_name: The name of the coherence scorer model to use. Defaults to `wandb/coherence_scorer`.
        device: The device to use for inference. Defaults to `auto`, which will use `cuda` if available.
    """

    task: str = "sentiment-analysis"
    model_max_length: int = 1024
    _label2id: dict[str, int] = {
        "Completely Incoherent": 0,
        "Mostly Incoherent": 1,
        "A Little Incoherent": 2,
        "Mostly Coherent": 3,
        "Perfectly Coherent": 4,
    }

    def _load_pipeline(self) -> None:
        # Lazy import of transformers
        ensure_hf_imports()
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

    @weave.op
    def score_messages(self, prompt: str, output: str) -> ScorerResult:
        """Score a prompt response pair."""
        assert self._pipeline is not None
        coherence_output = self._pipeline(inputs={"text": prompt, "text_pair": output})
        passed = True
        if "incoherent" in coherence_output["label"].lower():
            passed = False

        return ScorerResult(
            passed=passed,
            extras={
                "coherence_label": coherence_output["label"],
                "coherence_id": self._label2id[coherence_output["label"]],
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

    @weave.op
    def score(
        self,
        query: str,
        output: str,
        chat_history: Optional[list[dict[str, str]]] = None,
        context: Optional[Union[str, list[str]]] = None,
    ) -> ScorerResult:
        """
        Score the Coherence of the query and output.

        Args:
            query: text to score, must be a string
            output: text to score, must be a string
            chat_history: [optional] chat history to score, must be a list of dictionaries with keys `role` and `content`
            context: [optional] context to score, must be a string
        """
        check_score_param_type(output, str, "output", self)
        check_score_param_type(query, str, "query", self)
        prompt = query
        if chat_history:
            check_score_param_type(chat_history, list, "chat_history", self)
            history = self._format_chat_history(chat_history)
            prompt = f"{history}{query}"
        if context:
            check_score_param_type(context, (list, str), "context", self)
            if isinstance(context, list):
                context = "\n\n".join(context)
            prompt = f"{query}\n\n{context}"
        return self.score_messages(prompt, output)
