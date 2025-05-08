import asyncio
import logging
import traceback
from datetime import datetime
from itertools import chain, repeat
from typing import Any, Callable, Literal, Optional, Union

from pydantic import PrivateAttr
from rich import print
from rich.console import Console
from typing_extensions import Self

import weave
from weave.flow import util
from weave.flow.casting import DatasetLike, ScorerLike
from weave.flow.dataset import Dataset
from weave.flow.model import (
    ApplyModelError,
    Model,
    PreprocessModelInput,
    apply_model_async,
)
from weave.flow.obj import Object
from weave.flow.scorer import (
    Scorer,
    _has_oldstyle_scorers,
    auto_summarize,
    get_scorer_attributes,
)
from weave.flow.util import make_memorable_name, transpose
from weave.trace.env import get_weave_parallelism
from weave.trace.objectify import register_object
from weave.trace.op import CallDisplayNameFunc, Op, OpCallError, as_op, is_op
from weave.trace.vals import WeaveObject
from weave.trace.weave_client import Call, get_ref

console = Console()
logger = logging.getLogger(__name__)

INVALID_MODEL_ERROR = (
    "`Evaluation.evaluate` requires a `Model` or `Op` instance as the `model` argument. "
    + "If you are using a function, wrap it with `weave.op` to create an `Op` instance."
)


def default_evaluation_display_name(call: Call) -> str:
    date = datetime.now().strftime("%Y-%m-%d")
    unique_name = make_memorable_name()
    return f"eval-{date}-{unique_name}"


class EvaluationResults(Object):
    rows: weave.Table


