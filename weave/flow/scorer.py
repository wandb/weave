import inspect
import textwrap
from collections.abc import Sequence
from dataclasses import dataclass
from numbers import Number
from typing import Any, Callable, Optional, Union, cast

import numpy as np
from pydantic import BaseModel, Field

import weave
from weave.flow.obj import Object
from weave.trace.isinstance import weave_isinstance
from weave.trace.op import Op, OpCallError, as_op, is_op
from weave.trace.op_caller import async_call_op
from weave.trace.weave_client import Call, sanitize_object_name


class Scorer(Object):
    column_map: Optional[dict[str, str]] = Field(
        default=None,
        description="A mapping from column names in the dataset to the names expected by the scorer",
    )

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        _validate_scorer_signature(self)

    @weave.op
    def score(self, *, output: Any, **kwargs: Any) -> Any:
        raise NotImplementedError

    @weave.op()
    def summarize(self, score_rows: list) -> Optional[dict]:
        return auto_summarize(score_rows)


def _validate_scorer_signature(scorer: Union[Callable, Op, Scorer]) -> bool:
    """Validate that the scorer signature does not have both `output` and `model_output`.

    Having both `output` and `model_output` in the scorer signature causes
    issues with scoring because it's ambigious as to which one is the
    canonical "output", and which is just a regular kwarg.
    """
    if isinstance(scorer, Scorer):
        params = inspect.signature(scorer.score).parameters
    else:
        params = inspect.signature(scorer).parameters
    if "output" in params and "model_output" in params:
        raise ValueError(
            textwrap.dedent(
                """
                The scorer signature cannot include both `output` and `model_output` at the same time.

                To resolve, rename one of the arguments to avoid conflict. Prefer using `output` as the model's output.
                """
            )
        )
    return True


def stderr(data: Sequence[Union[int, float]]) -> float:
    if len(data) > 1:
        sample_variance = np.var(data, ddof=1)
        return float(np.sqrt(sample_variance / len(data)))
    else:
        return 0


def auto_summarize(data: list) -> Optional[dict[str, Any]]:
    """Automatically summarize a list of (potentially nested) dicts.

    Computes:
        - avg for numeric cols
        - count and fraction for boolean cols
        - other col types are ignored

    If col is all None, result is None

    Returns:
      dict of summary stats, with structure matching input dict structure.
    """
    if not data:
        return {}
    data = [x for x in data if x is not None]

    if not data:
        return None

    val = data[0]

    if isinstance(val, bool):
        return {
            "true_count": (true_count := sum(1 for x in data if x)),
            "true_fraction": true_count / len(data),
        }
    elif isinstance(val, Number):
        return {"mean": np.mean(data).item()}
    elif isinstance(val, dict):
        result = {}
        all_keys = set().union(*[x.keys() for x in data if isinstance(x, dict)])
        for k in all_keys:
            if (
                summary := auto_summarize(
                    [x.get(k) for x in data if isinstance(x, dict)]
                )
            ) is not None:
                if k in summary:
                    result.update(summary)
                else:
                    result[k] = summary
        if not result:
            return None
        return result
    elif isinstance(val, BaseModel):
        return auto_summarize([x.model_dump() for x in data])
    return None


@dataclass
class ScorerAttributes:
    scorer_name: str
    score_op: Op
    summarize_fn: Callable


def get_scorer_attributes(
    scorer: Union[Op, Scorer],
) -> ScorerAttributes:
    score_op: Op
    scorer_name: str
    if weave_isinstance(scorer, Scorer):
        if scorer.name:
            scorer_name = scorer.name
        else:
            scorer_name = scorer.__class__.__name__
        try:
            if not is_op(scorer.score):
                raise TypeError(
                    f"Scorer {scorer_name} must implement `score` as a weave.op() decorated function."
                )
            score_op = scorer.score
            summarize_fn = scorer.summarize  # type: ignore

        except AttributeError:
            raise ValueError(
                f"Scorer {scorer_name} must implement score and summarize methods. Did you forget to wrap with @weave.op()?"
            )
    elif is_op(scorer):
        scorer = as_op(scorer)
        scorer_name = cast(str, scorer.name)
        score_op = scorer
        summarize_fn = auto_summarize  # type: ignore
    else:
        raise ValueError(f"Unknown scorer type: {scorer}")

    if scorer_name:
        scorer_name = sanitize_object_name(scorer_name)

    return ScorerAttributes(
        scorer_name=scorer_name, score_op=score_op, summarize_fn=summarize_fn
    )


