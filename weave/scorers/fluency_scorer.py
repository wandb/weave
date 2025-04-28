from typing import Any

from pydantic import Field, validate_call

import weave
from weave.flow.scorer import WeaveScorerResult
from weave.scorers.default_models import MODEL_PATHS
from weave.scorers.scorer_types import HuggingFacePipelineScorer
from weave.scorers.utils import load_hf_model_weights

FLUENCY_SCORER_THRESHOLD = 0.5


class WeaveFluencyScorerV1(HuggingFacePipelineScorer):
    """
    The scorer uses an fine-tuned ModernBert model to score a given text's fluency,
    https://github.com/AnswerDotAI/ModernBERT

    Args:
        threshold (float): The threshold for the non-fluent score. Defaults to 0.5.
        device (str): The device to use for inference. Defaults to "auto".

    Note: This Scorer's `score` method expects the text to be passed as a string to its `output` parameter.

    Example:
        >>> from weave.scorers.fluency_scorer import WeaveFluencyScorerV1
        >>> scorer = WeaveFluencyScorerV1()
        >>> result = scorer.score("This text is fluent.")
        >>> print(result)
        WeaveScorerResult(
            passed=True,
            metadata={
                'score': 0.95
            }
        )
    """

    task: str = "text-classification"
    threshold: float = Field(
        default=FLUENCY_SCORER_THRESHOLD,
        description="The threshold for the non-fluent score.",
    )

    def load_pipeline(self) -> None:
        """Loads the _pipeline attribute using HF utilities"""
        from transformers import pipeline

        self._local_model_path = load_hf_model_weights(
            self.model_name_or_path, MODEL_PATHS["fluency_scorer"]
        )
        self._pipeline = pipeline(
            self.task,
            model=self._local_model_path,
            device=self.device,
            top_k=2,
        )

    @validate_call
    @weave.op
    def score(self, *, output: str, **kwargs: Any) -> WeaveScorerResult:
        assert self._pipeline is not None
        pipeline_output = self._pipeline(output)[0]
        fluency_score = next(
            pred["score"] for pred in pipeline_output if pred["label"] == "fluent"
        )
        passed = fluency_score >= self.threshold
        return WeaveScorerResult(
            passed=passed,
            metadata={"score": fluency_score},
        )
