import asyncio
import dataclasses
import datetime
import inspect
import logging
import textwrap
from collections.abc import Coroutine
from concurrent.futures import Future
from typing import Any, Callable, TypedDict, Union

import weave.trace.urls as urls
from weave.flow.scorer import Scorer, get_scorer_attributes
from weave.trace.context import weave_client_context as weave_client_context
from weave.trace.feedback import RefFeedbackQuery
from weave.trace.isinstance import weave_isinstance
from weave.trace.op import Op, OpCallError, OpNameError, as_op, is_op
from weave.trace.ref_util import get_ref
from weave.trace.refs import CallRef, ObjectRef, parse_op_uri
from weave.trace.serialization.serialize import from_json
from weave.trace.util import log_once
from weave.trace.vals import WeaveObject
from weave.trace_server.constants import MAX_DISPLAY_NAME_LENGTH
from weave.trace_server.trace_server_interface import (
    CallSchema,
    CallsFilter,
    CallsQueryReq,
    CallsQueryStatsReq,
    Query,
    SortBy,
    TraceServerInterface,
)
from weave.utils.iterators import PaginatedIterator

logger = logging.getLogger(__name__)

DEFAULT_CALLS_PAGE_SIZE = 1000
# TODO: should be Call, not WeaveObject
CallsIter = PaginatedIterator[CallSchema, WeaveObject]


