from __future__ import annotations

import asyncio
import inspect
import logging
import traceback
from collections.abc import AsyncGenerator, Generator, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import (
    Annotated,
    Any,
    Callable,
    Generic,
    Literal,
    NotRequired,
    Optional,
    Protocol,
    TypedDict,
    TypeVar,
    Union,
    cast,
)

from pydantic import BaseModel, Field, PrivateAttr, model_validator
from rich import print
from typing_extensions import Self, runtime_checkable

import weave
from weave.flow import util
from weave.flow.dataset import Dataset
from weave.flow.model import (
    ApplyModelError,
    Model,
    PreprocessModelInput,
    apply_model_async,
)
from weave.flow.obj import Object
from weave.flow.util import get_callable_name, make_memorable_name
from weave.scorers import (
    Scorer,
    _has_oldstyle_scorers,
    _validate_scorer_signature,
    auto_summarize,
    get_scorer_attributes,
    transpose,
)
from weave.trace.env import get_weave_parallelism
from weave.trace.errors import OpCallError
from weave.trace.isinstance import weave_isinstance
from weave.trace.objectify import register_object
from weave.trace.op import CallDisplayNameFunc, Op, as_op, is_op
from weave.trace.vals import WeaveObject
from weave.trace.weave_client import Call, get_ref

logger = logging.getLogger(__name__)


def default_evaluation_display_name(call: Call) -> str:
    date = datetime.now().strftime("%Y-%m-%d")
    unique_name = make_memorable_name()
    return f"eval-{date}-{unique_name}"


# TODO: Should this just be a TableLike?
class EvaluationResults(Object):
    rows: weave.Table


