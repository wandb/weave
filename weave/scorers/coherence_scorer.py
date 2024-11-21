import re
from typing import TYPE_CHECKING, Any, Optional

from pydantic import PrivateAttr

import weave
from weave.scorers.base_scorer import Scorer

try:
    import torch
    from transformers import pipeline
except ImportError:
    import_failed = True
    print(
        "The `transformers` package is required to use the CoherenceScorer, please run `pip install transformers`"
    )


class CoherenceScorer(Scorer):
    """
    Use wandb/coherence_scorer to check if the model output is coherent.

    Args:
        model_name: The name of the coherence scorer model to use. Defaults to `wandb/coherence_scorer`.
        device: The device to use for inference. Defaults to `cpu`.
    """

    device: str = "cpu"
    model_name: str = "wandb/coherence_scorer"
    _classifier: Any = PrivateAttr()

    def model_post_init(self, __context: Any) -> None:
        if not torch.cuda.is_available() and "cuda" in self.device:
            raise ValueError("CUDA is not available")
        self._classifier = pipeline(
            task="sentiment-analysis", model=self.model_name, device=self.device
        )

    @weave.op
    def score_messages(self, prompt: str, output: str) -> dict[str, Any]:
        """Score a prompt response pair."""
        coherence_output = self._classifier(
            inputs={"text": prompt, "text_pair": output}
        )
        coherent = True
        if "incoherent" in coherence_output["label"].lower():
            coherent = False

        return {
            "coherent": coherent,
            "coherence": coherence_output["label"],
            "coherence_score": coherence_output["score"],
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
    async def score(
        self,
        input: str,
        output: str,
        chat_history: Optional[list[dict[str, str]]] = None,
        context: Optional[str] = None,
    ) -> dict[str, Any]:
        prompt = input
        if chat_history is not None:
            chat_history = self._format_chat_history(chat_history)
            prompt = f"{chat_history}{input}"
        if context is not None:
            prompt = f"{input}\n\n{context}"
        return self.score_messages(prompt, output)
