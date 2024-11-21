import math
from typing import Optional, Union

import weave
from weave.scorers.base_scorer import Scorer


class RobustnessScorer(Scorer):
    @weave.op
    def score(
        self,
        output: list[Union[str, bool]],
        ground_truths: Optional[list[Union[str, bool]]] = None,
    ) -> dict:
        """
        Calculates Cohen's h for text outputs by comparing predictions with ground truths.

        Args:
            output (List[Union[str, bool]]): Predictions from the system, which can be strings
                                             or booleans.
            ground_truths (List[Union[str, bool]], optional): A list of ground truths.
                - If strings: Compare predicted outputs directly to the ground truth values.
                - If booleans: Convert `True` to `"True"` and `False` to `"False"` for comparison.

        Returns:
            dict: A dictionary containing the original score (1.0), the average similarity
                  score for perturbed outputs, and the Cohen's h value.
        """
        assert (
            len(output) > 1
        ), "There must be output of at least one perturbed question."

        if ground_truths:
            assert len(ground_truths) == len(output), (
                "Length of ground_truths must match the length of output. "
                f"Got {len(ground_truths)} ground_truths and {len(output)} outputs."
            )

        # Normalize `output` and `ground_truths` to strings if necessary
        output = [str(o) if isinstance(o, bool) else o for o in output]
        if ground_truths:
            ground_truths = [
                str(gt) if isinstance(gt, bool) else gt for gt in ground_truths
            ]

        # Ensure all elements are strings
        assert all(isinstance(o, str) for o in output), "All outputs must be strings."
        if ground_truths:
            assert all(
                isinstance(gt, str) for gt in ground_truths
            ), "All ground_truths must be strings."

        # Original prediction (reference output) and perturbed predictions
        original = output[0]
        perturbed_outputs = output[1:]

        # Determine binary scores
        if ground_truths:
            binary_scores = [
                1 if output[i] == ground_truths[i] else 0 for i in range(len(output))
            ]
        else:
            # Default: Compare perturbed outputs to the original prediction
            binary_scores = [
                1 if perturbed == original else 0 for perturbed in perturbed_outputs
            ]

        # Original score is perfect similarity (1.0) with itself or the ground truth
        score_o = 1.0 if not ground_truths else binary_scores[0]

        # Average perturbed similarity score
        score_p = sum(binary_scores[1:]) / len(binary_scores[1:])

        def psi(score: float) -> float:
            return 2 * math.asin(math.sqrt(score))

        # Normalize Cohen's h by dividing by pi and take absolute value
        h = abs((psi(score_p) - psi(score_o)) / math.pi)

        return {"cohen_h": h, "score(original)": score_o, "score(perturbed)": score_p}
