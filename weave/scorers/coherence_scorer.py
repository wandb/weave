import os
from typing import Any, Optional

import weave
from weave.scorers.llm_scorer import HuggingFacePipelineScorer
from weave.scorers.llm_utils import MODEL_PATHS, download_model


class CoherenceScorer(HuggingFacePipelineScorer):
    """
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
        from transformers import pipeline
        if os.path.isdir(self.model_name_or_path):
            self._local_model_path = self.model_name_or_path
        elif self.model_name_or_path != "":
            self._local_model_path = download_model(self.model_name_or_path)
        else:
            self._local_model_path = download_model(MODEL_PATHS["coherence_scorer"])

        self._pipeline = pipeline(
            task=self.task,
            model=self._local_model_path,
            device=self.device,
            max_length=self.model_max_length,
            truncation=True,
        )

    @weave.op
    def score_messages(self, prompt: str, output: str) -> dict[str, Any]:
        """Score a prompt response pair."""
        assert self._pipeline is not None
        coherence_output = self._pipeline(inputs={"text": prompt, "text_pair": output})
        coherence_score = 1 - coherence_output["score"]
        passed = True
        if "incoherent" in coherence_output["label"].lower():
            passed = False

        return {
            "pass": passed,
            "extras": {
                "coherence_label": coherence_output["label"],
                "coherence_id": self._label2id[coherence_output["label"]],
                "score": coherence_score,
            },
        }

    def _format_chat_history(self, chat_history: list[dict[str, str]]) -> str:
        """Format the chat history for the prompt."""
        formatted_chat_history = ""
        for turn in chat_history:
            if turn["role"] == "user":
                formatted_chat_history += f"{turn['text']}\n<extra_id_1>Assistant\n"
            else:
                formatted_chat_history += f"{turn['text']}\n<extra_id_1>User\n"
        return formatted_chat_history

    @weave.op
    def score(
        self,
        query: str,
        output: str,
        chat_history: Optional[list[dict[str, str]]] = None,
        context: Optional[str] = None,
    ) -> dict[str, Any]:
        prompt = query
        if chat_history is not None:
            history = self._format_chat_history(chat_history)
            prompt = f"{history}{query}"
        if context is not None:
            prompt = f"{query}\n\n{context}"
        return self.score_messages(prompt, output)
