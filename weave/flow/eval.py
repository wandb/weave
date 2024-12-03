import asyncio
import inspect
import logging
import textwrap
import time
import traceback
from collections.abc import Coroutine
from typing import Any, Callable, Literal, Optional, Union, cast

from pydantic import PrivateAttr
from rich import print
from rich.console import Console

import weave
from weave.flow import util
from weave.flow.dataset import Dataset
from weave.flow.model import Model, get_infer_method
from weave.flow.obj import Object
from weave.scorers import (
    Scorer,
    _has_oldstyle_scorers,
    _validate_scorer_signature,
    auto_summarize,
    get_scorer_attributes,
    transpose,
)
from weave.trace.context.weave_client_context import get_weave_client
from weave.trace.env import get_weave_parallelism
from weave.trace.errors import OpCallError
from weave.trace.isinstance import weave_isinstance
from weave.trace.op import Op, as_op, is_op
from weave.trace.vals import WeaveObject
from weave.trace.weave_client import Call, get_ref

console = Console()
logger = logging.getLogger(__name__)

INVALID_MODEL_ERROR = (
    "`Evaluation.evaluate` requires a `Model` or `Op` instance as the `model` argument. "
    + "If you are using a function, wrap it with `weave.op` to create an `Op` instance."
)


def async_call(func: Union[Callable, Op], *args: Any, **kwargs: Any) -> Coroutine:
    is_async = False
    if is_op(func):
        func = as_op(func)
        is_async = inspect.iscoroutinefunction(func.resolve_fn)
    else:
        is_async = inspect.iscoroutinefunction(func)
    if is_async:
        return func(*args, **kwargs)  # type: ignore
    return asyncio.to_thread(func, *args, **kwargs)


def async_call_op(
    func: Op, *args: Any, **kwargs: Any
) -> Coroutine[Any, Any, tuple[Any, "Call"]]:
    call_res = func.call(*args, __should_raise=True, **kwargs)
    if inspect.iscoroutine(call_res):
        return call_res
    return asyncio.to_thread(lambda: call_res)


