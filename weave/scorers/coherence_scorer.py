from typing import Any, Optional

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
    model_name_or_path: str = "wandb/coherence_scorer"
    base_url: Optional[str] = None
    _classifier: Any = PrivateAttr()
    _label2id: dict[str, int] = PrivateAttr()

    def model_post_init(self, __context: Any) -> None:
        if self.base_url:
            print(f"Using external API at {self.base_url} for scoring.")
            return  # Skip local model loading if base_url is provided
        if not torch.cuda.is_available() and "cuda" in self.device:
            raise ValueError("CUDA is not available")
        self._classifier = pipeline(
            task="sentiment-analysis", model=self.model_name_or_path, device=self.device
        )
        self._label2id = {
            "Completely Incoherent": 0,
            "Mostly Incoherent": 1,
            "A Little Incoherent": 2,
            "Mostly Coherent": 3,
            "Perfectly Coherent": 4,
        }

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
            "is_coherent": coherent,
            "coherence": coherence_output["label"],
            "coherence_score": self._label2id[coherence_output["label"]],
            "confidence": coherence_output["score"],
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
    
    def _score_via_api(
            self, 
            input: str, 
            output: str, 
            chat_history: Optional[list[dict[str, str]]] = None, 
            context: Optional[str] = None
    ) -> dict[str, Any]:
        import requests
        response = requests.post(
            self.base_url,
            json={"input": input, "output": output, "chat_history": chat_history, "context": context}
        )
        response.raise_for_status()
        return response.json()
    
    @weave.op
    def score(
        self,
        input: str,
        output: str,
        chat_history: Optional[list[dict[str, str]]] = None,
        context: Optional[str] = None,
    ) -> dict[str, Any]:
        if self.base_url:
            return self._score_via_api(input, output, chat_history, context)
        prompt = input
        if chat_history is not None:
            history = self._format_chat_history(chat_history)
            prompt = f"{history}{input}"
        if context is not None:
            prompt = f"{input}\n\n{context}"
        return self.score_messages(prompt, output)