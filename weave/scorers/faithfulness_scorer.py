from weave.scorers.hallucination_scorer import HallucinationScorer

from weave.scorers.hallucination_scorer import HALLUCINATION_SCORER_THRESHOLD

FAITHFULNESS_SCORER_THRESHOLD = HALLUCINATION_SCORER_THRESHOLD

class FaithfulnessScorer(HallucinationScorer):
    """A scorer that evaluates the faithfulness of model outputs to their input context.

    This scorer is an alias for HallucinationScorer, as both measure the same underlying concept:
    whether the model output contains information not supported by or contradicting the input context.

    See HallucinationScorer for full documentation of parameters, methods and return values.
    """

    pass
