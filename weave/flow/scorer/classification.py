from collections import defaultdict
from typing import Optional, Tuple

import weave
from weave.flow.scorer.base_scorer import Scorer


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