@register_object
class Evaluation(Object):
    """
    Sets up an evaluation which includes a set of scorers and a dataset.

    Calling evaluation.evaluate(model) will pass in rows from a dataset into a model matching
        the names of the columns of the dataset to the argument names in model.predict.

    Then it will call all of the scorers and save the results in weave.

    If you want to preprocess the rows from the dataset you can pass in a function
    to preprocess_model_input.

    Examples:

    ```python
    # Collect your examples
    examples = [
        {"question": "What is the capital of France?", "expected": "Paris"},
        {"question": "Who wrote 'To Kill a Mockingbird'?", "expected": "Harper Lee"},
        {"question": "What is the square root of 64?", "expected": "8"},
    ]

    # Define any custom scoring function
    @weave.op()
    def match_score1(expected: str, model_output: dict) -> dict:
        # Here is where you'd define the logic to score the model output
        return {'match': expected == model_output['generated_text']}

    @weave.op()
    def function_to_evaluate(question: str):
        # here's where you would add your LLM call and return the output
        return  {'generated_text': 'Paris'}

    # Score your examples using scoring functions
    evaluation = Evaluation(
        dataset=examples, scorers=[match_score1]
    )

    # Start tracking the evaluation
    weave.init('intro-example')
    # Run the evaluation
    asyncio.run(evaluation.evaluate(function_to_evaluate))
    ```
    """

    dataset: DatasetLike
    scorers: Optional[list[ScorerLike]] = None
    preprocess_model_input: Optional[PreprocessModelInput] = None
    trials: int = 1

    # Custom evaluation name for display in the UI.  This is the same API as passing a
    # custom `call_display_name` to `weave.op` (see that for more details).
    evaluation_name: Optional[Union[str, CallDisplayNameFunc]] = None

    # internal attr to track whether to use the new `output` or old `model_output` key for outputs
    _output_key: Literal["output", "model_output"] = PrivateAttr("output")

    @classmethod
    def from_obj(cls, obj: WeaveObject) -> Self:
        field_values = {}
        for field_name in cls.model_fields:
            if hasattr(obj, field_name):
                field_values[field_name] = getattr(obj, field_name)

        return cls(**field_values)

    def model_post_init(self, __context: Any) -> None:
        # Determine output key based on scorer types
        scorers = self.scorers or []
        if _has_oldstyle_scorers(scorers):
            self._output_key = "model_output"
            util.warn_once(
                logger,
                "Using 'model_output' key for compatibility with older scorers. Please update scorers to use 'output' parameter.",
            )

        if self.evaluation_name:
            eval_op = as_op(self.evaluate)
            eval_op.call_display_name = self.evaluation_name

        if self.name is None and self.dataset.name is not None:
            self.name = self.dataset.name + "-evaluation"  # type: ignore

    @weave.op
    async def predict_and_score(self, model: Union[Op, Model], example: dict) -> dict:
        apply_model_result = await apply_model_async(
            model, example, self.preprocess_model_input
        )

        if isinstance(apply_model_result, ApplyModelError):
            return {
                self._output_key: None,
                "scores": {},
                "model_latency": apply_model_result.model_latency,
            }

        model_output = apply_model_result.model_output
        model_call = apply_model_result.model_call
        model_latency = apply_model_result.model_latency

        scores = {}
        if scorers := self.scorers:
            for scorer in scorers:
                apply_scorer_result = await model_call.apply_scorer(scorer, example)
                result = apply_scorer_result.result
                scorer_attributes = get_scorer_attributes(scorer)
                scorer_name = scorer_attributes.scorer_name
                scores[scorer_name] = result

        return {
            self._output_key: model_output,
            "scores": scores,
            "model_latency": model_latency,
        }

    @weave.op()
    async def summarize(self, eval_table: EvaluationResults) -> dict:
        eval_table_rows = list(eval_table.rows)
        cols = transpose(eval_table_rows)
        summary = {}

        for name, vals in cols.items():
            if name == "scores":
                if scorers := self.scorers:
                    for scorer in scorers:
                        scorer_attributes = get_scorer_attributes(scorer)
                        scorer_name = scorer_attributes.scorer_name
                        summarize_fn = scorer_attributes.summarize_fn
                        scorer_stats = transpose(vals)
                        score_table = scorer_stats[scorer_name]
                        scored = summarize_fn(score_table)
                        summary[scorer_name] = scored
            else:
                model_output_summary = auto_summarize(vals)
                if model_output_summary:
                    summary[name] = model_output_summary
        return summary

    async def get_eval_results(self, model: Union[Op, Model]) -> EvaluationResults:
        if not is_valid_model(model):
            raise ValueError(INVALID_MODEL_ERROR)
        eval_rows = []

        async def eval_example(example: dict) -> dict:
            try:
                eval_row = await self.predict_and_score(model, example)
            except OpCallError as e:
                raise e
            except Exception:
                print("Predict and score failed")
                traceback.print_exc()
                return {self._output_key: None, "scores": {}}
            return eval_row

        n_complete = 0
        dataset = self.dataset
        _rows = dataset.rows
        num_rows = len(_rows) * self.trials

        trial_rows = chain.from_iterable(repeat(_rows, self.trials))
        async for example, eval_row in util.async_foreach(
            trial_rows, eval_example, get_weave_parallelism()
        ):
            n_complete += 1
            print(f"Evaluated {n_complete} of {num_rows} examples")
            if eval_row is None:
                eval_row = {self._output_key: None, "scores": {}}
            else:
                eval_row["scores"] = eval_row.get("scores", {})
            if self.scorers:
                for scorer in self.scorers:
                    scorer_attributes = get_scorer_attributes(scorer)
                    scorer_name = scorer_attributes.scorer_name
                    if scorer_name not in eval_row["scores"]:
                        eval_row["scores"][scorer_name] = {}
            eval_rows.append(eval_row)
        return EvaluationResults(rows=weave.Table(eval_rows))

    @weave.op(call_display_name=default_evaluation_display_name)
    async def evaluate(self, model: Union[Op, Model]) -> dict:
        eval_results = await self.get_eval_results(model)
        summary = await self.summarize(eval_results)

        print("Evaluation summary", summary)

        return summary


def evaluate(
    dataset: Union[Dataset, list],
    model: Union[Op, Model],
    scorers: Optional[list[Union[Callable, Scorer]]] = None,
    preprocess_model_input: Optional[PreprocessModelInput] = None,
) -> dict:
    eval = Evaluation(
        dataset=dataset, scorers=scorers, preprocess_model_input=preprocess_model_input
    )
    return asyncio.run(eval.evaluate(model))


def is_valid_model(model: Any) -> bool:
    return (
        # Model instances are supported
        isinstance(model, Model)
        # Ops are supported
        or is_op(model)
        # Saved Models (Objects with predict) are supported
        or (
            get_ref(model) is not None
            and isinstance(model, WeaveObject)
            and hasattr(model, "predict")
            and is_op(model.predict)
        )
    )
