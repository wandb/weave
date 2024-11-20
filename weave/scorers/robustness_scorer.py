from typing import Optional, List
import math

import weave
from weave.scorers.base_scorer import Scorer, auto_summarize


class RobustnessScorer(Scorer):
    """
    A scorer that evaluates the robustness of an LLM system. The system can be the LLM itself or something more complex like a pipeline.

    # TODO: better detailing
    The robustness scorer checks for the following:
    - Robustness to permuted inputs: This robustness metric measures insensitivity of the system's answers to meaning-preserving variants of their input. The permutations are categorized as superficial, paraphrasing and distractions. For more details, refer to the [A Novel Metric for Measuring the Robustness of Large Language Models in Non-adversarial Scenarios](https://arxiv.org/abs/2408.01963v1).

    We use the `cohen's h` to quatify the robustness of the system. Unlike the Performance Drop Rate (PDR), which has certain limitations:
    - Asymmetry: PDR overweights performance improvements compared to equivalent performance drops, leading to biased results.
    - Undefined for Zero Scores: PDR is undefined when the original score is zero, causing biased averages by ignoring such cases.

    `cohen's h` is symmetric and well-defined for zero scores, making it a more appropriate metric for measuring robustness.
    """

    @weave.op
    def score(self, output: List[str]) -> dict:
        """
        Calculates Cohen's h for text outputs by comparing string similarity
        of perturbed generations with the original generation.

        Args:
            output (List[str]): A list of strings where the first element is the original
                                generation and the rest are the perturbed generations.

        Returns:
            dict: A dictionary containing the original score (1.0), the average similarity
                  score for perturbed outputs, and the Cohen's h value.
        """
        assert len(output) > 1, "There must be output of at least one perturbed question"

        # Original generation (reference output) and perturbed generations
        original = output[0]
        perturbed_outputs = output[1:]

        # Compute similarity scores for each perturbed output
        # TODO: The scores should be provided by the caller especially for reference evaluations.
        binary_scores = [1 if perturbed == original else 0 for perturbed in perturbed_outputs]

        # Original score is perfect similarity (1.0) with itself
        score_o = 1.0

        # Average perturbed similarity score
        score_p = sum(binary_scores) / len(binary_scores)

        def psi(score: float) -> float:
            return 2 * math.asin(math.sqrt(score))

        # Normalize Cohen's h by dividing by pi and take absolute value
        h = abs((psi(score_p) - psi(score_o)) / math.pi)

        return {"cohen_h": h}
