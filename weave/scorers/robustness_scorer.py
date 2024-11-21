import math
from typing import Any, Optional, Union

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

import weave
from weave.scorers.base_scorer import Scorer


class RobustnessScorer(Scorer):
    binary: bool = True
    embedding_model_name: str = "all-MiniLM-L6-v2"
    similarity_metric: str = "cosine"
    embedding_model: Optional[SentenceTransformer] = None

    def model_post_init(self, __context: Any) -> None:
        # Load an embedding model
        if self.binary:
            self.embedding_model = None
        else:
            self.embedding_model = SentenceTransformer(self.embedding_model_name)

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

        # Compute similarity scores
        if self.binary:
            # Binary scoring using exact match
            if ground_truths:
                similarities = [
                    1.0 if output[i] == ground_truths[i] else 0.0
                    for i in range(len(output))
                ]
            else:
                similarities = [
                    1.0 if perturbed == original else 0.0
                    for perturbed in perturbed_outputs
                ]
        else:
            # Semantic similarity scoring
            if ground_truths:
                similarities = [
                    self.compute_similarity(output[i], ground_truths[i])
                    for i in range(len(output))
                ]
            else:
                similarities = [
                    self.compute_similarity(original, perturbed)
                    for perturbed in perturbed_outputs
                ]

        # Original score
        score_o = (
            similarities[0]
            if ground_truths
            else (1.0 if self.binary else similarities[0])
        )

        # Perturbed scores
        perturbed_similarities = similarities[1:] if ground_truths else similarities

        if not self.binary:
            # compute cohens d
            d = self.compute_cohens_d(score_o, perturbed_similarities)
            return {
                "cohen_d": d,
                "score(original)": score_o,
                "score(perturbed)": np.mean(perturbed_similarities),
            }
        else:
            # compute cohens h
            h = self.compute_cohens_h(score_o, perturbed_similarities)
            return {
                "cohen_h": h,
                "score(original)": score_o,
                "score(perturbed)": np.mean(perturbed_similarities),
            }

    def compute_cohens_h(
        self, score_o: float, perturbed_similarities: list[float]
    ) -> float:
        """Compute Cohen's h for binary scores."""

        def psi(score: float) -> float:
            return 2 * math.asin(math.sqrt(score))

        # Average perturbed similarities
        score_p = sum(perturbed_similarities) / len(perturbed_similarities)

        # Normalize Cohen's h by dividing by pi and take absolute value
        return abs((psi(score_p) - psi(score_o)) / math.pi)

    def compute_cohens_d(
        self, score_o: float, perturbed_similarities: list[float]
    ) -> float:
        """Compute effect size (Cohen's d for paired samples) for continuous scores."""
        differences = [score_o - s for s in perturbed_similarities]
        mean_diff = np.mean(differences)
        std_diff = np.std(differences, ddof=1)  # Sample standard deviation

        if std_diff == 0:
            return 0.0  # No variability in differences
        else:
            return mean_diff / std_diff

    def compute_similarity(self, text1: str, text2: str) -> float:
        """
        Computes similarity between two texts based on the specified metric.

        Args:
            text1 (str): The first text string.
            text2 (str): The second text string.

        Returns:
            float: Similarity score between 0 and 1.
        """
        if self.similarity_metric == "cosine":
            # Compute cosine similarity between sentence embeddings
            embeddings = self.embedding_model.encode([text1, text2])
            sim = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
            return sim
        elif self.similarity_metric == "bleu":
            # Compute BLEU score
            from nltk.translate.bleu_score import sentence_bleu

            reference = [text1.split()]
            candidate = text2.split()
            score = sentence_bleu(reference, candidate)
            return score
        elif self.similarity_metric == "rouge":
            # Compute ROUGE score
            from rouge import Rouge

            rouge = Rouge()
            scores = rouge.get_scores(text1, text2)
            # You can choose which ROUGE metric to use; here we use ROUGE-L F1 score
            return scores[0]["rouge-l"]["f"]
        else:
            raise ValueError(f"Unsupported similarity metric: {self.similarity_metric}")