DatasetLike = Union[Dataset, list[dict]]
ScorerLike = Union[Callable, Op, Scorer]
ModelLike = Union[Op, Model]


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

    @model_validator(mode="after")
    def _update_display_name(self) -> Evaluation:
        if self.evaluation_name:
            # Treat user-specified `evaluation_name` as the name for `Evaluation.evaluate`
            eval_op = as_op(self.evaluate)
            eval_op.call_display_name = self.evaluation_name
        return self

    def model_post_init(self, __context: Any) -> None:
        scorers: list[Union[Op, Scorer]] = []
        for scorer in self.scorers or []:
            if isinstance(scorer, Scorer):
                pass
            elif isinstance(scorer, type):
                raise TypeError(
                    f"Scorer {scorer.__name__} must be an instance, not a class. Did you forget to instantiate?"
                )
            elif callable(scorer) and not is_op(scorer):
                scorer = weave.op(scorer)
            elif is_op(scorer):
                scorer = as_op(scorer)
            else:
                raise ValueError(f"Invalid scorer: {scorer}")

            _validate_scorer_signature(scorer)

            scorers.append(scorer)

        # Determine output key based on scorer types
        if _has_oldstyle_scorers(scorers):
            self._output_key = "model_output"
            util.warn_once(
                logger,
                "Using 'model_output' key for compatibility with older scorers. Please update scorers to use 'output' parameter.",
            )

        # I don't understand why we need a type ignore here, error:
        # Incompatible types in assignment (expression has type "list[Op | Scorer]", variable has type "list[Callable[..., Any] | Op | Scorer] | None")
        # This seems to be a bug in the type checker as the assignment is a valid subset of the type.
        self.scorers = scorers  # type: ignore

        if isinstance(self.dataset, list):
            self.dataset = Dataset(rows=self.dataset)

        if self.name is None and self.dataset.name is not None:
            self.name = self.dataset.name + "-evaluation"  # type: ignore

    # _post_init_dataset and _post_init_scorers are a more tightly typed property.
    # This is because the initialization code can accept lists and callables respectively,
    # but after initialization, they are more tightly typed to the respective weave objects.
    # Using these reduces casting below and allows us to have less logical branches
    @property
    def _post_init_dataset(self) -> Dataset:
        if not weave_isinstance(self.dataset, Dataset):
            raise TypeError(
                f"Expected self.dataset to be converted to a Dataset in `model_post_init`. Found {str(type(self.dataset))}"
            )
        return self.dataset

    @property
    def _post_init_scorers(self) -> list[Union[Op, Scorer]]:
        if not isinstance(self.scorers, list):
            raise TypeError(
                f"Expected self.scorers to be a list in `model_post_init`. Found {str(type(self.scorers))}"
            )
        for scorer in self.scorers:
            if not weave_isinstance(scorer, (Op, Scorer)) and not is_op(scorer):
                raise TypeError(
                    f"Expected all elements in self.scorers to be an instance of Op or Scorer in `model_post_init`. Found {str(type(scorer))}"
                )
        return cast(list[Union[Op, Scorer]], self.scorers)

    @weave.op
    async def predict(self, model: Union[Op, Model], example: dict) -> dict:
        res = await apply_model_async(model, example, self.preprocess_model_input)

        if isinstance(res, ApplyModelError):
            return {
                self._output_key: None,
                "model_latency": res.model_latency,
            }

        return {
            self._output_key: res.model_output,
            "model_call": res.model_call,
            "model_latency": res.model_latency,
        }

    @weave.op
    async def score(self, prediction: dict, example: dict) -> dict:
        scores = {}
        scorers = self._post_init_scorers
        model_call = prediction["model_call"]

        for scorer in scorers:
            apply_scorer_result = await model_call.apply_scorer(scorer, example)
            result = apply_scorer_result.result
            scorer_attributes = get_scorer_attributes(scorer)
            scorer_name = scorer_attributes.scorer_name
            scores[scorer_name] = result

        return {
            self._output_key: prediction[self._output_key],
            "scores": scores,
            "model_latency": prediction["model_latency"],
        }

    @weave.op()
    async def predict_and_score(self, model: Union[Op, Model], example: dict) -> dict:
        prediction = await self.predict(model, example)
        if prediction[self._output_key] is None:
            return {
                self._output_key: None,
                "scores": {},
                "model_latency": prediction["model_latency"],
            }
        return await self.score(prediction, example)

    @weave.op
    async def summarize(self, eval_table: EvaluationResults) -> dict:
        cols = transpose(list(eval_table.rows))
        summary = {}

        if "scores" in cols:
            score_data = transpose(cols["scores"])
            for scorer in self._post_init_scorers:
                attrs = get_scorer_attributes(scorer)
                score_table = score_data[attrs.scorer_name]
                summary[attrs.scorer_name] = attrs.summarize_fn(score_table)

        for name, vals in cols.items():
            if name == "scores":
                continue
            if summary_result := auto_summarize(vals):
                summary[name] = summary_result

        return summary

    async def get_eval_results(self, model: Union[Op, Model]) -> EvaluationResults:
        if not is_valid_model(model):
            raise ValueError(
                "`Evaluation.evaluate` requires a `Model` or `Op` instance as the `model` argument. "
                "If you are using a function, wrap it with `weave.op` to create an `Op` instance."
            )

        async def eval_example(example: dict) -> dict:
            try:
                return await self.predict_and_score(model, example)
            except OpCallError as e:
                raise e
            except Exception:
                print("Predict and score failed")
                traceback.print_exc()
                return _create_empty_eval_row()

        def _create_empty_eval_row() -> dict:
            return {self._output_key: None, "scores": {}}

        trial_rows = list(self._post_init_dataset.rows) * self.trials
        eval_rows = []

        async for _, eval_row in util.async_foreach(
            trial_rows, eval_example, get_weave_parallelism()
        ):
            print(f"Evaluated {len(eval_rows)} of {len(trial_rows)} examples")
            if eval_row is None:
                eval_row = _create_empty_eval_row()
            else:
                eval_row["scores"] = eval_row.get("scores", {})
                for scorer in self._post_init_scorers:
                    attrs = get_scorer_attributes(scorer)
                    scorer_name = attrs.scorer_name
                    eval_row["scores"].setdefault(scorer_name, {})
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


I = TypeVar("I", bound=dict[str, Any])
O = TypeVar("O")
ScoreT = TypeVar("ScoreT")
ScorerName = TypeVar("ScorerName", bound=str)


