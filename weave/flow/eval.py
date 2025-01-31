import asyncio
import logging
import traceback
from datetime import datetime
from typing import Any, Callable, Literal, Optional, TypedDict, Union

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
from weave.flow.util import make_memorable_name
from weave.scorers import (
    Scorer,
    _has_oldstyle_scorers,
    auto_summarize,
    get_scorer_attributes,
    transpose,
)
from weave.trace.env import get_weave_parallelism
from weave.trace.errors import OpCallError
from weave.trace.objectify import register_object
from weave.trace.op import CallDisplayNameFunc, Op, as_op, is_op
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


class PredictionResult(TypedDict):
    output_key: str
    model_call: Optional[Call]
    model_latency: float


class ScoreResult(TypedDict):
    scores: dict[str, Any]


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
        return cls(
            name=obj.name,
            description=obj.description,
            ref=obj.ref,
            dataset=obj.dataset,
            scorers=obj.scorers,
            preprocess_model_input=obj.preprocess_model_input,
            trials=obj.trials,
            evaluation_name=obj.evaluation_name,
        )

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

    # @weave.op
    async def predict_one(
        self, model: Union[Op, Model], example: dict
    ) -> PredictionResult:
        apply_model_result = await apply_model_async(
            model, example, self.preprocess_model_input
        )
        if isinstance(apply_model_result, ApplyModelError):
            model_call = None
        else:
            model_call = apply_model_result.model_call

        return PredictionResult(
            output_key=self._output_key,
            model_call=model_call,
            model_latency=apply_model_result.model_latency,
        )

    # @weave.op
    async def score_one(
        self, example: dict, prediction: PredictionResult
    ) -> ScoreResult:
        scores = {}
        model_call = prediction["model_call"]

        if not self.scorers:
            return scores

        for scorer in self.scorers:
            attrs = get_scorer_attributes(scorer)
            name = attrs.scorer_name

            res = None
            if model_call:
                apply_scorer_result = await model_call.apply_scorer(scorer, example)
                res = apply_scorer_result.result

            scores[name] = res
        return scores

    @weave.op()
    async def predict_and_score(self, model: Union[Op, Model], example: dict) -> dict:
        predict_res = await self.predict_one(model, example)
        score_res = await self.score_one(example, predict_res)

        return {
            self._output_key: predict_res["model_call"].output,
            "scores": score_res,
            "model_latency": predict_res["model_latency"],
        }

    @weave.op()
    async def summarize(self, eval_table: EvaluationResults) -> dict:
        cols = transpose(eval_table.rows)
        summary = {}

        for name, vals in cols.items():
            if name == "scores" and self.scorers:
                scorer_stats = transpose(vals)
                for scorer in self.scorers:
                    attrs = get_scorer_attributes(scorer)
                    score_table = scorer_stats[attrs.scorer_name]
                    summary[attrs.scorer_name] = attrs.summarize_fn(score_table)

            elif model_output_summary := auto_summarize(vals):
                summary[name] = model_output_summary

        return summary

    async def get_eval_results(self, model: Union[Op, Model]) -> EvaluationResults:
        if not is_valid_model(model):
            raise ValueError(INVALID_MODEL_ERROR)

        async def eval_example(example: dict) -> dict:
            try:
                return await self.predict_and_score(model, example)
            except OpCallError:
                raise
            except Exception:
                print("Predict and score failed")
                traceback.print_exc()
                return {self._output_key: None, "scores": {}}

        trial_rows = list(self.dataset) * self.trials
        eval_rows = []

        async for _, eval_row in util.async_foreach(
            trial_rows, eval_example, get_weave_parallelism()
        ):
            print(f"Evaluated {len(eval_rows) + 1} of {len(trial_rows)} examples")
            if eval_row is None:
                eval_row = {self._output_key: None, "scores": {}}
            eval_row.setdefault("scores", {})

            if not self.scorers:
                continue
            for scorer in self.scorers:
                attrs = get_scorer_attributes(scorer)
                name = attrs.scorer_name
                eval_row["scores"].setdefault(name, {})

            eval_rows.append(eval_row)

        return EvaluationResults(rows=weave.Table(eval_rows))

    @weave.op(call_display_name=default_evaluation_display_name)
    async def evaluate(self, model: Union[Op, Model]) -> dict:
        # The need for this pattern is quite unfortunate and highlights a gap in our
        # data model. As a user, I just want to pass a list of data `eval_rows` to
        # summarize. Under the hood, Weave should choose the appropriate storage
        # format (in this case `Table`) and serialize it that way. Right now, it is
        # just a huge list of dicts. The fact that "as a user" I need to construct
        # `weave.Table` at all is a leaky abstraction. Moreover, the need to
        # construct `EvaluationResults` just so that tracing and the UI works is
        # also bad. In the near-term, this will at least solve the problem of
        # breaking summarization with big datasets, but this is not the correct
        # long-term solution.
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
