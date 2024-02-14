from dataclasses import dataclass
import weave
from typing import Any, Callable, Optional
import numpy as np
from weave.weaveflow import Dataset, Model
from weave import op_def
from weave.weaveflow import util
import time
import inspect
import traceback

from rich.console import Console
from rich import print

console = Console()


def auto_summarize(data: weave.WeaveList) -> Optional[dict]:
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


@weave.type()
class Evaluation:
    dataset: Dataset
    scores: list[op_def.OpDef]

    # TODO: can't use regular callables here, Weave doesn't know about them.
    # example_to_model_input: Callable = lambda x: x["input"]
    example_to_model_input: op_def.OpDef

    @weave.op()
    async def predict_and_score(self, example: dict, model: Model) -> dict:
        model_input = self.example_to_model_input(example)
        try:
            prediction = await model.predict(model_input)
        except Exception as e:
            print("Prediction failed")
            traceback.print_exc()
            return {
                "prediction": None,
                "prediction_error": True,
                "scores": {},
                "score_errors": 0,
            }
        scores = {}
        score_errors = 0
        for scorer in self.scores:
            # TODO: if there are multiple of the same we need to distinguish
            scorer_name = scorer.common_name
            try:
                result = scorer(example, prediction)
                if inspect.iscoroutine(result):
                    result = await result
            except Exception as e:
                print(f"Score {scorer_name} exception")
                traceback.print_exc()
                result = None
                score_errors += 1
            scores[scorer_name] = result

        return {
            "prediction": prediction,
            "prediction_error": False,
            "scores": scores,
            "score_errors": score_errors,
        }

    @weave.op()
    async def summarize(self, eval_table: weave.WeaveList) -> dict:
        summary = {}
        prediction_summary = auto_summarize(eval_table.column("prediction"))
        if prediction_summary:
            summary["prediction"] = prediction_summary
        for scorer in self.scores:
            scorer_name = scorer.common_name
            scorer_scores = eval_table.column("scores").column(scorer_name)
            summary[scorer_name] = auto_summarize(scorer_scores)  # type: ignore
        return summary

    @weave.op()
    async def evaluate(self, model: Model) -> dict:
        eval_rows = []

        start_time = time.time()

        async def eval_example(example: dict) -> dict:
            eval_row = await self.predict_and_score(example, model)
            return eval_row

        prediction_errors = 0
        score_errors = 0
        n_complete = 0
        with console.status("Evaluating...") as status:
            _rows = self.dataset.rows
            async for example, eval_row in util.async_foreach(_rows, eval_example, 30):
                n_complete += 1
                prediction_errors += int(eval_row["prediction_error"])
                score_errors += eval_row["score_errors"]
                duration = time.time() - start_time
                status.update(
                    f"Evaluating... {duration:.2f}s [{n_complete} / {len(self.dataset.rows)} complete] [{prediction_errors} prediction errors] [{score_errors} score errors]"
                )
                eval_rows.append(eval_row)

        with console.status("Summarizing...") as status:
            eval_table: weave.WeaveList = weave.WeaveList(eval_rows)

            summary = await self.summarize(eval_table)

        return summary
