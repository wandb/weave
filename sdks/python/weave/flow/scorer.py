from collections import defaultdict
from numbers import Number
from typing import Any, Callable, Optional, Sequence, Tuple, Union

import numpy as np
from pydantic import BaseModel

import weave
from weave.flow.obj import Object
from weave.trace.isinstance import weave_isinstance
from weave.trace.op import Op, as_op, is_op


class Scorer(Object):
    def score(self, target: Any, model_output: Any) -> Any:
        raise NotImplementedError

    @weave.op()
    def summarize(self, score_rows: list) -> Optional[dict]:
        return auto_summarize(score_rows)


def stderr(data: Sequence[Union[int, float]]) -> float:
    if len(data) > 1:
        sample_variance = np.var(data, ddof=1)
        return float(np.sqrt(sample_variance / len(data)))
    else:
        return 0


def auto_summarize(data: list) -> Optional[dict[str, Any]]:
    """Automatically summarize a list of (potentially nested) dicts.

    Computes:
        - avg for numeric cols
        - count and fraction for boolean cols
        - other col types are ignored

    If col is all None, result is None

    Returns:
      dict of summary stats, with structure matching input dict structure.
    """
    if not data:
        return {}
    data = [x for x in data if x is not None]

    if not data:
        return None

    val = data[0]

    if isinstance(val, bool):
        return {
            "true_count": (true_count := sum(1 for x in data if x)),
            "true_fraction": true_count / len(data),
        }
    elif isinstance(val, Number):
        return {"mean": np.mean(data).item()}
    elif isinstance(val, dict):
        result = {}
        all_keys = set().union(*[x.keys() for x in data if isinstance(x, dict)])
        for k in all_keys:
            if (
                summary := auto_summarize(
                    [x.get(k) for x in data if isinstance(x, dict)]
                )
            ) is not None:
                if k in summary:
                    result.update(summary)
                else:
                    result[k] = summary
        if not result:
            return None
        return result
    elif isinstance(val, BaseModel):
        return auto_summarize([x.model_dump() for x in data])
    return None


def get_scorer_attributes(
    scorer: Union[Callable, Op, Scorer],
) -> Tuple[str, Callable, Callable]:
    if weave_isinstance(scorer, Scorer):
        scorer_name = scorer.name
        if scorer_name is None:
            scorer_name = scorer.__class__.__name__
        try:
            score_fn = scorer.score
            summarize_fn = scorer.summarize  # type: ignore
        except AttributeError:
            raise ValueError(
                f"Scorer {scorer_name} must implement score and summarize methods. Did you forget to wrap with @weave.op()?"
            )
    elif callable(scorer):
        if is_op(scorer):
            scorer = as_op(scorer)
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
    class_names: list[str]

    @weave.op()
    def summarize(self, score_rows: list) -> Optional[dict]:
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
        result = {}
        for class_name in self.class_names:
            class_label = target.get(class_name)
            class_model_output = model_output.get(class_name) if model_output else None
            result[class_name] = {
                "correct": class_label == class_model_output,
                "negative": not class_model_output,
            }
        return result


def transpose(rows: list[dict]) -> dict[str, list]:
    cols = defaultdict(list)
    for row in rows:
        for k, v in row.items():
            cols[k].append(v)
    return dict(cols)
