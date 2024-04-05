from collections import defaultdict
import numpy as np
from typing import List, Union, Callable, Optional, Tuple, Any
import weave
from weave.trace.isinstance import weave_isinstance
from weave.flow.obj import Object
from weave.trace.op import Op
from weave import WeaveList


class Scorer(Object):
    def score(self, target: Any, model_output: Any) -> Any:
        raise NotImplementedError

    @weave.op()
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
    if not isinstance(data, WeaveList):
        data = WeaveList(data)
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
    scorer: Union[Callable, Op, Scorer]
) -> Tuple[str, Callable, Callable]:
    if weave_isinstance(scorer, Scorer):
        scorer_name = scorer.name
        if scorer_name == None:
            scorer_name = scorer.__class__.__name__
        try:
            score_fn = scorer.score
            summarize_fn = scorer.summarize  # type: ignore
        except AttributeError:
            raise ValueError(
                f"Scorer {scorer_name} must implement score and summarize methods. Did you forget to wrap with @weave.op()?"
            )
    elif callable(scorer):
        if isinstance(scorer, Op):
            scorer_name = scorer.name
        else:
            scorer_name = scorer.__name__
        score_fn = scorer
        summarize_fn = auto_summarize  # type: ignore
    else:
        raise ValueError(f"Unknown scorer type: {scorer}")
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


class MultiTaskBinaryClassificationF1(Scorer):
    # a list specifying which average functions to apply to the F1 score (binary, macro, micro, weighted)
    class_names: list[str]

    @weave.op()
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

    @weave.op()
    def score(self, target: dict, model_output: Optional[dict]) -> dict:
        result = {}
        for class_name in self.class_names:
            class_label = target.get(class_name)
            class_model_output = model_output.get(class_name) if model_output else None
            result[class_name] = {
                "correct": class_label == class_model_output,
                "negative": not class_model_output,
            }
        return result

class MultiTaskAccuracy(Scorer):
    """A MultiTask version of accuracy where the input is a dict of different 
    outputs, with each task defined by a unique key.
    """
    @weave.op()
    def score(self, target: Union[str, dict], model_output: dict) -> dict:
        result = {}
        for task_key in target.keys():
            ground_truth_label = target.get(task_key)
            model_output_label = model_output.get(task_key) if model_output else None
            result[task_key] = {
                "correct": ground_truth_label == model_output_label,
            }
        return result

    @weave.op()
    def summarize(self, score_rows: WeaveList) -> Optional[dict]:
        result = {}
        for task_key in score_rows.keys():
            task_scores = [row.get(task_key) for row in score_rows]
            result[task_key] = sum(
               score["correct"] for score in task_scores
            ) / len(task_scores)
        return result
    

class MultiTaskF1Score(Scorer):
    # a list specifying which average functions to apply to the F1 score (binary, macro, micro, weighted)
    average: List[str]

    @weave.op()
    def score(self, target: dict, model_output: dict) -> dict:
        result = {}
        for task_key in target.keys():
            ground_truth_label = target.get(task_key)
            model_output_label = model_output.get(task_key) if model_output else None
            result[task_key] = {
                # force them to be strings as otherwise it becomes a reference of some sort and not so easy to compare
                "ground_truth_label": str(ground_truth_label), 
                "model_output_label": str(model_output_label)
            }
        return result

    @weave.op()
    def summarize(self, score_rows: WeaveList) -> Optional[dict]:
        from sklearn.metrics import f1_score
        from sklearn.preprocessing import OrdinalEncoder

        result = defaultdict(dict)
        for task_key in score_rows.keys():
            # use OrdinalEncoder rather than LabelEncoder as LLMs can generate labels not in the training set
            le = OrdinalEncoder(handle_unknown='use_encoded_value',
                                 unknown_value=-1)                        
            ground_truths = np.array([row[task_key]['ground_truth_label'] for row in score_rows]).reshape(-1, 1)
            model_outputs = np.array([row[task_key]['model_output_label'] for row in score_rows]).reshape(-1, 1)

            le.fit(ground_truths)
            y = le.transform(ground_truths)
            y_pred = le.transform(model_outputs)
            
            for avg in self.average:
                result[task_key][avg] = f1_score(y, y_pred, average=avg)
        return result

class Accuracy(Scorer):
    @weave.op()
    def score(self, target: str, model_output: dict) -> dict:
        return {
            "correct": target == model_output,
        }

    @weave.op()
    def summarize(self, score_rows: WeaveList) -> Optional[dict]:
       return sum(
            score["correct"] for score in score_rows
        ) / len(score_rows)
       
    

class F1Score(Scorer):
    average: List[str]

    @weave.op()
    def score(self, target: str, model_output: dict) -> dict:
        return {
            "ground_truth_label": str(target), 
            "model_output_label": str(model_output)
        }

    @weave.op()
    def summarize(self, score_rows: WeaveList) -> Optional[dict]:
        from sklearn.metrics import f1_score
        from sklearn.preprocessing import OrdinalEncoder
        # use OrdinalEncoder rather than LabelEncoder as LLMs can generate labels not in the training set
        le = OrdinalEncoder(handle_unknown='use_encoded_value',
                                unknown_value=-1)                        
        ground_truths = np.array([row['ground_truth_label'] for row in score_rows]).reshape(-1, 1)
        model_outputs = np.array([row['model_output_label'] for row in score_rows]).reshape(-1, 1)
        
        le.fit(ground_truths)
        y = le.transform(ground_truths)
        y_pred = le.transform(model_outputs)
        result = {}
        for avg in self.average:
            result[avg] = f1_score(y, y_pred, average=avg)
        return result
