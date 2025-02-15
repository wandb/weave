from typing import Any, Literal, Optional

from pydantic import Field

import weave


class AccuracyScorer(weave.Scorer):
    """Accuracy scorer supporting binary, multiclass, and multilabel tasks."""

    task: Literal["binary", "multiclass", "multilabel"]
    num_classes: Optional[int] = Field(
        default=None,
        description="Number of classes for multiclass or multilabel tasks",
    )
    threshold: float = Field(
        default=0.5,
        description="Threshold to binarize predictions for binary or multilabel tasks",
    )
    average: Optional[Literal["micro", "macro", "weighted", "none"]] = Field(
        default="micro",
        description="Averaging method for multiclass and multilabel tasks",
    )

    @weave.op
    def score(self, output: Any, ground_truth: Any) -> dict[str, Any]:
        """
        Compare a single prediction to the ground truth and return a binary correctness score.

        Args:
            output (Any): Model's prediction.
            ground_truth (Any): Ground truth labels.

        Returns:
            float: 1.0 if the prediction matches the ground truth, otherwise 0.0.
        """
        if self.task == "binary":
            output = self._apply_threshold(output)
            result = 1.0 if output == ground_truth else 0.0

        elif self.task == "multiclass":
            if not isinstance(output, int):
                raise ValueError(
                    "For multiclass tasks, predictions must be an integer representing the class."
                )
            result = 1.0 if output == ground_truth else 0.0

        elif self.task == "multilabel":
            output = self._apply_threshold(output)
            if isinstance(output, list) and isinstance(ground_truth, list):
                result = 1.0 if set(output) == set(ground_truth) else 0.0
            raise ValueError(
                "For multilabel tasks, predictions and ground truth must be lists of labels."
            )
        else:
            raise ValueError(f"Unsupported task type: {self.task}")

        return {
            "score": result,
            "output": output,
            "ground_truth": ground_truth,
        }

    @weave.op
    def summarize(self, score_rows: list[dict]) -> Optional[dict]:
        """
        Summarize the accuracy scores for a batch of predictions.

        Args:
            score_rows (list[dict]): A list of dictionaries with `score`, `output`, and `ground_truth`.

        Returns:
            Optional[dict]: Summary statistics including accuracy and class-wise details for multiclass and multilabel tasks.
        """
        print(score_rows)
        scores = [row.get("score", 0) for row in score_rows]
        outputs = [row.get("output") for row in score_rows]
        ground_truths = [row.get("ground_truth") for row in score_rows]

        if not scores:
            return None

        if self.task == "binary":
            accuracy = sum(scores) / len(scores)
            return {"accuracy": accuracy}

        elif self.task == "multiclass":
            return self._summarize_multiclass(scores, outputs, ground_truths)

        elif self.task == "multilabel":
            return self._summarize_multilabel(scores, outputs, ground_truths)

        return None

    def _summarize_multiclass(
        self, scores: list[float], outputs: list[Any], ground_truths: list[Any]
    ) -> dict[str, Any]:
        """
        Summarize accuracy for multiclass tasks.

        Args:
            scores (list[float]): List of scores.
            outputs (list[Any]): Predictions from the model.
            ground_truths (list[Any]): Ground truth labels.

        Returns:
            dict: Summary of multiclass accuracy.
        """
        if not self.num_classes:
            raise ValueError(
                "num_classes must be provided for multiclass summarization."
            )

        per_class_correct = [0] * self.num_classes
        per_class_total = [0] * self.num_classes

        for pred, gt in zip(outputs, ground_truths):
            per_class_total[gt] += 1
            if pred == gt:
                per_class_correct[gt] += 1

        per_class_accuracy = [
            correct / total if total > 0 else 0.0
            for correct, total in zip(per_class_correct, per_class_total)
        ]

        if self.average == "micro":
            accuracy = sum(scores) / len(scores)
        elif self.average == "macro":
            accuracy = sum(per_class_accuracy) / self.num_classes
        elif self.average == "weighted":
            weights = [total / sum(per_class_total) for total in per_class_total]
            accuracy = sum(
                acc * weight for acc, weight in zip(per_class_accuracy, weights)
            )
        else:
            raise ValueError(f"Unsupported average type: {self.average}")

        return {"accuracy": accuracy, "per_class_accuracy": per_class_accuracy}

    def _summarize_multilabel(
        self, scores: list[float], outputs: list[Any], ground_truths: list[Any]
    ) -> dict:
        """
        Summarize accuracy for multilabel tasks.

        Args:
            scores (list[float]): List of scores.
            outputs (list[Any]): Predictions from the model.
            ground_truths (list[Any]): Ground truth labels.

        Returns:
            dict: Summary of multilabel accuracy.
        """
        if self.average == "micro":
            return {"accuracy": sum(scores) / len(scores)}
        elif self.average == "macro":
            per_label_accuracies = []
            num_labels = len(outputs[0]) if outputs else 0

            for label_idx in range(num_labels):
                correct = sum(
                    1
                    for output, gt in zip(outputs, ground_truths)
                    if output[label_idx] == gt[label_idx]
                )
                per_label_accuracies.append(correct / len(outputs))

            return {"accuracy": sum(per_label_accuracies) / num_labels}
        else:
            raise ValueError(f"Unsupported average type for multilabel: {self.average}")

    def _apply_threshold(self, output: Any) -> Any:
        """
        Apply a threshold to binarize predictions.

        Args:
            output (Any): Model's prediction.

        Returns:
            Any: Thresholded output.
        """
        if isinstance(output, (float, list)):
            if isinstance(output, list):
                return [int(o > self.threshold) for o in output]
            return int(output > self.threshold)
        return output
