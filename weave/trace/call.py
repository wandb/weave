from __future__ import annotations

import dataclasses
import datetime
import logging
from collections.abc import Callable
from concurrent.futures import Future
from typing import TYPE_CHECKING, Any, TypedDict

from weave.trace import urls
from weave.trace.context import weave_client_context as weave_client_context
from weave.trace.feedback import RefFeedbackQuery
from weave.trace.isinstance import weave_isinstance
from weave.trace.op_protocol import Op
from weave.trace.ref_util import get_ref
from weave.trace.refs import CallRef, ObjectRef, OpRef
from weave.trace.serialization.serialize import from_json
from weave.trace.util import log_once
from weave.trace.vals import WeaveObject
from weave.trace_server.constants import MAX_DISPLAY_NAME_LENGTH
from weave.trace_server.interface.query import Query
from weave.trace_server.trace_server_interface import (
    CallSchema,
    CallsFilter,
    CallsQueryReq,
    CallsQueryStatsReq,
    SortBy,
    TraceServerInterface,
)
from weave.utils.attributes_dict import AttributesDict
from weave.utils.paginated_iterator import PaginatedIterator
from weave.utils.project_id import from_project_id

if TYPE_CHECKING:
    from weave.flow.scorer import ApplyScorerResult, Scorer

logger = logging.getLogger(__name__)

DEFAULT_CALLS_PAGE_SIZE = 1000


class OpNameError(ValueError):
    """Raised when an op name is invalid."""


@dataclasses.dataclass
class Call:
    """A Call represents a single operation executed as part of a trace.

    ``attributes`` are frozen once the call is created. Use
    :func:`weave.attributes` or ``create_call(..., attributes=...)`` to
    populate metadata beforehand. The ``summary`` dictionary may be
    modified while the call is running; its contents are deep-merged
    with computed summary values when :meth:`WeaveClient.finish_call`
    is invoked.
    """

    _op_name: str | Future[str]
    trace_id: str
    project_id: str
    parent_id: str | None
    inputs: dict[str, Any]
    id: str | None = None
    output: Any = None
    exception: str | None = None
    summary: dict[str, Any] | None = dataclasses.field(default_factory=dict)
    _display_name: str | Callable[[Call], str] | None = None
    attributes: dict[str, Any] | None = None
    started_at: datetime.datetime | None = None
    ended_at: datetime.datetime | None = None
    deleted_at: datetime.datetime | None = None
    thread_id: str | None = None
    turn_id: str | None = None
    wb_run_id: str | None = None
    wb_run_step: int | None = None
    wb_run_step_end: int | None = None

    # These are the live children during logging
    _children: list[Call] = dataclasses.field(default_factory=list)
    _feedback: RefFeedbackQuery | None = None

    # Size of metadata storage for this call
    storage_size_bytes: int | None = None

    # Total size of metadata storage for the entire trace
    total_storage_size_bytes: int | None = None

    @property
    def display_name(self) -> str | Callable[[Call], str] | None:
        return self._display_name

    @display_name.setter
    def display_name(self, name: str | Callable[[Call], str] | None) -> None:
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
        """The decorated function's name that produced this call.

        This is different from `op_name` which is usually the ref of the op.
        """
        if self.op_name.startswith("weave:///"):
            ref = OpRef.parse_uri(self.op_name)
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
                entity, project = from_project_id(self.project_id)
            except ValueError:
                raise ValueError(f"Invalid project_id: {self.project_id}") from None
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
            entity, project = from_project_id(self.project_id)
        except ValueError:
            raise ValueError(f"Invalid project_id: {self.project_id}") from None
        return urls.redirect_call(entity, project, self.id)

    @property
    def ref(self) -> CallRef:
        entity, project = from_project_id(self.project_id)
        if not self.id:
            raise ValueError(
                "Can't get ref for call without ID, was `weave.init` called?"
            )

        return CallRef(entity, project, self.id)

    # These are the children if we're using Call at read-time
    def children(self, *, page_size: int = DEFAULT_CALLS_PAGE_SIZE) -> CallsIter:
        """Get the children of the call.

        Args:
            page_size: Tune performance by changing the number of calls fetched at a time.

        Returns:
            An iterator of calls.
        """
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
        """Set the display name for the call.

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
        additional_scorer_kwargs: dict[str, Any] | None = None,
    ) -> ApplyScorerResult:
        """`apply_scorer` is a method that applies a Scorer to a Call. This is useful
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
        apply_scorer_result = await apply_scorer_async(scorer, example, output)
        score_call = apply_scorer_result.score_call

        wc = weave_client_context.get_weave_client()
        if wc:
            scorer_ref = None
            if weave_isinstance(scorer, Scorer):
                # Very important: if the score is generated from a Scorer subclass,
                # then scorer_ref will be None, and we will use the op_name from
                # the score_call instead.
                scorer_ref = get_ref(scorer)
            wc._send_score_call(self, score_call, scorer_ref)
        return apply_scorer_result

    def to_dict(self) -> CallDict:
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
            thread_id=self.thread_id,
            turn_id=self.turn_id,
        )