class EvaluationResults(Object):
    rows: weave.Table


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

    dataset: Union[Dataset, list]
    scorers: Optional[list[Union[Callable, Op, Scorer]]] = None
    preprocess_model_input: Optional[Callable] = None
    trials: int = 1

    # internal attr to track whether to use the new `output` or old `model_output` key for outputs
    _output_key: Literal["output", "model_output"] = PrivateAttr("output")

    def model_post_init(self, __context: Any) -> None:
        scorers: list[Union[Callable, Scorer, Op]] = []
        for scorer in self.scorers or []:
            if isinstance(scorer, Scorer):
                pass
            elif isinstance(scorer, type):
                raise TypeError(
                    f"Scorer {scorer.__name__} must be an instance, not a class. Did you forget to instantiate?"
                )
            elif callable(scorer) and not is_op(scorer):
                scorer = weave.op()(scorer)
            elif is_op(scorer):
                pass
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
        self.scorers = scorers

        if isinstance(self.dataset, list):
            self.dataset = Dataset(rows=self.dataset)

        if self.name is None and self.dataset.name is not None:
            self.name = self.dataset.name + "-evaluation"  # type: ignore

    @weave.op()
    async def predict_and_score(
        self, model: Union[Callable, Model], example: dict
    ) -> dict:
        if self.preprocess_model_input is None:
            model_input = example
        else:
            model_input = self.preprocess_model_input(example)  # type: ignore

        model_self = None
        model_predict: Union[Callable, Model]
        if callable(model):
            model_predict = model
        else:
            model_self = model
            model_predict = get_infer_method(model)

        model_predict_fn_name = (
            as_op(model_predict).name
            if is_op(model_predict)
            else model_predict.__name__
        )

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
            model_start_time = time.time()
            model_call = None
            if is_op(model_predict):
                # I would expect this path to always be hit, but keeping the other
                # path for backwards compatibility / safety
                model_predict = as_op(model_predict)
                if model_self is not None:
                    model_predict_args = {
                        **model_predict_args,
                        "self": model_self,
                    }
                model_output, model_call = await async_call_op(
                    model_predict, **model_predict_args
                )
            else:
                # I would not expect this path to be hit, but keeping it for
                # backwards compatibility / safety
                model_output = await async_call(model_predict, **model_predict_args)
        except OpCallError as e:
            dataset_column_names = list(example.keys())
            dataset_column_names_str = ", ".join(dataset_column_names[:3])
            if len(dataset_column_names) > 3:
                dataset_column_names_str += ", ..."
            required_arg_names = [
                param.name
                for param in predict_signature.parameters.values()
                if param.default == inspect.Parameter.empty
            ]

            message = textwrap.dedent(
                f"""
                Call error: {e}

                Options for resolving:
                a. change {model_predict_fn_name} argument names to match a subset of dataset column names: {dataset_column_names_str}
                b. change dataset column names to match expected {model_predict_fn_name} argument names: {required_arg_names}
                c. construct Evaluation with a preprocess_model_input function that accepts a dataset example and returns a dict with keys expected by {model_predict_fn_name}
                """
            )
            raise OpCallError(message)
        except Exception as e:
            print("model_output failed")
            traceback.print_exc()
            model_output = None
        model_latency = time.time() - model_start_time

        scores = {}  # TODO: Consider moving scorer setup and checks out of `predict_and_score`
        scorers = cast(list[Union[Op, Scorer]], self.scorers or [])

        for scorer in scorers:
            scorer_self = None
            if weave_isinstance(scorer, Scorer):
                scorer_self = scorer
            scorer_name, score_fn, _ = get_scorer_attributes(scorer)
            score_signature = inspect.signature(score_fn)
            score_arg_names = list(score_signature.parameters.keys())

            # the actual kwarg name depends on the scorer
            if "output" in score_arg_names:
                score_output_name = "output"
            elif "model_output" in score_arg_names:
                score_output_name = "model_output"
            else:
                message = textwrap.dedent(
                    f"""
                    Scorer {scorer_name} must have an `output` or `model_output` argument, to receive the
                    output of the model function.
                    """
                )
                raise OpCallError(message)

            if isinstance(example, dict):
                # The keys of `score_args` must match the argument names of the scorer's `score` method.
                # If scorer.column_map is set, then user is indicating that the dataset column(s)
                # being passed to the scorer have different names to the `score` functions' argument names.
                # So we need to remap the dataset columns to the expected argument names in the scorer,
                #
                # column_map k:v pairs must be structured as `scorer param name : dataset column name`
                #
                # For instance, if the scorer expects "input" and "ground_truth" and we have a dataset
                # with columns "question" and "answer", column_map should be defined as follows:
                # {"input": "question", "ground_truth": "answer"}
                #
                # input: is the full row, we have access to it via example
                # output: is the model output, we have access to it via model_output
                score_arg_names = [
                    param for param in score_arg_names if (param != "self")
                ]
                score_args = {}

                if isinstance(scorer, Scorer) and scorer.column_map is not None:
                    # Ensure that all keys in column_map are in score_arg_names
                    for key in scorer.column_map.keys():
                        if key not in score_arg_names:
                            message = textwrap.dedent(
                                f"""
                                    You have created `{scorer_name}(column_map={scorer.column_map}, ...)`.

                                    The `column_map` contains a key, `{key}`, which is not in the `score` methods' argument names.
                                    `score` methods' argument names: {score_arg_names}

                                    Hint:
                                    - Ensure that the keys in `column_map` match the scorer's argument names.
                                    """
                            )
                            raise ValueError(message)

                    for arg in score_arg_names:
                        if arg == "output" or arg == "model_output":
                            continue
                        if arg in example:
                            score_args[arg] = example[arg]
                        elif arg in scorer.column_map:
                            dataset_column_name = scorer.column_map[arg]
                            if dataset_column_name in example:
                                score_args[arg] = example[dataset_column_name]
                            else:
                                message = textwrap.dedent(
                                    f"""
                                        You have created `{scorer_name}(column_map={scorer.column_map}, ...)`.

                                        You are mapping `{arg}` to `{dataset_column_name}`, but `{dataset_column_name}`
                                        was not found in the dataset columns.

                                        Available dataset columns: {list(example.keys())}

                                        Hint:
                                        - Ensure that `column_map` maps the `score` methods' argument names to existing dataset column names.
                                        """
                                )
                                raise ValueError(message)
                        else:
                            message = textwrap.dedent(
                                f"""
                                    You have created `{scorer_name}(column_map={scorer.column_map}, ...)`.

                                    `score` method argument `{arg}` is not found in the dataset columns and is not mapped in `column_map`.

                                    Available dataset columns: {list(example.keys())}
                                    `column_map`: {scorer.column_map}

                                    Hint:
                                    Either:
                                    - map the argument name to the dataset column using the scorers `column_map` attribute, in the form {{score_arg_name : dataset_column_name}} or
                                    - rename a column in the dataset to `{arg}` or
                                    - re-name the `{arg}` argument in your `score` method to match a dataset column name
                                    """
                            )
                            raise ValueError(message)
                else:
                    score_args = {
                        k: v for k, v in example.items() if k in score_arg_names
                    }

            else:
                if len(score_arg_names) == 2:
                    score_args = {score_arg_names[0]: example}
                else:
                    raise ValueError(
                        f"{score_fn} expects arguments: {score_arg_names}, provide a preprocess_model_input function that returns a dict with those keys."
                    )
            score_args[score_output_name] = model_output

            try:
                if is_op(score_fn) and model_call:
                    # I would expect this path to always be hit, but keeping the other
                    # path for backwards compatibility / safety
                    score_fn = as_op(score_fn)
                    if scorer_self is not None:
                        score_args = {
                            **score_args,
                            "self": scorer_self,
                        }
                    result, score_call = await async_call_op(score_fn, **score_args)
                    wc = get_weave_client()
                    if wc:
                        # Very important: if the score is generated from a Scorer subclass,
                        # then scorer_ref_uri will be None, and we will use the op_name from
                        # the score_call instead.
                        scorer_ref = get_ref(scorer_self) if scorer_self else None
                        scorer_ref_uri = scorer_ref.uri() if scorer_ref else None
                        wc._send_score_call(model_call, score_call, scorer_ref_uri)

                else:
                    # I would not expect this path to be hit, but keeping it for
                    # backwards compatibility / safety
                    result = await async_call(score_fn, **score_args)
            except OpCallError as e:
                dataset_column_names = list(example.keys())
                dataset_column_names_str = ", ".join(dataset_column_names[:3])
                if len(dataset_column_names) > 10:
                    dataset_column_names_str += ", ..."
                required_arg_names = [
                    param.name
                    for param in score_signature.parameters.values()
                    if param.default == inspect.Parameter.empty
                ]
                required_arg_names.remove(score_output_name)

                message = textwrap.dedent(
                    f"""
                    Call error: {e}

                                        If using the `Scorer` weave class, you can set the `scorer.column_map`
                    attribute to map scorer argument names to dataset columns.

                    For example, if the `score` expects "output", "input" and "ground_truth" and we have a dataset
                    with columns "question" and "answer", `column_map` can be used to map the non-output parameter like so:
                    {{"input": "question", "ground_truth": "answer"}}

                    scorer argument names: {score_arg_names}
                    dataset keys: {example.keys()}
                    scorer.column_map: {getattr(scorer, 'column_map', '{}')}

                    Options for resolving:
                    a. if using the `Scorer` weave class, you can set the `scorer.column_map` attribute to map scorer argument names to dataset column names or
                    b. change the argument names the in the scoring function of {scorer_name} to match a subset of dataset column names: ({dataset_column_names_str}) or
                    c. change dataset column names to match expected {scorer_name} argument names: {required_arg_names}
                    """
                )
                raise OpCallError(message)
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
                scorers = self.scorers or []
                for scorer in scorers:
                    scorer_name, _, summarize_fn = get_scorer_attributes(scorer)
                    scorer_stats = transpose(vals)
                    score_table = scorer_stats[scorer_name]
                    scored = summarize_fn(score_table)
                    summary[scorer_name] = scored
            else:
                model_output_summary = auto_summarize(vals)
                if model_output_summary:
                    summary[name] = model_output_summary
        return summary

    async def get_eval_results(
        self, model: Union[Callable, Model]
    ) -> EvaluationResults:
        if not is_valid_model(model):
            raise ValueError(INVALID_MODEL_ERROR)
        eval_rows = []

        start_time = time.time()

        async def eval_example(example: dict) -> dict:
            try:
                eval_row = await self.predict_and_score(model, example)
            except OpCallError as e:
                raise e
            except Exception as e:
                print("Predict and score failed")
                traceback.print_exc()
                return {self._output_key: None, "scores": {}}
            return eval_row

        n_complete = 0
        # with console.status("Evaluating...") as status:
        dataset = cast(Dataset, self.dataset)
        _rows = dataset.rows
        trial_rows = list(_rows) * self.trials
        async for example, eval_row in util.async_foreach(
            trial_rows, eval_example, get_weave_parallelism()
        ):
            n_complete += 1
            print(f"Evaluated {n_complete} of {len(trial_rows)} examples")
            # status.update(
            #     f"Evaluating... {duration:.2f}s [{n_complete} / {len(self.dataset.rows)} complete]"  # type:ignore
            # )
            if eval_row is None:
                eval_row = {self._output_key: None, "scores": {}}
            else:
                eval_row["scores"] = eval_row.get("scores", {})
            for scorer in self.scorers or []:
                scorer_name, _, _ = get_scorer_attributes(scorer)
                if scorer_name not in eval_row["scores"]:
                    eval_row["scores"][scorer_name] = {}
            eval_rows.append(eval_row)
        return EvaluationResults(rows=weave.Table(eval_rows))

    @weave.op()
    async def evaluate(self, model: Union[Callable, Model]) -> dict:
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
    model: Union[Callable, Model],
    scores: Optional[list[Union[Callable, Scorer]]] = None,
    preprocess_model_input: Optional[Callable] = None,
) -> dict:
    eval = Evaluation(
        dataset=dataset, scorers=scores, preprocess_model_input=preprocess_model_input
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
