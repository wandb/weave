import weave
import os
from weave.scorers.llm_scorer import HuggingFacePipelineScorer
from weave.scorers.llm_utils import set_device, download_model, MODEL_PATHS


FLUENCY_SCORER_THRESHOLD = 0.5

class FluencyScorer(HuggingFacePipelineScorer):
    """
    W&B Fluency Scorer

    This scorer uses an in-house model to score fluency based on ModernBert.

    Args:
        threshold (float): The threshold for the non-fluent score. Defaults to 0.5.
        device (str): The device to use for inference. Defaults to "auto".
    
    Example:
        >>> from weave.scorers.fluency_scorer import FluencyScorer
        >>> scorer = FluencyScorer()
        >>> result = scorer.score("This text is fluent.")
        >>> print(result)
        {
            'flagged': True,
        }
    """
    task: str = "text-classification"
    model_name_or_path: str = ""
    device: str = "auto"
    threshold: float = FLUENCY_SCORER_THRESHOLD

    
    def _load_pipeline(self) -> None:
        """Loads the _pipeline attribute"""
        from transformers import pipeline
        self.device = set_device(self.device)
        if os.path.isdir(self.model_name_or_path):
            self._local_model_path = self.model_name_or_path
        elif self.model_name_or_path != "":
            self._local_model_path = download_model(self.model_name_or_path)
        else:
            self._local_model_path = download_model(MODEL_PATHS["fluency_scorer"])

        self._pipeline = pipeline(
            "text-classification", 
            model=self._local_model_path,
            device=self.device,
            top_k=2,
        )

    @weave.op
    def score(self, output: str):
        pipeline_output = self._pipeline(output)[0]
        fluency_score = next(pred['score'] for pred in pipeline_output if pred['label'] == 'fluent')
        if fluency_score <= self.threshold:
            return {"flagged": True, "extras": {"score": fluency_score}}
        return {"flagged": False, "extras": {"score": fluency_score}}
