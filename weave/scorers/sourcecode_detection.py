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


class SourceCodeDetector(Scorer):
    """
    Use wandb/sourcecode-detection classifier to check if input or output contains source code.

    Args:
        model_name: The name of the source code classifier model to use. Defaults to `wandb/sourcecode-detection`.
        device: The device to use for inference. Defaults to `cpu`.
    """

    device: str = "cpu"
    model_name_or_path: str = "wandb/sourcecode-detection"
    _classifier: Any = PrivateAttr()
    _label2id: dict[str, int] = PrivateAttr()

    def model_post_init(self, __context: Any) -> None:
        if not torch.cuda.is_available() and "cuda" in self.device:
            raise ValueError("CUDA is not available")
        self._classifier = pipeline(
            task="text-classification",
            model=self.model_name_or_path,
            device=self.device,
        )
        self._label2id = {"no_code": 0, "code": 1}

    @weave.op
    def score_texts(self, texts: list[str]) -> list[dict[str, Any]]:
        """Score a prompt response pair."""
        sourcecode_detection_output = self._classifier(texts)
        outputs = []
        for out in sourcecode_detection_output:
            outputs.append(
                {
                    "confidence": out["score"],
                    "has_code": bool(self._label2id.get(out["label"], -1)),
                }
            )

        return outputs

    @weave.op
    def score(
        self,
        input: Optional[str] = None,
        output: Optional[str] = None,
    ) -> dict[str, Any]:
        texts = []
        if input is not None:
            texts.append(input)
        if output is not None:
            texts.append(output)
        if not texts:
            raise ValueError("Either input or output must be provided")

        scores = self.score_texts(texts)
        return_dict = {}
        for text_type, score in zip(["input", "output"], scores):
            return_dict[f"{text_type}_has_code"] = score["has_code"]
            return_dict[f"{text_type}_confidence"] = score["confidence"]
        return return_dict
