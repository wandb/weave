from typing import Any, Optional

import weave
from weave.flow.util import transpose


def p_r_f1(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    """
    Compute precision, recall, and F1 score based on true positives (tp), false positives (fp), and false negatives (fn).

    If any denominator is zero, the corresponding metric is set to zero.

    Args:
        tp (int): Number of true positives.
        fp (int): Number of false positives.
        fn (int): Number of false negatives.

    Returns:
        tuple[float, float, float]: A tuple containing (precision, recall, f1) scores.
    """
    precision: float = 0
    if tp or fp:
        precision = tp / (tp + fp)
    recall: float = 0
    if tp or fn:
        recall = tp / (tp + fn)
    f1: float = 0
    if precision or recall:
        f1 = 2 * (precision * recall) / (precision + recall)
    return precision, recall, f1


class MultiTaskBinaryClassificationF1(weave.Scorer):
    """
    Multi-task binary classification scorer that computes precision, recall, and F1 score for each target class based on
    the model output and ground truth labels.

    Attributes:
        class_names (list[str]): The list of target class names.

    Methods:
        score(target: dict, model_output: Optional[dict]) -> dict:
            Compares the target class labels with the model outputs to indicate correctness for each class.
            Uses the "model_output" key for backwards compatibility.

        summarize(score_rows: list) -> Optional[dict]:
            Aggregates multiple scoring results to compute the precision, recall, and F1 score for each class.
    """

    class_names: list[str]

    @weave.op()
    def summarize(self, score_rows: list) -> Optional[dict]:
        """
        Aggregate scoring results and compute precision, recall, and F1 score for each class.

        Args:
            score_rows (list[dict]): A list of score dictionaries for each sample where each dictionary
            contains entries for each class with keys "correct" and "negative".

        Returns:
            Optional[dict]: A dictionary mapping each class name to its metrics,
            including keys "precision", "recall", and "f1".
        """
        result = {}
        cols = transpose(score_rows)

        for class_name in self.class_names:
            col = cols[class_name]
            tp = sum(r["correct"] and not r["negative"] for r in col)
            fp = sum(not r["correct"] and not r["negative"] for r in col)
            fn = sum(not r["correct"] and r["negative"] for r in col)
            precision, recall, f1 = p_r_f1(tp, fp, fn)
            result[class_name] = {"f1": f1, "precision": precision, "recall": recall}

        return result

    # NOTE: This is an old-style scorer that uses `model_output` instead of `output` for
    # backwards compatibility.  In the future, this behavior may change to use the newer `output` key.
    # You can still pass a `column_map` to map to the new `output` key if preferred.
    @weave.op()
    def score(
        self, *, target: dict, model_output: Optional[dict], **kwargs: Any
    ) -> dict:
        """
        Compare target labels with model outputs to determine correctness for each class.

        Args:
            target (dict): A dictionary mapping each class name to the ground truth label.
            model_output (Optional[dict]): A dictionary mapping each class name to the model's output.
                If None, outputs are treated as false.

        Returns:
            dict: A dictionary mapping each class name to a dictionary containing:
                - "correct": True if the target label matches the model output.
                - "negative": True if the model output is missing or false.
        Note:
            This method uses the `model_output` key for backwards compatibility.
        """
        result = {}
        for class_name in self.class_names:
            class_label = target.get(class_name)
            class_output = model_output.get(class_name) if model_output else None
            result[class_name] = {
                "correct": class_label == class_output,
                "negative": not class_output,
            }
        return result
