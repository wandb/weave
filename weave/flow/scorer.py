from __future__ import annotations

from collections import defaultdict
from numbers import Number
from typing import Any, Callable, Optional, Sequence, Tuple, Union

import numpy as np
from pydantic import BaseModel

import weave
from weave import WeaveList
from weave.flow.obj import Object
from weave.legacy import box
from weave.trace.isinstance import weave_isinstance
from weave.trace.op import Op


class Scorer(Object):
    def score(self, target: Any, model_output: Any) -> Any:
        raise NotImplementedError

    @weave.op()
    def summarize(self, score_rows: WeaveList) -> Optional[dict]:
        return new_auto_summarize(score_rows)


def stderr(data: Sequence[Union[int, float]]) -> float:
    if len(data) > 1:
        sample_variance = np.var(data, ddof=1)
        return float(np.sqrt(sample_variance / len(data)))
    else:
        return 0


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
        count_true = list(valid_data).count(True)
        int_data = [int(x) for x in valid_data]
        sample_mean = np.mean(int_data) if int_data else 0
        # standard error
        # sample_variance = np.var(int_data) if int_data else 0
        # sample_error = np.sqrt(sample_variance / len(int_data)) if int_data else 0
        return {
            "true_count": count_true,
            "true_fraction": sample_mean,
            # "stderr": stderr(int_data),
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
    scorer: Union[Callable, Op, Scorer],
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
        summarize_fn = new_auto_summarize  # type: ignore
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
    class_names: list[str]

    @weave.op()
    def summarize(self, score_rows: WeaveList) -> Optional[dict]:
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

    @weave.op()
    def score(self, target: dict, model_output: Optional[dict]) -> dict:
        print(f"inside score... {target=}, {model_output=}")
        result = {}
        for class_name in self.class_names:
            class_label = target.get(class_name)
            class_model_output = model_output.get(class_name) if model_output else None
            result[class_name] = {
                "correct": class_label == class_model_output,
                "negative": not class_model_output,
            }
        return result


def new_auto_summarize(values: list) -> dict[str, Any] | None:
    if not values:
        return {}

    values = [x for x in values if x is not None]
    val = values[0]

    if isinstance(val, (bool, box.BoxedBool)):
        return {
            "true_count": (true_count := sum(1 for x in values if x)),
            "true_fraction": true_count / len(values),
        }

    elif isinstance(val, Number):
        return {"mean": np.mean(values).item()}

    elif isinstance(val, dict):
        result = {}
        for k in val:
            if (summary := new_auto_summarize([x[k] for x in values])) is not None:
                if k in summary:
                    result.update(summary)
                else:
                    result[k] = summary
        if not result:
            return None
        return result

    elif isinstance(val, BaseModel):
        return new_auto_summarize([x.model_dump() for x in values])

    return None


def transpose(rows: list[dict]) -> dict[str, list]:
    cols = defaultdict(list)
    for row in rows:
        for k, v in row.items():
            cols[k].append(v)
    return dict(cols)