# ScoreT alternative (more permissive)
class ScoreDict(TypedDict):
    score: float
    metadata: NotRequired[dict[str, Any]]


# ScoreT alternative 2 (more constrained)
class ScorePydantic(BaseModel):
    score: Annotated[float, Field(gte=0, lte=1)]
    metadata: Optional[dict[str, Any]] = None


@runtime_checkable
class ScorerProtocol(Protocol[O]):
    """Scorers are anything that return ScoreDict"""

    async def __call__(self, output: O, *args: Any, **kwargs: Any) -> ScoreDict: ...


@dataclass
class ScoringTask(Generic[O]):
    scorer: ScorerProtocol[O]
    output: O
    metadata: dict[str, Any]


@dataclass
class ScoringTaskResult:
    name: str
    score: ScoreDict


class ScoringResult(TypedDict):
    scores: dict


@runtime_checkable
class ModelProtocol(Protocol[I, O]):
    def __call__(self, input: I) -> O: ...


@runtime_checkable
class AsyncModelProtocol(Protocol[I, O]):
    async def __call__(self, input: I) -> O: ...


class PredictorOutputDict(TypedDict, Generic[O]):
    output: O
    metadata: NotRequired[dict[str, Any]]


@runtime_checkable
class PredictorProtocol(Protocol[I, O]):
    """Unsure about this one.  The intent is to wrap a model with metadata that is created at runtime."""

    async def __call__(self, input: I) -> PredictorOutputDict[O]: ...


def is_async_callable(obj: Any) -> bool:
    if inspect.iscoroutinefunction(obj):
        return True

    if hasattr(obj, "__call__") and inspect.iscoroutinefunction(obj.__call__):
        return True

    return False


class BasicPredictor:
    """A basic predictor that wraps a model output to include latency and success/error info"""

    def __init__(self, model: ModelProtocol[I, O] | AsyncModelProtocol[I, O]):
        self.model = model

    # async def __call__(self, input: I) -> PredictorOutputDict[O]:
    async def __call__(self, input: I) -> Call:
        if is_async_callable(self.model):
            return await self.model(**input)
        return self.model(**input)

        # start_time = time()
        # try:
        #     if is_async_callable(self.model):
        #         # output = await self.model(**input)
        #         _, call = await self.model.call(**input)
        #     else:
        #         # output = self.model(**input)
        #         _, call = self.model.call(**input)
        # except Exception as e:
        #     output = None
        #     metadata = {
        #         "latency": time() - start_time,
        #         "success": False,
        #         "error": str(e),
        #     }
        # else:
        #     metadata = {
        #         "latency": time() - start_time,
        #         "success": True,
        #     }

        # return PredictorOutputDict(input=input, output=output, metadata=metadata)
        return call


