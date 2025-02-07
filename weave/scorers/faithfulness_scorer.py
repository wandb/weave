from weave.scorers.hallucination_scorer import (
    HALLUCINATION_SCORER_THRESHOLD,
    WeaveHallucinationScorer,
)

FAITHFULNESS_SCORER_THRESHOLD = HALLUCINATION_SCORER_THRESHOLD


class WeaveFaithfulnessScorer(WeaveHallucinationScorer):
    """A scorer that evaluates the faithfulness of model outputs to their input context.
    This scorer uses the HHEM 2.1 model from Vectara, https://huggingface.co/vectara/hallucination_evaluation_model

    For now this scorer is an alias for WeaveHallucinationScorer, as both measure the same underlying concept:
    whether the model output contains information not supported by or contradicting the input context.

    See WeaveHallucinationScorer for full documentation of parameters, methods and return values.
    """

    pass