class NoOpCall(Call):
    def __init__(self) -> None:
        super().__init__(
            _op_name="", trace_id="", project_id="", parent_id=None, inputs={}
        )


class CallDict(TypedDict):
    op_name: str
    trace_id: str
    project_id: str
    parent_id: str | None
    inputs: dict[str, Any]
    id: str | None
    output: Any
    exception: str | None
    summary: dict[str, Any] | None
    display_name: str | None
    attributes: dict[str, Any] | None
    started_at: datetime.datetime | None
    ended_at: datetime.datetime | None
    deleted_at: datetime.datetime | None
    thread_id: str | None
    turn_id: str | None


CallsIter = PaginatedIterator[CallSchema, WeaveObject]


def elide_display_name(name: str) -> str:
    if len(name) > MAX_DISPLAY_NAME_LENGTH:
        log_once(
            logger.warning,
            f"Display name {name} is longer than {MAX_DISPLAY_NAME_LENGTH} characters.  It will be truncated!",
        )
        return name[: MAX_DISPLAY_NAME_LENGTH - 3] + "..."
    return name


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
    include_storage_size: bool = False,
    include_total_storage_size: bool = False,
    columns: list[str] | None = None,
    expand_columns: list[str] | None = None,
    return_expanded_column_values: bool = True,
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
                    include_storage_size=include_storage_size,
                    include_total_storage_size=include_total_storage_size,
                    query=query,
                    sort_by=sort_by,
                    columns=columns,
                    expand_columns=expand_columns,
                    return_expanded_column_values=return_expanded_column_values,
                )
            )
        )

    # TODO: Should be Call, not WeaveObject
    def transform_func(call: CallSchema) -> WeaveObject:
        entity, project = from_project_id(project_id)
        return make_client_call(entity, project, call, server)

    def size_func() -> int:
        response = server.calls_query_stats(
            CallsQueryStatsReq(
                project_id=project_id,
                filter=filter,
                query=query,
                expand_columns=expand_columns,
            )
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
        summary=dict(server_call.summary) if server_call.summary is not None else {},
        _display_name=server_call.display_name,
        attributes=server_call.attributes,
        started_at=server_call.started_at,
        ended_at=server_call.ended_at,
        deleted_at=server_call.deleted_at,
        thread_id=server_call.thread_id,
        turn_id=server_call.turn_id,
        wb_run_id=server_call.wb_run_id,
        wb_run_step=server_call.wb_run_step,
        wb_run_step_end=server_call.wb_run_step_end,
        storage_size_bytes=server_call.storage_size_bytes,
        total_storage_size_bytes=server_call.total_storage_size_bytes,
    )
    if isinstance(call.attributes, AttributesDict):
        call.attributes.freeze()
    ref = CallRef(entity, project, call_id)
    return WeaveObject(call, ref, server, None)
