import asyncio
import inspect
import textwrap
import time
import traceback
from typing import Any, Callable, Coroutine, Optional, Union, cast

from rich import print
from rich.console import Console

import weave
from weave.flow import util
from weave.flow.dataset import Dataset
from weave.flow.model import Model, get_infer_method
from weave.flow.obj import Object
from weave.flow.scorer import (
    Scorer,
    auto_summarize,
    get_scorer_attributes,
    transpose,
)
from weave.trace.env import get_weave_parallelism
from weave.trace.errors import OpCallError
from weave.trace.op import Op, as_op, is_op
from weave.trace.vals import WeaveObject
from weave.trace.weave_client import get_ref

console = Console()


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

    def model_post_init(self, __context: Any) -> None:
        scorers: list[Union[Callable, Scorer, Op]] = []
        for scorer in self.scorers or []:
            if isinstance(scorer, Scorer):
                pass
            elif isinstance(scorer, type):
                raise ValueError(
                    f"Scorer {scorer.__name__} must be an instance, not a class. Did you forget to instantiate?"
                )
            elif callable(scorer) and not is_op(scorer):
                scorer = weave.op()(scorer)
            elif is_op(scorer):
                pass
            else:
                raise ValueError(f"Invalid scorer: {scorer}")
            scorers.append(scorer)
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

        if callable(model):
            model_predict = model
        else:
            model_predict = get_infer_method(model)

        model_predict_fn_name = (
            as_op(model_predict).name
            if is_op(model_predict)
            else model_predict.__name__
        )

        if is_op(model_predict):
            model_predict = as_op(model_predict)
            predict_signature = model_predict.signature
        else:
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

        scores = {}
        scorers = cast(list[Union[Op, Scorer]], self.scorers or [])
        for scorer in scorers:
            scorer_name, score_fn, _ = get_scorer_attributes(scorer)
            if is_op(score_fn):
                score_fn = as_op(score_fn)
                score_signature = score_fn.signature
            else:
                score_signature = inspect.signature(score_fn)
            score_arg_names = list(score_signature.parameters.keys())

            if "model_output" not in score_arg_names:
                raise OpCallError(
                    f"Scorer {scorer_name} must have a 'model_output' argument, to receive the output of the model function."
                )

            if isinstance(example, dict):
                score_args = {k: v for k, v in example.items() if k in score_arg_names}
            else:
                if len(score_arg_names) == 2:
                    score_args = {score_arg_names[0]: example}
                else:
                    raise ValueError(
                        f"{score_fn} expects arguments: {score_arg_names}, provide a preprocess_model_input function that returns a dict with those keys."
                    )
            score_args["model_output"] = model_output

            try:
                result = await async_call(score_fn, **score_args)
            except OpCallError as e:
                dataset_column_names = list(example.keys())
                dataset_column_names_str = ", ".join(dataset_column_names[:3])
                if len(dataset_column_names) > 3:
                    dataset_column_names_str += ", ..."
                required_arg_names = [
                    param.name
                    for param in score_signature.parameters.values()
                    if param.default == inspect.Parameter.empty
                ]
                required_arg_names.remove("model_output")

                message = textwrap.dedent(
                    f"""
                    Call error: {e}

                    Options for resolving:
                    a. change {scorer_name} argument names to match a subset of dataset column names ({dataset_column_names_str})
                    b. change dataset column names to match expected {scorer_name} argument names: {required_arg_names}
                    """
                )
                raise OpCallError(message)
            scores[scorer_name] = result

        return {
            "model_output": model_output,
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

    @weave.op()
    async def evaluate(self, model: Union[Callable, Model]) -> dict:
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
                return {"model_output": None, "scores": {}}
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
            duration = time.time() - start_time
            print(f"Evaluated {n_complete} of {len(trial_rows)} examples")
            # status.update(
            #     f"Evaluating... {duration:.2f}s [{n_complete} / {len(self.dataset.rows)} complete]"  # type:ignore
            # )
            if eval_row is None:
                eval_row = {"model_output": None, "scores": {}}
            else:
                eval_row["scores"] = eval_row.get("scores", {})
            for scorer in self.scorers or []:
                scorer_name, _, _ = get_scorer_attributes(scorer)
                if scorer_name not in eval_row["scores"]:
                    eval_row["scores"][scorer_name] = {}
            eval_rows.append(eval_row)

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
        eval_results = EvaluationResults(rows=weave.Table(eval_rows))
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
