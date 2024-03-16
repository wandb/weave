import numpy as np
from typing import Union, Callable, Optional, Tuple, Any
from weave.flow import Object
from weave import op_def, WeaveList


class Scorer(Object):
    def score(self, target: Any, prediction: Any) -> Any:
        raise NotImplementedError

    def summarize(self, score_rows: WeaveList) -> Optional[dict]:
        return auto_summarize(score_rows)


def auto_summarize(data: WeaveList) -> Optional[dict]:
    """Automatically summarize a WeaveList of (potentially nested) dicts.

    Will compute min/p25/avg/p75/max for all numeric columns.
    Will compute count and fraction for all boolean columns.
    Other leaf column types will be ignored.
    Also computes none_count and none_fraction for numeric and boolean columns.
    If a column is all None, result will be None

    Returns:
      dict of summary stats, with structure matching input dict structure.
    """
    if data.is_number():
        valid_data = [x for x in data if x is not None]
        if not valid_data:
            return None
        # Just avg and none_fraction for now. The others make the UI
        # too noisy. And all of these can be derived.
        return {
            # "min": float(np.min(valid_data)),
            # "p25": float(np.percentile(valid_data, 25)),
            "mean": float(np.mean(valid_data)),
            # "p75": float(np.percentile(valid_data, 75)),
            # "max": float(np.max(valid_data)),
            # "none_fraction": (len(data) - len(valid_data)) / len(data),
        }
    elif data.is_boolean():
        valid_data = [x for x in data if x is not None]
        count_true = valid_data.count(True)
        return {
            "true_count": count_true,
            "true_fraction": count_true / len(valid_data) if valid_data else 0,
            # "none_fraction": (len(data) - len(valid_data)) / len(data),
        }
    elif data.is_dict():
        result = {}
        for col_name in data.column_names:
            nested_data = data.column(col_name)
            summary = auto_summarize(nested_data)
            if summary is not None:
                result[col_name] = summary
        if not result:
            return None
        return result
    return None


def get_scorer_attributes(
    scorer: Union[Callable, op_def.OpDef, Scorer]
) -> Tuple[str, Callable, Callable]:
    if isinstance(scorer, Scorer):
        scorer_name = scorer.name
        if scorer_name == None:
            scorer_name = scorer.__class__.__name__
        score_fn = scorer.score
        summarize_fn = scorer.summarize  # type: ignore
    else:
        if isinstance(scorer, op_def.OpDef):
            scorer_name = scorer.common_name
        else:
            scorer_name = scorer.__name__
        score_fn = scorer
        summarize_fn = auto_summarize  # type: ignore
    return (scorer_name, score_fn, summarize_fn)  # type: ignore


def p_r_f1(tp: int, fp: int, fn: int) -> Tuple[float, float, float]:
    # if any denom is zero, then zero. could use NaN instead...
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


class MulticlassF1Score(Scorer):
    class_names: list[str]

    def summarize(self, score_rows: WeaveList) -> Optional[dict]:
        # Compute f1, precision, recall
        result = {}
        for class_name in self.class_names:
            class_scores = [row.get(class_name) for row in score_rows]
            true_positives = sum(
                not score["negative"] and score["correct"] for score in class_scores
            )
            false_positives = sum(
                not score["negative"] and not score["correct"] for score in class_scores
            )
            false_negatives = sum(
                score["negative"] and not score["correct"] for score in class_scores
            )
            precision, recall, f1 = p_r_f1(
                true_positives, false_positives, false_negatives
            )
            result[class_name] = {"f1": f1, "precision": precision, "recall": recall}
        return result

    def score(self, target: dict, prediction: Optional[dict]) -> dict:
        result = {}
        for class_name in self.class_names:
            class_label = target.get(class_name)
            class_prediction = prediction.get(class_name) if prediction else None
            result[class_name] = {
                "correct": class_label == class_prediction,
                "negative": not class_prediction,
            }
        return result