class Evaluation2(Object, Generic[I, O, ScoreT]):
    dataset: Dataset | Sequence[I]  # TODO: Dataset can also be parameterized
    scorers: list[Scorer] | Sequence[ScorerProtocol[ScoreT]]
    preprocess_model_input: PreprocessModelInput | None = None
    trials: int = 1

    @model_validator(mode="before")
    def _convert_dataset(cls, values: dict) -> dict:
        if "dataset" in values:
            if not isinstance(values["dataset"], Dataset):
                values["dataset"] = Dataset(rows=values["dataset"])
        return values

    async def evaluate(
        self,
        *,
        model: ModelProtocol[I, O] | None = None,
        predictions: Sequence[O] | None = None,
    ) -> dict:
        """Evaluate a model or a set of predictions.

        This runs both predict and score concurrently!"""
        if not model and not predictions:
            raise ValueError("Must provide a model or predictions")

        # TODO: Each step does an async_foreach, but must collect results back into
        # a list before returning.  This is not efficient!  Evaluate should instead
        # have a more optimized version that does everything in one step.  That
        # implementation is TBD.
        if not predictions:
            predictions = await self.predict(model=model)

        return await self.score(predictions=predictions)

    async def predict(
        self,
        *,
        model: ModelProtocol[I, O],
        predictor_cls: PredictorProtocol[I, O] = BasicPredictor,
    ) -> Dataset:
        new_rows = []
        async for row in self._predict(model, predictor_cls):
            new_rows.append(row)
        return Dataset(rows=new_rows)

    async def _predict(
        self,
        model: ModelProtocol[I, O],
        predictor_cls: PredictorProtocol[I, O] = BasicPredictor,
        # ) -> Sequence[PredictorOutputDict[O]]:
    ) -> AsyncGenerator[dict, None, None]:
        # At the end of this method, the user should have the same thing as `Dataset.from_calls(...)`

        async def predict_row(row: Any) -> dict:
            # TODO: Suppress call donut messages here
            if is_async_callable(model):
                _, call = await model.call(**row)
            else:
                _, call = model.call(**row)

            return call

        async for _, prediction in util.async_foreach(
            self.dataset, predict_row, get_weave_parallelism()
        ):
            # TODO: Instead of dictify, it would be nice if we could link to the actual call
            yield prediction.to_dict()

    async def score(
        self,
        *,
        predictions: Sequence[PredictorOutputDict[O]],
        extra_metadata: Sequence[dict[str, Any]] | None = None,
    ) -> Sequence[dict[ScorerName, list[ScoreDict]]]:
        scores = {get_callable_name(scorer): [] for scorer in self.scorers}
        async for res in self._score(predictions, extra_metadata):
            scores[res.name].append(res.score)
        return scores

    async def _score(
        self,
        predictions: Sequence[PredictorOutputDict[O]],
        extra_metadata: Sequence[dict[str, Any]] | None = None,
    ) -> AsyncGenerator[ScoringTaskResult, None, None]:
        if extra_metadata is None:
            extra_metadata = [{} for _ in predictions]

        if not (len(predictions) == len(self.dataset) == len(extra_metadata)):
            raise ValueError(
                f"Number of predictions ({len(predictions)}) must match dataset size ({len(self.dataset)}) times trials ({self.trials})"
            )

        def scoring_tasks() -> Generator[ScoringTask, None, None]:
            for pred, meta_dict in zip(predictions, extra_metadata):
                combined_metadata = {**pred.get("metadata", {}), **meta_dict}
                for scorer in self.scorers:
                    yield ScoringTask(scorer, pred["output"], combined_metadata)

        async def run_scorer(task: ScoringTask) -> ScoringTaskResult:
            try:
                if is_async_callable(task.scorer):
                    score = await task.scorer(task.output, **task.metadata)
                else:
                    score = task.scorer(task.output, **task.metadata)
            except Exception as e:
                score = None
                metadata = {"error": str(e)}
            else:
                metadata = {}

            return ScoringTaskResult(
                name=get_callable_name(task.scorer),
                score={"score": score, "metadata": metadata},
            )

        async for _, res in util.async_foreach(
            scoring_tasks(), run_scorer, get_weave_parallelism()
        ):
            yield res

    async def aggregate_results(self): ...

    def summarize(self, results: Sequence[ScoringResult]) -> dict[str, Any]:
        cols = transpose(list(results))
        summary = {}

        if "scores" in cols:
            score_data = transpose(cols["scores"])
            for scorer in self._post_init_scorers:
                attrs = get_scorer_attributes(scorer)
                score_table = score_data[attrs.scorer_name]
                summary[attrs.scorer_name] = attrs.summarize_fn(score_table)

        for name, vals in cols.items():
            if name == "scores":
                continue
            if summary_result := auto_summarize(vals):
                summary[name] = summary_result

        return summary


def evaluate(
    dataset: Union[Dataset, list],
    model: Union[Op, Model],
    scorers: Optional[list[Union[Callable, Scorer]]] = None,
    preprocess_model_input: Optional[PreprocessModelInput] = None,
) -> dict:
    ev = Evaluation(
        dataset=dataset,
        scorers=scorers,
        preprocess_model_input=preprocess_model_input,
    )
    return asyncio.run(ev.evaluate(model))


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
