from dataclasses import dataclass
import weave
from typing import Any, Callable, Optional
import numpy as np
from weave.weaveflow import Dataset, Model
from weave import op_def
from weave.weaveflow import util
import time
import traceback

# from rich.console import Console

# console = Console()


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
        breakpoint()
        return {
            # "min": float(np.min(valid_data)),
            # "p25": float(np.percentile(valid_data, 25)),
            "avg": float(np.mean(valid_data)),
            # "p75": float(np.percentile(valid_data, 75)),
            # "max": float(np.max(valid_data)),
            "none_fraction": (len(data) - len(valid_data)) / len(data),
        }
    elif data.is_boolean():
        valid_data = [x for x in data if x is not None]
        count_true = valid_data.count(True)
        return {
            "fraction_true": count_true / len(valid_data) if valid_data else 0,
            "none_fraction": (len(data) - len(valid_data)) / len(data),
        }
    elif data.is_dict():
        result = {}
        for col_name in data.column_names:
            nested_data = data.column(col_name)
            print("NESTED", nested_data)
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

    def expected_output(self, example: dict) -> Any:
        return example["output"]

    @weave.op()
    async def predict_and_score(self, example: dict, model: Model) -> dict:
        model_input = self.example_to_model_input(example)
        # expected_output = self.expected_output(example)
        prediction = await model.predict(model_input)
        # try:
        #     prediction = await model.predict(model_input)
        # except Exception as e:
        #     print("Prediction failed")
        #     traceback.print_exc()
        #     return {"prediction": None, "scores": {}}
        scores = {}
        for scorer in self.scores:
            # TODO: if there are multiple of the same we need to distinguish
            scorer_name = scorer.name
            scores[scorer_name] = scorer(example, prediction)

        return {
            "prediction": prediction,
            "scores": scores,
        }

    @weave.op()
    async def summarize(self, eval_table: weave.WeaveList) -> dict:
        summary = {}
        for scorer in self.scores:
            scorer_name = scorer.name
            try:
                scorer_scores = eval_table.column("scores").column(scorer_name)
            except:
                breakpoint()
            summary[scorer_name] = auto_summarize(scorer_scores)
        return summary

    @weave.op()
    async def evaluate(self, model: Model) -> dict:
        eval_rows = []

        start_time = time.time()

        async def eval_example(example: dict) -> dict:
            eval_row = await self.predict_and_score(example, model)
            return eval_row

        # with console.status("Evaluating...") as status:
        async for example, eval_row in util.async_foreach(
            self.dataset.rows, eval_example, 30
        ):
            duration = time.time() - start_time
            # status.update(f"Evaluating... {duration:.2f}s")
            eval_rows.append(eval_row)

        eval_table: weave.WeaveList = weave.WeaveList(eval_rows)

        summary = await self.summarize(eval_table)

        return summary
