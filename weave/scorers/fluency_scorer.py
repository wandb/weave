import weave
from weave.scorers.llm_scorer import HuggingFacePipelineScorer
from weave.scorers.llm_utils import set_device


class FluencyScorer(HuggingFacePipelineScorer):
    """
    W&B Fluency Scorer

    This scorer uses an in-house model to score fluency based on ModernBert.
    
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
    model_name_or_path: str = "tcapelle/fluency-scorer" # TODO: replace with an artifact
    device: str = "auto"

    
    def _load_pipeline(self) -> None:
        """Loads the _pipeline attribute"""
        from transformers import pipeline
        self.device = set_device(self.device)
        self._pipeline = pipeline(
            "text-classification", 
            model=self.model_name_or_path,
            device=self.device
        )
    
    @weave.op
    def score(self, output: str):
        pipeline_output = self._pipeline(output)
        return {"flagged": pipeline_output[0]["label"] == "non-fluent"}