def _has_oldstyle_scorers(scorers: list[Union[Op, Scorer]]) -> bool:
    """Check if any scorers use the deprecated 'model_output' parameter."""
    for scorer in scorers:
        scorer_attributes = get_scorer_attributes(scorer)
        score_op = scorer_attributes.score_op
        score_signature = inspect.signature(score_op)
        if "model_output" in score_signature.parameters:
            return True
    return False


# Using `dataclass` because pydantic does not like `Call` as a property
@dataclass
class ApplyScorerSuccess:
    result: Any
    score_call: Call


ApplyScorerResult = ApplyScorerSuccess


async def apply_scorer_async(
    scorer: Union[Op, Scorer], example: dict, model_output: Any
) -> ApplyScorerResult:
    """Apply a scoring function to model output and example data asynchronously.

    This function handles the application of a scoring function to evaluate model outputs.
    It supports both function-based scorers (Op) and class-based scorers (Scorer),
    managing argument mapping and validation.

    Args:
        scorer: Either an Op (function) or Scorer (class) that implements scoring logic
        example: Dictionary containing the input example data with features to score against
        model_output: Dictionary containing the model's output to be scored

    Returns:
        ApplyScorerResult: Contains the scoring result and the Call object representing
            the scoring operation

    Raises:
        OpCallError: If there are issues with argument mapping or scorer execution
        ValueError: If the column mapping configuration is invalid
    """
    # For class-based scorers, we need to keep track of the instance
    scorer_self = None
    if weave_isinstance(scorer, Scorer):
        scorer_self = scorer

    # Extract the core components of the scorer
    scorer_attributes = get_scorer_attributes(scorer)
    scorer_name = scorer_attributes.scorer_name
    score_op = scorer_attributes.score_op
    score_signature = inspect.signature(score_op)
    score_arg_names = list(score_signature.parameters.keys())

    # Determine which parameter name is used for model output
    # Scorers must have either 'output' or 'model_output' (deprecated) parameter
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
    # Remove 'self' from argument names if present (for class-based scorers)
    score_arg_names = [param for param in score_arg_names if (param != "self")]
    score_args = {}

    # Handle column mapping if provided
    # This allows dataset columns to be mapped to scorer argument names
    if isinstance(scorer, Scorer) and scorer.column_map is not None:
        # Validate that all mapped columns exist in scorer signature
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

        # Build arguments dictionary using column mapping
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
        # Without column mapping, directly match scorer arguments to example keys
        score_args = {k: v for k, v in example.items() if k in score_arg_names}

    # Add the model output to the arguments
    score_args[score_output_name] = model_output

    try:
        # Execute the scoring operation
        score_op = as_op(score_op)
        if scorer_self is not None:
            score_args = {
                **score_args,
                "self": scorer_self,
            }
        result, score_call = await async_call_op(score_op, **score_args)
    except OpCallError as e:
        # Provide detailed error message if scoring fails
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
            scorer.column_map: {getattr(scorer, "column_map", "{}")}

            Options for resolving:
            a. if using the `Scorer` weave class, you can set the `scorer.column_map` attribute to map scorer argument names to dataset column names or
            b. change the argument names the in the scoring function of {scorer_name} to match a subset of dataset column names: ({dataset_column_names_str}) or
            c. change dataset column names to match expected {scorer_name} argument names: {required_arg_names}
            """
        )
        raise OpCallError(message)

    return ApplyScorerSuccess(result=result, score_call=score_call)


class WeaveScorerResult(BaseModel):
    """The result of a weave.Scorer.score method."""

    passed: bool = Field(description="Whether the scorer passed or not")
    metadata: dict[str, Any] = Field(
        description="Any extra information from the scorer like numerical scores, model outputs, etc."
    )