@dataclasses.dataclass
class Call:
    """A Call represents a single operation that was executed as part of a trace."""

    _op_name: str | Future[str]
    trace_id: str
    project_id: str
    parent_id: str | None
    inputs: dict
    id: str | None = None
    output: Any = None
    exception: str | None = None
    summary: dict | None = None
    _display_name: str | Callable[["Call"], str] | None = None
    attributes: dict | None = None
    started_at: datetime.datetime | None = None
    ended_at: datetime.datetime | None = None
    deleted_at: datetime.datetime | None = None

    # These are the live children during logging
    _children: list["Call"] = dataclasses.field(default_factory=list)
    _feedback: RefFeedbackQuery | None = None

    @property
    def display_name(self) -> str | Callable[["Call"], str] | None:
        return self._display_name

    @display_name.setter
    def display_name(self, name: str | Callable[["Call"], str] | None) -> None:
        if isinstance(name, str):
            name = elide_display_name(name)
        self._display_name = name

    @property
    def op_name(self) -> str:
        if isinstance(self._op_name, Future):
            self.__dict__["_op_name"] = self._op_name.result()

        if not isinstance(self._op_name, str):
            raise OpNameError(f"Call op_name is not a string: {self._op_name}")

        return self._op_name

    @property
    def func_name(self) -> str:
        """
        The decorated function's name that produced this call.

        This is different from `op_name` which is usually the ref of the op.
        """
        if self.op_name.startswith("weave:///"):
            ref = parse_op_uri(self.op_name)
            return ref.name

        return self.op_name

    @property
    def feedback(self) -> RefFeedbackQuery:
        if not self.id:
            raise ValueError(
                "Can't get feedback for call without ID, was `weave.init` called?"
            )

        if self._feedback is None:
            try:
                entity, project = self.project_id.split("/")
            except ValueError:
                raise ValueError(f"Invalid project_id: {self.project_id}")
            weave_ref = CallRef(entity, project, self.id)
            self._feedback = RefFeedbackQuery(weave_ref.uri())
        return self._feedback

    @property
    def ui_url(self) -> str:
        if not self.id:
            raise ValueError(
                "Can't get URL for call without ID, was `weave.init` called?"
            )

        try:
            entity, project = self.project_id.split("/")
        except ValueError:
            raise ValueError(f"Invalid project_id: {self.project_id}")
        return urls.redirect_call(entity, project, self.id)

    @property
    def ref(self) -> CallRef:
        entity, project = self.project_id.split("/")
        if not self.id:
            raise ValueError(
                "Can't get ref for call without ID, was `weave.init` called?"
            )

        return CallRef(entity, project, self.id)

    # These are the children if we're using Call at read-time
    def children(self, *, page_size: int = DEFAULT_CALLS_PAGE_SIZE) -> CallsIter:
        """
        Get the children of the call.

        Args:
            page_size: Tune performance by changing the number of calls fetched at a time.

        Returns:
            An iterator of calls.
        """
        client = weave_client_context.require_weave_client()
        if not self.id:
            raise ValueError(
                "Can't get children of call without ID, was `weave.init` called?"
            )

        client = weave_client_context.require_weave_client()
        return _make_calls_iterator(
            client.server,
            self.project_id,
            CallsFilter(parent_ids=[self.id]),
            page_size=page_size,
        )

    def delete(self) -> bool:
        """Delete the call."""
        client = weave_client_context.require_weave_client()
        client.delete_call(call=self)
        return True

    def set_display_name(self, name: str | None) -> None:
        """
        Set the display name for the call.

        Args:
            name: The display name to set for the call.

        Example:

        ```python
        result, call = my_function.call("World")
        call.set_display_name("My Custom Display Name")
        ```
        """
        if name == "":
            raise ValueError(
                "Display name cannot be empty. To remove the display_name, set name=None or use remove_display_name."
            )
        if name == self.display_name:
            return
        client = weave_client_context.require_weave_client()
        client._set_call_display_name(call=self, display_name=name)
        self.display_name = name

    def remove_display_name(self) -> None:
        self.set_display_name(None)

    async def apply_scorer(
        self,
        scorer: Op | Scorer,
        additional_scorer_kwargs: dict | None = None,
    ) -> "ApplyScorerResult":
        """
        `apply_scorer` is a method that applies a Scorer to a Call. This is useful
        for guarding application logic with a scorer and/or monitoring the quality
        of critical ops. Scorers are automatically logged to Weave as Feedback and
        can be used in queries & analysis.

        Args:
            scorer: The Scorer to apply.
            additional_scorer_kwargs: Additional kwargs to pass to the scorer. This is
                useful for passing in additional context that is not part of the call
                inputs.useful for passing in additional context that is not part of the call
                inputs.

        Returns:
            The result of the scorer application in the form of an `ApplyScorerResult`.

        ```python
        class ApplyScorerSuccess:
            result: Any
            score_call: Call
        ```

        Example usage:

        ```python
        my_scorer = ... # construct a scorer
        prediction, prediction_call = my_op.call(input_data)
        result, score_call = prediction.apply_scorer(my_scorer)
        ```
        """
        from weave.flow.scorer import Scorer, apply_scorer_async

        model_inputs = {k: v for k, v in self.inputs.items() if k != "self"}
        example = {**model_inputs, **(additional_scorer_kwargs or {})}
        output = self.output
        if isinstance(output, ObjectRef):
            output = output.get()
        apply_scorer_result = await apply_scorer_async(
            scorer, example, output, async_call_op
        )
        score_call = apply_scorer_result.score_call

        wc = weave_client_context.get_weave_client()
        if wc:
            scorer_ref_uri = None
            if weave_isinstance(scorer, Scorer):
                # Very important: if the score is generated from a Scorer subclass,
                # then scorer_ref_uri will be None, and we will use the op_name from
                # the score_call instead.
                scorer_ref = get_ref(scorer)
                scorer_ref_uri = scorer_ref.uri() if scorer_ref else None
            wc._send_score_call(self, score_call, scorer_ref_uri)
        return apply_scorer_result

    def to_dict(self) -> "CallDict":
        if callable(display_name := self.display_name):
            display_name = "Callable Display Name (not called yet)"

        return CallDict(
            op_name=self.op_name,
            trace_id=self.trace_id,
            project_id=self.project_id,
            parent_id=self.parent_id,
            inputs=self.inputs,
            id=self.id,
            output=self.output,
            exception=self.exception,
            summary=self.summary,
            display_name=display_name,
            attributes=self.attributes,
            started_at=self.started_at,
            ended_at=self.ended_at,
            deleted_at=self.deleted_at,
        )


class CallDict(TypedDict):
    op_name: str
    trace_id: str
    project_id: str
    parent_id: str | None
    inputs: dict
    id: str | None
    output: Any
    exception: str | None
    summary: dict | None
    display_name: str | None
    attributes: dict | None
    started_at: datetime.datetime | None
    ended_at: datetime.datetime | None
    deleted_at: datetime.datetime | None


