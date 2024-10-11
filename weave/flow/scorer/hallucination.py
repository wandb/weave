from weave.flow.scorer.llm_scorer import PromptScorer


class HallucinationScorer(PromptScorer):
    def score(self, model_output, target):
        return super().score(model_output, target)
