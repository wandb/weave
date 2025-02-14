from pydantic import validate_call, Field

import weave
from weave.scorers.scorer_types import HuggingFacePipelineScorer
from weave.scorers.default_models import MODEL_PATHS
from weave.scorers.utils import (
    WeaveScorerResult,
    ensure_hf_imports,
    load_hf_model_weights,
)

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
        {
            'pass': True,
            'extras': {
                'score': 0.95
            }
        }
    """

    task: str = "text-classification"
    model_name_or_path: str = ""
    device: str = "auto"
    threshold: float = Field(default=FLUENCY_SCORER_THRESHOLD, description="The threshold for the non-fluent score.")

    def load_pipeline(self) -> None:
        """Loads the _pipeline attribute using HF utilities"""
        from transformers import pipeline

        ensure_hf_imports()
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
    def score(self, output: str) -> WeaveScorerResult:
        pipeline_output = self._pipeline(output)[0]  # type: ignore
        fluency_score = next(
            pred["score"] for pred in pipeline_output if pred["label"] == "fluent"
        )
        passed = fluency_score >= self.threshold
        return WeaveScorerResult(
            passed=passed,
            extras={"score": fluency_score},
        )