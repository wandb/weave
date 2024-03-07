import asyncio
import time
import inspect
import traceback
import typing
from typing import Any, Callable, Optional, Union
import numpy as np

import weave
from weave import op_def
from weave.flow import Object, Dataset, Model
from weave.flow.scorer import Scorer, get_scorer_attributes, auto_summarize
from weave.weaveflow import util

from rich.console import Console
from rich import print

console = Console()


class Evaluation(Object):
    dataset: Union[Dataset, list]
    scores: Optional[list[Union[Callable, op_def.OpDef, Scorer]]] = None
    preprocess_model_input: Optional[Callable] = None

    def model_post_init(self, __context) -> None:
        scorers = []
        for scorer in self.scores or []:
            if isinstance(scorer, Scorer):
                pass
            elif callable(scorer) and not isinstance(scorer, op_def.OpDef):
                scorer = weave.op()(scorer)
            else:
                raise ValueError(f"Invalid scorer: {scorer}")
            scorers.append(scorer)
        self.scores = scorers

        if isinstance(self.dataset, list):
            self.dataset = Dataset(rows=self.dataset)

        if self.name == None and self.dataset.name != None:
            self.name = self.dataset.name + "-evaluation"

    @weave.op()
    async def predict_and_score(
        self, example: dict, model: Union[Callable, Model]
    ) -> dict:
        if self.preprocess_model_input == None:
            model_input = example
        else:
            model_input = self.preprocess_model_input(example)

        if isinstance(model, Model):
            model_predict = model.get_infer_method()
        else:
            model_predict = model
        predict_signature = inspect.signature(model_predict)
        model_predict_arg_names = list(predict_signature.parameters.keys())
        if isinstance(model_input, dict):
            model_predict_args = {
                k: v for k, v in model_input.items() if k in model_predict_arg_names
            }
        else:
            if len(model_predict_arg_names) == 1:
                model_predict_args = {model_predict_arg_names[0]: model_input}
            else:
                raise ValueError(
                    f"{model_predict} expects arguments: {model_predict_arg_names}, provide a preprocess_model_input function that returns a dict with those keys."
                )

        try:
            prediction = await model_predict(**model_predict_args)
        except Exception as e:
            print("Prediction failed")
            traceback.print_exc()
            prediction = None

        scores = {}
        scorers = typing.cast(list[Union[op_def.OpDef, Scorer]], self.scores or [])
        for scorer in scorers:
            scorer_name, score_fn, _ = get_scorer_attributes(scorer)
            score_signature = inspect.signature(score_fn)
            score_arg_names = list(score_signature.parameters.keys())
            if isinstance(example, dict):
                score_args = {k: v for k, v in example.items() if k in score_arg_names}
            else:
                if len(score_arg_names) == 2:
                    score_args = {score_arg_names[0]: example}
                else:
                    raise ValueError(
                        f"{score_fn} expects arguments: {score_arg_names}, provide a preprocess_model_input function that returns a dict with those keys."
                    )
            score_args["prediction"] = prediction

            result = score_fn(**score_args)
            if inspect.iscoroutine(result):
                result = await result
            scores[scorer_name] = result

        return {
            "prediction": prediction,
            "scores": scores,
        }

    @weave.op()
    async def summarize(self, eval_table: weave.WeaveList) -> dict:
        summary = {}
        prediction_summary = auto_summarize(eval_table.column("prediction"))
        if prediction_summary:
            summary["prediction"] = prediction_summary
        scorers = self.scores or []
        for scorer in scorers:
            scorer_name, _, summarize_fn = get_scorer_attributes(scorer)
            scorer_scores = eval_table.column("scores").column(scorer_name)
            summary[scorer_name] = summarize_fn(scorer_scores)  # type: ignore
        return summary

    @weave.op()
    async def evaluate(self, model: Union[Callable, Model]) -> dict:
        eval_rows = []

        start_time = time.time()

        async def eval_example(example: dict) -> dict:
            try:
                eval_row = await self.predict_and_score(example, model)
            except Exception as e:
                print("Predict and score failed")
                traceback.print_exc()
                return {"prediction": None, "scores": {}}
            return eval_row

        n_complete = 0
        # with console.status("Evaluating...") as status:
        _rows = self.dataset.rows
        async for example, eval_row in util.async_foreach(_rows, eval_example, 30):
            n_complete += 1
            # prediction_errors += int(eval_row["prediction_error"])
            # score_errors += eval_row["score_errors"]
            duration = time.time() - start_time
            # status.update(
            #     f"Evaluating... {duration:.2f}s [{n_complete} / {len(self.dataset.rows)} complete] [{prediction_errors} prediction errors] [{score_errors} score errors]"
            # )
            if eval_row == None:
                eval_row = {"prediction": None, "scores": {}}
            if eval_row["scores"] == None:
                eval_row["scores"] = {}
            for scorer in self.scores or []:
                scorer_name, _, _ = get_scorer_attributes(scorer)
                if scorer_name not in eval_row["scores"]:
                    eval_row["scores"][scorer_name] = {}
            eval_rows.append(eval_row)

        eval_table: weave.WeaveList = weave.WeaveList(eval_rows)

        summary = await self.summarize(eval_table)

        print("Evaluation summary", summary)

        return summary


def evaluate(
    dataset: Union[Dataset, list],
    model: Union[Callable, Model],
    scores: Optional[list[Union[Callable, Scorer]]] = None,
    preprocess_model_input: Optional[Callable] = None,
) -> dict:
    eval = Evaluation(
        dataset=dataset, scores=scores, preprocess_model_input=preprocess_model_input
    )
    return asyncio.run(eval.evaluate(model))