def _make_calls_iterator(
    server: TraceServerInterface,
    project_id: str,
    filter: CallsFilter,
    limit_override: int | None = None,
    offset_override: int | None = None,
    sort_by: list[SortBy] | None = None,
    query: Query | None = None,
    include_costs: bool = False,
    include_feedback: bool = False,
    columns: list[str] | None = None,
    page_size: int = DEFAULT_CALLS_PAGE_SIZE,
) -> CallsIter:
    def fetch_func(offset: int, limit: int) -> list[CallSchema]:
        # Add the global offset to the page offset
        # This ensures the offset is applied only once
        effective_offset = offset
        if offset_override is not None:
            effective_offset += offset_override

        return list(
            server.calls_query_stream(
                CallsQueryReq(
                    project_id=project_id,
                    filter=filter,
                    offset=effective_offset,
                    limit=limit,
                    include_costs=include_costs,
                    include_feedback=include_feedback,
                    query=query,
                    sort_by=sort_by,
                    columns=columns,
                )
            )
        )

    # TODO: Should be Call, not WeaveObject
    def transform_func(call: CallSchema) -> WeaveObject:
        entity, project = project_id.split("/")
        return make_client_call(entity, project, call, server)

    def size_func() -> int:
        response = server.calls_query_stats(
            CallsQueryStatsReq(project_id=project_id, filter=filter, query=query)
        )
        if limit_override is not None:
            offset = offset_override or 0
            return min(limit_override, max(0, response.count - offset))
        if offset_override is not None:
            return response.count - offset_override
        return response.count

    if offset_override is not None and offset_override < 0:
        raise ValueError("offset must be greater than or equal to 0")

    return PaginatedIterator(
        fetch_func,
        transform_func=transform_func,
        size_func=size_func,
        limit=limit_override,
        offset=None,  # Set offset to None since we handle it in fetch_func
        page_size=page_size,
    )


def make_client_call(
    entity: str, project: str, server_call: CallSchema, server: TraceServerInterface
) -> WeaveObject:
    if (call_id := server_call.id) is None:
        raise ValueError("Call ID is None")

    call = Call(
        _op_name=server_call.op_name,
        project_id=server_call.project_id,
        trace_id=server_call.trace_id,
        parent_id=server_call.parent_id,
        id=call_id,
        inputs=from_json(server_call.inputs, server_call.project_id, server),
        output=from_json(server_call.output, server_call.project_id, server),
        exception=server_call.exception,
        summary=dict(server_call.summary) if server_call.summary is not None else None,
        _display_name=server_call.display_name,
        attributes=server_call.attributes,
        started_at=server_call.started_at,
        ended_at=server_call.ended_at,
        deleted_at=server_call.deleted_at,
    )
    ref = CallRef(entity, project, call_id)
    return WeaveObject(call, ref, server, None)


class NoOpCall(Call):
    def __init__(self) -> None:
        super().__init__(
            _op_name="", trace_id="", project_id="", parent_id=None, inputs={}
        )


def async_call(func: Union[Callable, Op], *args: Any, **kwargs: Any) -> Coroutine:
    """For async functions, calls them directly. For sync functions, runs them in a thread.
    This provides a common async interface for both sync and async functions.

    Args:
        func: The callable or Op to wrap
        *args: Positional arguments to pass to the function
        **kwargs: Keyword arguments to pass to the function

    Returns:
        A coroutine that will execute the function
    """
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
    """Similar to async_call but specifically for Ops, handling the Weave tracing
    functionality. For sync Ops, runs them in a thread.

    Args:
        func: The Op to wrap
        *args: Positional arguments to pass to the Op
        **kwargs: Keyword arguments to pass to the Op

    Returns:
        A coroutine that will execute the Op and return a tuple of (result, Call)
    """
    is_async = inspect.iscoroutinefunction(func.resolve_fn)
    if is_async:
        return func.call(*args, __should_raise=True, **kwargs)
    else:
        return asyncio.to_thread(
            lambda: func.call(*args, __should_raise=True, **kwargs)
        )


def elide_display_name(name: str) -> str:
    if len(name) > MAX_DISPLAY_NAME_LENGTH:
        log_once(
            logger.warning,
            f"Display name {name} is longer than {MAX_DISPLAY_NAME_LENGTH} characters.  It will be truncated!",
        )
        return name[: MAX_DISPLAY_NAME_LENGTH - 3] + "..."
    return name


# Using `dataclass` because pydantic does not like `Call` as a property
@dataclasses.dataclass
class ApplyScorerSuccess:
    result: Any
    score_call: Call


ApplyScorerResult = ApplyScorerSuccess


async def apply_scorer_async(
    scorer: Union[Op, Scorer],
    example: dict,
    model_output: Any,
    async_call_op: Callable[
        [Op, Any, dict[str, Any]], Coroutine[Any, Any, tuple[Any, Call]]
    ],
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
