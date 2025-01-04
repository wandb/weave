import inspect
import textwrap
from concurrent.futures import Future
from typing import Any, TypedDict, Union

from weave.scorers import (
    Scorer,
    get_scorer_attributes,
)
from weave.trace.async_caller import async_call, async_call_op
from weave.trace.context.weave_client_context import get_weave_client
from weave.trace.errors import OpCallError
from weave.trace.isinstance import weave_isinstance
from weave.trace.op import Op, as_op, is_op
from weave.trace.weave_client import Call, get_ref


class ApplyScorerResult(TypedDict):
    scorer_name: str
    score: Any
    # Only non in legacy cases which i think can be removed
    score_call: Call | None
    # TODO: Get rid of these nones
    feedback_id_future: Future[str] | None


async def apply_scorer(
    scorer: Union[Scorer, Op],
    example: dict,
    model_output: Any,
    model_call: Call | None = None,
) -> ApplyScorerResult:
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
        score_arg_names = [param for param in score_arg_names if (param != "self")]
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
            score_args = {k: v for k, v in example.items() if k in score_arg_names}

    else:
        if len(score_arg_names) == 2:
            score_args = {score_arg_names[0]: example}
        else:
            raise ValueError(
                f"{score_fn} expects arguments: {score_arg_names}, provide a preprocess_model_input function that returns a dict with those keys."
            )
    score_args[score_output_name] = model_output

    try:
        score_call = None
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

            # Maybe this should be done in the caller?
            wc = get_weave_client()
            if wc:
                # Very important: if the score is generated from a Scorer subclass,
                # then scorer_ref_uri will be None, and we will use the op_name from
                # the score_call instead.
                scorer_ref = get_ref(scorer_self) if scorer_self else None
                scorer_ref_uri = scorer_ref.uri() if scorer_ref else None
                feedback_id_future = wc._send_score_call(
                    model_call, score_call, scorer_ref_uri
                )

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

    return ApplyScorerResult(
        scorer_name=scorer_name,
        score=result,
        score_call=score_call,
        feedback_id_future=feedback_id_future,
    )
