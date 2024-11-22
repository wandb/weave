import math
from typing import Any, Optional, Union

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

import weave
from weave.scorers.base_scorer import Scorer


class RobustnessScorer(Scorer):
    """
    RobustnessScorer evaluates the robustness of a language model's outputs against input perturbations.

    The scorer measures how much the model's outputs change when the inputs are slightly altered.
    It quantifies this change using statistical effect size measures:

    - **Cohen's h** for binary (exact match) comparisons.
    - **Cohen's d** for continuous (semantic similarity) comparisons.

    The scorer supports both exact match (binary) and semantic similarity evaluations. Both metrics are statistical measures and should be interpreted accordingly.

    Attributes:
        binary (bool): If True, uses exact match for binary scoring and computes Cohen's h.
                       If False, uses semantic similarity and computes Cohen's d.
        embedding_model_name (str): Name of the embedding model to use for computing semantic similarity.
        similarity_metric (str): The similarity metric to use. Currently, only 'cosine' is supported.
        embedding_model (Optional[SentenceTransformer]): The loaded embedding model used for computing embeddings.

    Usage Example:
        # Initialize the scorer
        scorer = RobustnessScorer(binary=False)

        # Outputs from the model
        outputs = [
            "The capital of France is Paris.",
            "Paris is the capital of France.",
            "France's capital is Berlin."
        ]

        # Compute the robustness score
        result = scorer.score(output=outputs)

        print("Robustness Scorer Results:")
        print(result)
    """

    binary: bool = True
    embedding_model_name: str = "all-MiniLM-L6-v2"
    similarity_metric: str = "cosine"
    embedding_model: Optional[SentenceTransformer] = None

    def model_post_init(self, __context: Any) -> None:
        """
        Post-initialization method to load the embedding model if required.

        Args:
            __context (Any): Contextual information (not used in this implementation).
        """
        # Load an embedding model for semantic similarity scoring
        if not self.binary:
            self.embedding_model = SentenceTransformer(self.embedding_model_name)

    @weave.op
    def score(
        self,
        output: list[Union[str, bool]],
        ground_truths: Optional[list[Union[str, bool]]] = None,
    ) -> dict:
        """
        Computes the robustness score of the model's outputs.

        Args:
            output (List[Union[str, bool]]): A list containing the original output followed by perturbed outputs.
            ground_truths (Optional[List[Union[str, bool]]]): Optional list of ground truths corresponding to each output.

        Returns:
            dict: A dictionary containing the robustness metrics and scores.

                - For binary scoring:
                    - "cohen_h": The computed Cohen's h value.
                - For non-binary scoring:
                    - "cohen_d": The computed Cohen's d value.

                Common keys:
                    - "score(original)": The similarity score of the original output.
                    - "score(perturbed)": The mean similarity score of the perturbed outputs.

        Raises:
            AssertionError: If the inputs are invalid or inconsistent.
            ValueError: If an unsupported similarity metric is specified.
        """
        assert (
            len(output) > 1
        ), "There must be output of at least one perturbed question."

        if ground_truths:
            assert len(ground_truths) == len(output), (
                "Length of ground_truths must match the length of output. "
                f"Got {len(ground_truths)} ground_truths and {len(output)} outputs."
            )

        # Normalize `output` and `ground_truths` to strings
        output = [str(o) for o in output]
        if ground_truths:
            ground_truths = [str(gt) for gt in ground_truths]

        # Ensure all elements are strings
        assert all(isinstance(o, str) for o in output), "All outputs must be strings."
        if ground_truths:
            assert all(
                isinstance(gt, str) for gt in ground_truths
            ), "All ground_truths must be strings."

        # Original prediction and perturbed predictions
        original = output[0]
        perturbed_outputs = output[1:]

        # Compute similarity scores
        if self.binary:
            # Binary scoring using exact match
            if ground_truths:
                similarities = [
                    1.0 if output[i] == ground_truths[i] else 0.0
                    for i in range(len(output))
                ]
                score_o = similarities[0]
                perturbed_similarities = similarities[1:]
            else:
                similarities = [
                    1.0 if perturbed == original else 0.0
                    for perturbed in perturbed_outputs
                ]
                score_o = 1.0  # Original output compared with itself
                perturbed_similarities = similarities
        else:
            # Semantic similarity scoring
            if ground_truths:
                similarities = [
                    self.compute_similarity(output[i], ground_truths[i])
                    for i in range(len(output))
                ]
                score_o = similarities[0]
                perturbed_similarities = similarities[1:]
            else:
                similarities = [
                    self.compute_similarity(original, perturbed)
                    for perturbed in perturbed_outputs
                ]
                score_o = 1.0  # Similarity of original output with itself
                perturbed_similarities = similarities

        if not self.binary:
            # Compute Cohen's d for continuous scores
            d = self.compute_cohens_d(score_o, perturbed_similarities)
            return {
                "cohen_d": d,
                "score(original)": score_o,
                "score(perturbed)": np.mean(perturbed_similarities).item(),
            }
        else:
            # Compute Cohen's h for binary scores
            h = self.compute_cohens_h(score_o, perturbed_similarities)
            return {
                "cohen_h": h,
                "score(original)": score_o,
                "score(perturbed)": np.mean(perturbed_similarities).item(),
            }

    def compute_cohens_h(
        self, score_o: float, perturbed_similarities: list[float]
    ) -> float:
        """
        Computes Cohen's h for binary scores.

        Cohen's h measures the effect size for proportions, suitable for binary data.
        It is calculated using the arcsine transformation of the proportions.

        Args:
            score_o (float): The similarity score of the original output (0 or 1).
            perturbed_similarities (List[float]): Similarity scores of perturbed outputs (0s and 1s).

        Returns:
            float: The absolute value of Cohen's h normalized by π.

        Interpretation:
            - **0.0 ≤ h < 0.0032**: Essentially no effect
            - **0.0032 ≤ h < 0.0637**: Very small effect
            - **0.0637 ≤ h < 0.1592**: Small effect
            - **0.1592 ≤ h < 0.2546**: Medium effect
            - **0.2546 ≤ h < 0.3820**: Large effect
            - **0.3820 ≤ h < 0.6366**: Very large effect
            - **0.6366 ≤ h < 1**: Huge effect

        Note that the interpretation is a rule of thumb and may not be appropriate for small sample sizes. Feel free to interpret the results according to your use case.

        """
        def psi(score: float) -> float:
            """Arcsine transformation used in Cohen's h calculation."""
            return 2 * math.asin(math.sqrt(score))

        # Average perturbed similarities
        score_p = sum(perturbed_similarities) / len(perturbed_similarities)

        # Compute Cohen's h and normalize by π
        h = abs((psi(score_p) - psi(score_o)) / math.pi)

        return h

    def compute_cohens_d(
        self, score_o: float, perturbed_similarities: list[float]
    ) -> float:
        """
        Computes Cohen's d for continuous scores.

        Cohen's d measures the effect size for the differences between two means,
        suitable for continuous data. In this context, it quantifies the impact
        of perturbations on the similarity scores.

        Args:
            score_o (float): The similarity score of the original output (usually 1.0).
            perturbed_similarities (List[float]): Similarity scores of perturbed outputs.

        Returns:
            float: The computed Cohen's d value.

        Interpretation:
            - **0.0 ≤ d < 0.01**: Negligible effect
            - **0.01 ≤ d < 0.19**: Very small effect
            - **0.19 ≤ d < 0.49**: Small effect
            - **0.49 ≤ d < 0.79**: Medium effect
            - **0.79 ≤ d < 1.19**: Large effect
            - **1.19 ≤ d < 1.99**: Very large effect
            - **1.99 ≤ d**: Huge effect

        Note that the interpretation is a rule of thumb and may not be appropriate for small sample sizes. Feel free to interpret the results according to your use case. Refer to the notes below for more details.

        Notes:
            - A positive Cohen's d indicates that the original score is higher than
              the perturbed scores on average, suggesting that perturbations decrease
              the similarity.
            - A negative Cohen's d indicates that the perturbed scores are higher,
              which may suggest unexpected behavior.
            - Interpretation should consider the practical significance and context,
              especially with small sample sizes.
            - If the standard deviation of the differences is zero, the effect size is 0.
            - If the standard deviation is very close to zero and the mean difference is also close to zero, the effect size will be large which is counter intuitive. Either increase the number of perturbed outputs or use binary scoring in such cases. Alternatively, interpret the results accordingly.

        """
        differences = [score_o - s for s in perturbed_similarities]
        mean_diff = np.mean(differences)
        std_diff = np.std(differences, ddof=1)  # Sample standard deviation

        if std_diff == 0:
            return 0.0  # No variability in differences; negligible effect
        else:
            return (mean_diff / std_diff).item()

    def compute_similarity(self, text1: str, text2: str) -> float:
        """
        Computes similarity between two texts based on the specified metric.

        Args:
            text1 (str): The first text string.
            text2 (str): The second text string.

        Returns:
            float: Similarity score between 0 and 1.

        Raises:
            ValueError: If an unsupported similarity metric is specified.

        Supported Similarity Metrics:
            - **"cosine"**: Cosine similarity between sentence embeddings.

        Notes:
            - Requires the embedding model to be loaded (when `binary=False`).
            - Cosine similarity is computed using sentence embeddings from the specified model.
            - You can use any other embedding model by setting the `embedding_model_name` attribute which is compatible with `SentenceTransformer`. This flexibility will allow you to use the right embedding representation for your use case.

        """
        if self.similarity_metric == "cosine":
            # Ensure the embedding model is loaded
            if self.embedding_model is None:
                raise ValueError("Embedding model is not initialized.")

            # Compute cosine similarity between sentence embeddings
            embeddings = self.embedding_model.encode([text1, text2])
            sim = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
            return sim.item()
        else:
            raise ValueError(f"Unsupported similarity metric: {self.similarity_metric}")
