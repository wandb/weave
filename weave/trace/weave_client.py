from __future__ import annotations

import dataclasses
import datetime
import json
import logging
import os
import platform
import re
import sys
import time
from collections.abc import Iterator, Sequence
from concurrent.futures import Future
from functools import lru_cache
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Generic,
    Protocol,
    TypedDict,
    TypeVar,
    cast,
    overload,
)

import pydantic
from requests import HTTPError

from weave import version
from weave.trace import trace_sentry, urls
from weave.trace.concurrent.futures import FutureExecutor
from weave.trace.context import call_context
from weave.trace.context import weave_client_context as weave_client_context
from weave.trace.exception import exception_to_json_str
from weave.trace.feedback import FeedbackQuery, RefFeedbackQuery
from weave.trace.interface_query_builder import (
    exists_expr,
    get_field_expr,
    literal_expr,
)
from weave.trace.isinstance import weave_isinstance
from weave.trace.object_record import (
    ObjectRecord,
    dataclass_object_record,
    pydantic_object_record,
)
from weave.trace.objectify import maybe_objectify
from weave.trace.op import (
    Op,
    as_op,
    is_op,
    is_placeholder_call,
    is_tracing_setting_disabled,
    maybe_unbind_method,
    placeholder_call,
    print_call_link,
    should_skip_tracing_for_op,
)
from weave.trace.op import op as op_deco
from weave.trace.ref_util import get_ref, remove_ref, set_ref
from weave.trace.refs import (
    CallRef,
    ObjectRef,
    OpRef,
    Ref,
    TableRef,
    maybe_parse_uri,
    parse_op_uri,
    parse_uri,
)
from weave.trace.sanitize import REDACTED_VALUE, should_redact
from weave.trace.serialization.serialize import (
    from_json,
    isinstance_namedtuple,
    to_json,
)
from weave.trace.serialization.serializer import get_serializer_for_obj
from weave.trace.settings import (
    client_parallelism,
    should_capture_client_info,
    should_capture_system_info,
    should_print_call_link,
    should_redact_pii,
)
from weave.trace.table import Table
from weave.trace.util import deprecated, log_once
from weave.trace.vals import WeaveObject, WeaveTable, make_trace_obj
from weave.trace.weave_client_send_file_cache import WeaveClientSendFileCache
from weave.trace_server.constants import MAX_DISPLAY_NAME_LENGTH, MAX_OBJECT_NAME_LENGTH
from weave.trace_server.ids import generate_id
from weave.trace_server.interface.feedback_types import (
    RUNNABLE_FEEDBACK_TYPE_PREFIX,
    runnable_feedback_output_selector,
    runnable_feedback_runnable_ref_selector,
)
from weave.trace_server.trace_server_interface import (
    CallEndReq,
    CallSchema,
    CallsDeleteReq,
    CallsFilter,
    CallsQueryReq,
    CallsQueryStatsReq,
    CallStartReq,
    CallUpdateReq,
    CostCreateInput,
    CostCreateReq,
    CostCreateRes,
    CostPurgeReq,
    CostQueryOutput,
    CostQueryReq,
    EndedCallSchemaForInsert,
    FeedbackCreateReq,
    FileCreateReq,
    FileCreateRes,
    ObjCreateReq,
    ObjCreateRes,
    ObjDeleteReq,
    ObjectVersionFilter,
    ObjQueryReq,
    ObjReadReq,
    ObjSchema,
    ObjSchemaForInsert,
    Query,
    RefsReadBatchReq,
    SortBy,
    StartedCallSchemaForInsert,
    TableAppendSpec,
    TableAppendSpecPayload,
    TableCreateReq,
    TableCreateRes,
    TableSchemaForInsert,
    TableUpdateReq,
    TraceServerInterface,
)
from weave.trace_server_bindings.remote_http_trace_server import RemoteHTTPTraceServer

if TYPE_CHECKING:
    import pandas as pd

    from weave.flow.scorer import ApplyScorerResult, Scorer


# Controls if objects can have refs to projects not the WeaveClient project.
# If False, object refs with with mismatching projects will be recreated.
# If True, use existing ref to object in other project.
ALLOW_MIXED_PROJECT_REFS = False

logger = logging.getLogger(__name__)

T = TypeVar("T")
R = TypeVar("R", covariant=True)


class FetchFunc(Protocol[T]):
    def __call__(self, offset: int, limit: int) -> list[T]: ...


TransformFunc = Callable[[T], R]
SizeFunc = Callable[[], int]


class PaginatedIterator(Generic[T, R]):
    """An iterator that fetches pages of items from a server and optionally transforms them
    into a more user-friendly type."""

    def __init__(
        self,
        fetch_func: FetchFunc[T],
        page_size: int = 1000,
        transform_func: TransformFunc[T, R] | None = None,
        size_func: SizeFunc | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> None:
        self.fetch_func = fetch_func
        self.page_size = page_size
        self.transform_func = transform_func
        self.size_func = size_func
        self.limit = limit
        self.offset = offset

        if page_size <= 0:
            raise ValueError("page_size must be greater than 0")
        if limit is not None and limit <= 0:
            raise ValueError("limit must be greater than 0")

    @lru_cache
    def _fetch_page(self, index: int) -> list[T]:
        return self.fetch_func(index * self.page_size, self.page_size)

    @overload
    def _get_one(self: PaginatedIterator[T, T], index: int) -> T: ...
    @overload
    def _get_one(self: PaginatedIterator[T, R], index: int) -> R: ...
    def _get_one(self, index: int) -> T | R:
        if index < 0:
            raise IndexError("Negative indexing not supported")

        if self.limit is not None and index >= self.limit + (self.offset or 0):
            raise IndexError(f"Index {index} out of range")

        if self.offset is not None:
            index += self.offset

        page_index = index // self.page_size
        page_offset = index % self.page_size

        page = self._fetch_page(page_index)
        if page_offset >= len(page):
            raise IndexError(f"Index {index} out of range")

        res = page[page_offset]
        if transform := self.transform_func:
            return transform(res)
        return res

    @overload
    def _get_slice(self: PaginatedIterator[T, T], key: slice) -> Iterator[T]: ...
    @overload
    def _get_slice(self: PaginatedIterator[T, R], key: slice) -> Iterator[R]: ...
    def _get_slice(self, key: slice) -> Iterator[T] | Iterator[R]:
        if (start := key.start or 0) < 0:
            raise ValueError("Negative start not supported")
        if (stop := key.stop) is not None and stop < 0:
            raise ValueError("Negative stop not supported")
        if (step := key.step or 1) < 0:
            raise ValueError("Negative step not supported")

        # Apply limit if provided
        if self.limit is not None:
            if stop is None or stop > self.limit:
                stop = self.limit

        # Apply offset if provided
        if self.offset is not None:
            start += self.offset
            if stop is not None:
                stop += self.offset

        i = start
        while stop is None or i < stop:
            try:
                yield self._get_one(i)
            except IndexError:
                break
            i += step

    @overload
    def __getitem__(self: PaginatedIterator[T, T], key: int) -> T: ...
    @overload
    def __getitem__(self: PaginatedIterator[T, R], key: int) -> R: ...
    @overload
    def __getitem__(self: PaginatedIterator[T, T], key: slice) -> list[T]: ...
    @overload
    def __getitem__(self: PaginatedIterator[T, R], key: slice) -> list[R]: ...
    def __getitem__(self, key: slice | int) -> T | R | list[T] | list[R]:
        if isinstance(key, slice):
            return list(self._get_slice(key))
        return self._get_one(key)

    @overload
    def __iter__(self: PaginatedIterator[T, T]) -> Iterator[T]: ...
    @overload
    def __iter__(self: PaginatedIterator[T, R]) -> Iterator[R]: ...
    def __iter__(self) -> Iterator[T] | Iterator[R]:
        return self._get_slice(slice(0, None, 1))

    def __len__(self) -> int:
        """This method is included for convenience.  It includes a network call, which
        is typically slower than most other len() operations!"""
        if not self.size_func:
            raise TypeError("This iterator does not support len()")
        return self.size_func()

    def to_pandas(self) -> pd.DataFrame:
        """Convert the iterator's contents to a pandas DataFrame.

        Returns:
            A pandas DataFrame containing all the data from the iterator.

        Example:
            ```python
            calls = client.get_calls()
            df = calls.to_pandas()
            ```

        Note:
            This method will fetch all data from the iterator, which may involve
            multiple network calls. For large datasets, consider using limits
            or filters to reduce the amount of data fetched.
        """
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas is required to use this method")

        records = []
        for item in self:
            if isinstance(item, dict):
                records.append(item)
            elif hasattr(item, "to_dict"):
                records.append(item.to_dict())
            else:
                raise ValueError(f"Unable to convert item to dict: {item}")

        return pd.DataFrame(records)


# TODO: should be Call, not WeaveObject
CallsIter = PaginatedIterator[CallSchema, WeaveObject]
DEFAULT_CALLS_PAGE_SIZE = 1000


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


def _add_scored_by_to_calls_query(
    scored_by: list[str] | str | None, query: Query | None
) -> Query | None:
    # This logic might be pushed down to the server soon, but for now it lives here:
    if not scored_by:
        return query

    if isinstance(scored_by, str):
        scored_by = [scored_by]
    exprs = []
    if query is not None:
        exprs.append(query["$expr"])
    for name in scored_by:
        ref = maybe_parse_uri(name)
        if ref and isinstance(ref, ObjectRef):
            uri = name
            scorer_name = ref.name
            exprs.append(
                {
                    "$eq": (
                        get_field_expr(
                            runnable_feedback_runnable_ref_selector(scorer_name)
                        ),
                        literal_expr(uri),
                    )
                }
            )
        else:
            exprs.append(
                exists_expr(get_field_expr(runnable_feedback_output_selector(name)))
            )
    return Query.model_validate({"$expr": {"$and": exprs}})


class OpNameError(ValueError):
    """Raised when an op name is invalid."""


def get_obj_name(val: Any) -> str:
    name = getattr(val, "name", None)
    if name is None:
        if isinstance(val, ObjectRecord):
            name = val._class_name
        else:
            name = f"{val.__class__.__name__}"
    if not isinstance(name, str):
        raise TypeError(f"Object's name attribute is not a string: {name}")
    return name


def _get_direct_ref(obj: Any) -> Ref | None:
    if isinstance(obj, WeaveTable):
        # TODO: this path is odd. We want to use table_ref when serializing
        # which is the direct ref to the table. But .ref on WeaveTable is
        # the "container ref", ie a ref to the root object that the WeaveTable
        # is within, with extra pointing to the table.
        return obj.table_ref
    return get_ref(obj)


def map_to_refs(obj: Any) -> Any:
    if isinstance(obj, Ref):
        return obj
    if ref := _get_direct_ref(obj):
        return ref

    if isinstance(obj, ObjectRecord):
        return obj.map_values(map_to_refs)
    elif isinstance(obj, (pydantic.BaseModel, pydantic.v1.BaseModel)):
        obj_record = pydantic_object_record(obj)
        return obj_record.map_values(map_to_refs)
    elif dataclasses.is_dataclass(obj):
        obj_record = dataclass_object_record(obj)
        return obj_record.map_values(map_to_refs)
    elif isinstance(obj, Table):
        return obj.ref
    elif isinstance(obj, WeaveTable):
        return obj.ref
    elif isinstance_namedtuple(obj):
        return {k: map_to_refs(v) for k, v in obj._asdict().items()}
    elif isinstance(obj, (list, tuple)):
        return [map_to_refs(v) for v in obj]
    elif isinstance(obj, dict):
        return {k: map_to_refs(v) for k, v in obj.items()}

    # This path should only be reached if the object is both:
    # 1. A `WeaveObject`; and
    # 2. Has been dirtied (edited in any way), causing obj.ref=None
    elif isinstance(obj, WeaveObject):
        return map_to_refs(obj._val)

    return obj


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
    _display_name: str | Callable[[Call], str] | None = None
    attributes: dict | None = None
    started_at: datetime.datetime | None = None
    ended_at: datetime.datetime | None = None
    deleted_at: datetime.datetime | None = None

    # These are the live children during logging
    _children: list[Call] = dataclasses.field(default_factory=list)
    _feedback: RefFeedbackQuery | None = None

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
        self, scorer: Op | Scorer, additional_scorer_kwargs: dict | None = None
    ) -> ApplyScorerResult:
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
        apply_scorer_result = await apply_scorer_async(scorer, example, output)
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
        )


class NoOpCall(Call):
    def __init__(self) -> None:
        super().__init__(
            _op_name="", trace_id="", project_id="", parent_id=None, inputs={}
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


def sum_dict_leaves(dicts: list[dict]) -> dict:
    # dicts is a list of dictionaries, that may or may not
    # have nested dictionaries. Sum all the leaves that match
    result: dict = {}
    for d in dicts:
        for k, v in d.items():
            if isinstance(v, dict):
                result[k] = sum_dict_leaves([result.get(k, {}), v])
            elif v is not None:
                result[k] = result.get(k, 0) + v
    return result


class WeaveKeyDict(dict):
    """A dict representing the 'weave' subdictionary of a call's attributes.

    This dictionary is not intended to be set directly.
    """

    def __setitem__(self, key: Any, value: Any) -> None:
        raise KeyError("Cannot modify `weave` dict directly -- for internal use only!")


class AttributesDict(dict):
    """A dict representing the attributes of a call.

    The `weave` key is reserved for internal use and cannot be set directly.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__()
        dict.__setitem__(self, "weave", WeaveKeyDict())

        if kwargs:
            for key, value in kwargs.items():
                if key == "weave":
                    if isinstance(value, dict):
                        for subkey, subvalue in value.items():
                            self._set_weave_item(subkey, subvalue)
                else:
                    self[key] = value

    def __setitem__(self, key: Any, value: Any) -> None:
        if key == "weave":
            raise KeyError("Cannot set 'weave' directly -- for internal use only!")
        super().__setitem__(key, value)

    def _set_weave_item(self, subkey: Any, value: Any) -> None:
        """Internal method to set items in the 'weave' subdictionary."""
        dict.__setitem__(self["weave"], subkey, value)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({super().__repr__()})"


BACKGROUND_PARALLELISM_MIX = 0.5


class WeaveClient:
    server: TraceServerInterface

    # Main future executor, handling deferred tasks for the client
    future_executor: FutureExecutor
    # Fast-lane executor for operations guaranteed to not defer
    # to child operations, impossible to deadlock
    # Currently only used for create_file operation
    # Mix of main and fastlane workers is set by BACKGROUND_PARALLELISM_MIX
    future_executor_fastlane: FutureExecutor | None

    # Cache of files sent to the server to avoid sending the same file
    # multiple times.
    send_file_cache: WeaveClientSendFileCache

    """
    A client for interacting with the Weave trace server.

    Args:
        entity: The entity name.
        project: The project name.
        server: The server to use for communication.
        ensure_project_exists: Whether to ensure the project exists on the server.
    """

    def __init__(
        self,
        entity: str,
        project: str,
        server: TraceServerInterface,
        ensure_project_exists: bool = True,
    ):
        self.entity = entity
        self.project = project
        self.server = server
        self._anonymous_ops: dict[str, Op] = {}
        parallelism_main, parallelism_upload = get_parallelism_settings()
        self.future_executor = FutureExecutor(max_workers=parallelism_main)
        if parallelism_upload:
            self.future_executor_fastlane = FutureExecutor(
                max_workers=parallelism_upload
            )
        self.ensure_project_exists = ensure_project_exists

        if ensure_project_exists:
            resp = self.server.ensure_project_exists(entity, project)
            # Set Client project name with updated project name
            self.project = resp.project_name

        self._server_is_flushable = False
        if isinstance(self.server, RemoteHTTPTraceServer):
            self._server_is_flushable = self.server.should_batch
        self.send_file_cache = WeaveClientSendFileCache()

    ################ High Level Convenience Methods ################

    @trace_sentry.global_trace_sentry.watch()
    def save(self, val: Any, name: str, branch: str = "latest") -> Any:
        """Do not call directly, use weave.publish() instead.

        Args:
            val: The object to save.
            name: The name to save the object under.
            branch: The branch to save the object under. Defaults to "latest".

        Returns:
            A deserialized version of the saved object.
        """
        # Adding a second comment line for developers that is not a docstring:
        # Save an object to the weave server and return a deserialized version of it.

        # Note: This is sort of a weird method becuase:
        # 1. It returns a deserialized version of the object (which will often not pass type-checks)
        # 2. It is slow (because it re-downloads the object from the weave server)
        # 3. It explicitly filters out non ObjectRefs, which seems like a useless constraint.
        #
        # Because of these reasons, `weave.publish()` directly calls `_save_object()`
        # and then returns the raw ObjectRef. I (Tim) think we should consider refactoring
        # `save()`. I am not sure when as an end user you would ever want to use this method.

        ref = self._save_object(val, name, branch)
        if not isinstance(ref, ObjectRef):
            raise TypeError(f"Expected ObjectRef, got {ref}")
        return self.get(ref)

    @trace_sentry.global_trace_sentry.watch()
    def get(self, ref: ObjectRef, *, objectify: bool = True) -> Any:
        project_id = f"{ref.entity}/{ref.project}"
        try:
            read_res = self.server.obj_read(
                ObjReadReq(
                    project_id=project_id,
                    object_id=ref.name,
                    digest=ref.digest,
                )
            )
        except HTTPError as e:
            if e.response is not None:
                if e.response.content:
                    try:
                        reason = json.loads(e.response.content).get("reason")
                        raise ValueError(reason)
                    except json.JSONDecodeError:
                        raise ValueError(e.response.content)
                if e.response.status_code == 404:
                    raise ValueError(f"Unable to find object for ref uri: {ref.uri()}")
            raise

        # At this point, `ref.digest` is one of three things:
        # 1. "latest" - the user asked for the latest version of the object
        # 2. "v###" - the user asked for a specific version of the object
        # 3. The actual digest.
        #
        # However, we always want to resolve the ref to the digest. So
        # here, we just directly assign the digest.
        ref = dataclasses.replace(ref, _digest=read_res.obj.digest)

        # If there is a ref-extra, we should resolve it. Rather than walking
        # the object, it is more efficient to directly query for the data and
        # let the server resolve it.
        if ref.extra:
            try:
                ref_read_res = self.server.refs_read_batch(
                    RefsReadBatchReq(refs=[ref.uri()])
                )
            except HTTPError as e:
                if e.response is not None and e.response.status_code == 404:
                    raise ValueError(f"Unable to find object for ref uri: {ref.uri()}")
                raise
            if not ref_read_res.vals:
                raise ValueError(f"Unable to find object for ref uri: {ref.uri()}")
            data = ref_read_res.vals[0]
        else:
            data = read_res.obj.val

        val = from_json(data, project_id, self.server)
        weave_obj = make_trace_obj(val, ref, self.server, None)
        if objectify:
            return maybe_objectify(weave_obj)
        return weave_obj

    ################ Query API ################

    @trace_sentry.global_trace_sentry.watch()
    def get_calls(
        self,
        *,
        filter: CallsFilter | None = None,
        limit: int | None = None,
        offset: int | None = None,
        sort_by: list[SortBy] | None = None,
        query: Query | None = None,
        include_costs: bool = False,
        include_feedback: bool = False,
        columns: list[str] | None = None,
        scored_by: str | list[str] | None = None,
        page_size: int = DEFAULT_CALLS_PAGE_SIZE,
    ) -> CallsIter:
        """
        Get a list of calls.

        Args:
            filter: A filter to apply to the calls.
            limit: The maximum number of calls to return.
            offset: The number of calls to skip.
            sort_by: A list of fields to sort the calls by.
            query: A mongo-like query to filter the calls.
            include_costs: If true, cost info is included at summary.weave
            include_feedback: If true, feedback info is included at summary.weave.feedback
            columns: A list of columns to include in the response. If None,
               all columns are included. Specifying fewer columns may be more performant.
               Some columns are always included: id, project_id, trace_id, op_name, started_at
            scored_by: Accepts a list or single item. Each item is a name or ref uri of a scorer
                to filter by. Multiple scorers are ANDed together. If passing in just the name,
                then scores for all versions of the scorer are returned. If passing in the full ref
                URI, then scores for a specific version of the scorer are returned.
            page_size: Tune performance by changing the number of calls fetched at a time.

        Returns:
            An iterator of calls.
        """
        if filter is None:
            filter = CallsFilter()

        query = _add_scored_by_to_calls_query(scored_by, query)

        return _make_calls_iterator(
            self.server,
            self._project_id(),
            filter=filter,
            limit_override=limit,
            offset_override=offset,
            sort_by=sort_by,
            query=query,
            include_costs=include_costs,
            include_feedback=include_feedback,
            columns=columns,
            page_size=page_size,
        )

    @deprecated(new_name="get_calls")
    def calls(
        self,
        filter: CallsFilter | None = None,
        include_costs: bool = False,
    ) -> CallsIter:
        return self.get_calls(filter=filter, include_costs=include_costs)

    @trace_sentry.global_trace_sentry.watch()
    def get_call(
        self,
        call_id: str,
        include_costs: bool = False,
        include_feedback: bool = False,
        columns: list[str] | None = None,
    ) -> WeaveObject:
        """
        Get a single call by its ID.

        Args:
            call_id: The ID of the call to get.
            include_costs: If true, cost info is included at summary.weave
            include_feedback: If true, feedback info is included at summary.weave.feedback
            columns: A list of columns to include in the response. If None,
               all columns are included. Specifying fewer columns may be more performant.
               Some columns are always included: id, project_id, trace_id, op_name, started_at

        Returns:
            A call object.
        """
        calls = list(
            self.server.calls_query_stream(
                CallsQueryReq(
                    project_id=self._project_id(),
                    filter=CallsFilter(call_ids=[call_id]),
                    include_costs=include_costs,
                    include_feedback=include_feedback,
                    columns=columns,
                )
            )
        )
        if not calls:
            raise ValueError(f"Call not found: {call_id}")
        response_call = calls[0]
        return make_client_call(self.entity, self.project, response_call, self.server)

    @deprecated(new_name="get_call")
    def call(
        self,
        call_id: str,
        include_costs: bool = False,
    ) -> WeaveObject:
        return self.get_call(call_id=call_id, include_costs=include_costs)

    @trace_sentry.global_trace_sentry.watch()
    def create_call(
        self,
        op: str | Op,
        inputs: dict,
        parent: Call | None = None,
        attributes: dict | None = None,
        display_name: str | Callable[[Call], str] | None = None,
        *,
        use_stack: bool = True,
    ) -> Call:
        """Create, log, and push a call onto the runtime stack.

        Args:
            op: The operation producing the call, or the name of an anonymous operation.
            inputs: The inputs to the operation.
            parent: The parent call. If parent is not provided, the current run is used as the parent.
            display_name: The display name for the call. Defaults to None.
            attributes: The attributes for the call. Defaults to None.
            use_stack: Whether to push the call onto the runtime stack. Defaults to True.

        Returns:
            The created Call object.
        """
        if is_tracing_setting_disabled() or (
            is_op(op) and should_skip_tracing_for_op(cast(Op, op))
        ):
            return placeholder_call()

        from weave.trace.api import _global_attributes, _global_postprocess_inputs

        if isinstance(op, str):
            if op not in self._anonymous_ops:
                self._anonymous_ops[op] = _build_anonymous_op(op)
            op = self._anonymous_ops[op]

        unbound_op = maybe_unbind_method(op)
        op_def_ref = self._save_op(unbound_op)

        inputs_sensitive_keys_redacted = redact_sensitive_keys(inputs)

        if op.postprocess_inputs:
            inputs_postprocessed = op.postprocess_inputs(inputs_sensitive_keys_redacted)
        else:
            inputs_postprocessed = inputs_sensitive_keys_redacted

        if _global_postprocess_inputs:
            inputs_postprocessed = _global_postprocess_inputs(inputs_postprocessed)

        self._save_nested_objects(inputs_postprocessed)
        inputs_with_refs = map_to_refs(inputs_postprocessed)

        if parent is None and use_stack:
            parent = call_context.get_current_call()

        if parent:
            trace_id = parent.trace_id
            parent_id = parent.id
        else:
            trace_id = generate_id()
            parent_id = None

        if not attributes:
            attributes = {}

        # First create an AttributesDict with global attributes, then update with local attributes
        # Local attributes take precedence over global ones
        attributes_dict = AttributesDict()
        attributes_dict.update(_global_attributes)
        attributes_dict.update(attributes)

        if should_capture_client_info():
            attributes_dict._set_weave_item("client_version", version.VERSION)
            attributes_dict._set_weave_item("source", "python-sdk")
            attributes_dict._set_weave_item("sys_version", sys.version)
        if should_capture_system_info():
            attributes_dict._set_weave_item("os_name", platform.system())
            attributes_dict._set_weave_item("os_version", platform.version())
            attributes_dict._set_weave_item("os_release", platform.release())

        op_name_future = self.future_executor.defer(lambda: op_def_ref.uri())

        call_id = generate_id()
        call = Call(
            _op_name=op_name_future,
            project_id=self._project_id(),
            trace_id=trace_id,
            parent_id=parent_id,
            id=call_id,
            # It feels like this should be inputs_postprocessed, not the refs.
            inputs=inputs_with_refs,
            attributes=attributes_dict,
        )
        # feels like this should be in post init, but keping here
        # because the func needs to be resolved for schema insert below
        if callable(name_func := display_name):
            display_name = name_func(call)
        call.display_name = display_name

        if parent is not None:
            parent._children.append(call)

        current_wb_run_id = safe_current_wb_run_id()
        check_wandb_run_matches(current_wb_run_id, self.entity, self.project)

        started_at = datetime.datetime.now(tz=datetime.timezone.utc)
        project_id = self._project_id()

        _should_print_call_link = should_print_call_link()
        _current_call = call_context.get_current_call()

        def send_start_call() -> bool:
            maybe_redacted_inputs_with_refs = inputs_with_refs
            if should_redact_pii():
                from weave.trace.pii_redaction import redact_pii

                maybe_redacted_inputs_with_refs = redact_pii(inputs_with_refs)

            inputs_json = to_json(
                maybe_redacted_inputs_with_refs, project_id, self, use_dictify=False
            )
            self.server.call_start(
                CallStartReq(
                    start=StartedCallSchemaForInsert(
                        project_id=project_id,
                        id=call_id,
                        op_name=op_def_ref.uri(),
                        display_name=call.display_name,
                        trace_id=trace_id,
                        started_at=started_at,
                        parent_id=parent_id,
                        inputs=inputs_json,
                        attributes=attributes_dict,
                        wb_run_id=current_wb_run_id,
                    )
                )
            )
            return True

        def on_complete(f: Future) -> None:
            try:
                root_call_did_not_error = f.result() and not _current_call
                if root_call_did_not_error and _should_print_call_link:
                    print_call_link(call)
            except Exception:
                pass

        fut = self.future_executor.defer(send_start_call)
        fut.add_done_callback(on_complete)

        if use_stack:
            call_context.push_call(call)

        return call

    @trace_sentry.global_trace_sentry.watch()
    def finish_call(
        self,
        call: Call,
        output: Any = None,
        exception: BaseException | None = None,
        *,
        op: Op | None = None,
    ) -> None:
        if (
            is_tracing_setting_disabled()
            or (op is not None and should_skip_tracing_for_op(op))
            or is_placeholder_call(call)
        ):
            return None

        from weave.trace.api import _global_postprocess_output

        ended_at = datetime.datetime.now(tz=datetime.timezone.utc)
        call.ended_at = ended_at
        original_output = output

        if op is not None and op.postprocess_output:
            postprocessed_output = op.postprocess_output(original_output)
        else:
            postprocessed_output = original_output

        if _global_postprocess_output:
            postprocessed_output = _global_postprocess_output(postprocessed_output)

        self._save_nested_objects(postprocessed_output)
        output_as_refs = map_to_refs(postprocessed_output)
        call.output = postprocessed_output

        # Summary handling
        summary = {}
        if call._children:
            summary = sum_dict_leaves([child.summary or {} for child in call._children])
        elif (
            isinstance(original_output, dict)
            and "usage" in original_output
            and "model" in original_output
        ):
            summary["usage"] = {}
            summary["usage"][original_output["model"]] = {
                "requests": 1,
                **original_output["usage"],
            }
        elif hasattr(original_output, "usage") and hasattr(original_output, "model"):
            # Handle the cases where we are emitting an object instead of a pre-serialized dict
            # In fact, this is going to become the more common case
            model = original_output.model
            usage = original_output.usage
            if isinstance(usage, pydantic.BaseModel):
                usage = usage.model_dump(exclude_unset=True)
            if isinstance(usage, dict) and isinstance(model, str):
                summary["usage"] = {}
                summary["usage"][model] = {"requests": 1, **usage}

        # JR Oct 24 - This descendants stats code has been commented out since
        # it entered the code base. A screenshot of the non-ideal UI that the
        # comment refers to is available in the description of that PR:
        # https://github.com/wandb/weave/pull/1414
        # These should probably be added under the "weave" key in the summary.
        # ---
        # Descendent error tracking disabled til we fix UI
        # Add this call's summary after logging the call, so that only
        # descendents are included in what we log
        # summary.setdefault("descendants", {}).setdefault(
        #     call.op_name, {"successes": 0, "errors": 0}
        # )["successes"] += 1
        call.summary = summary

        # Exception Handling
        exception_str: str | None = None
        if exception:
            exception_str = exception_to_json_str(exception)
            call.exception = exception_str

        project_id = self._project_id()

        # The finish handler serves as a last chance for integrations
        # to customize what gets logged for a call.
        if op is not None and op._on_finish_handler:
            op._on_finish_handler(call, original_output, exception)

        def send_end_call() -> None:
            maybe_redacted_output_as_refs = output_as_refs
            if should_redact_pii():
                from weave.trace.pii_redaction import redact_pii

                maybe_redacted_output_as_refs = redact_pii(output_as_refs)

            output_json = to_json(
                maybe_redacted_output_as_refs, project_id, self, use_dictify=False
            )
            self.server.call_end(
                CallEndReq(
                    end=EndedCallSchemaForInsert(
                        project_id=project_id,
                        id=call.id,
                        ended_at=ended_at,
                        output=output_json,
                        summary=summary,
                        exception=exception_str,
                    )
                )
            )

        self.future_executor.defer(send_end_call)

        call_context.pop_call(call.id)

    @trace_sentry.global_trace_sentry.watch()
    def fail_call(self, call: Call, exception: BaseException) -> None:
        """Fail a call with an exception. This is a convenience method for finish_call."""
        return self.finish_call(call, exception=exception)

    @trace_sentry.global_trace_sentry.watch()
    def delete_call(self, call: Call) -> None:
        self.server.calls_delete(
            CallsDeleteReq(
                project_id=self._project_id(),
                call_ids=[call.id],
            )
        )

    @trace_sentry.global_trace_sentry.watch()
    def delete_calls(self, call_ids: list[str]) -> None:
        """Delete calls by their IDs.

        Deleting a call will also delete all of its children.

        Args:
            call_ids: A list of call IDs to delete. Ex: ["2F0193e107-8fcf-7630-b576-977cc3062e2e"]
        """
        self.server.calls_delete(
            CallsDeleteReq(
                project_id=self._project_id(),
                call_ids=call_ids,
            )
        )

    @trace_sentry.global_trace_sentry.watch()
    def delete_object_version(self, object: ObjectRef) -> None:
        self.server.obj_delete(
            ObjDeleteReq(
                project_id=self._project_id(),
                object_id=object.name,
                digests=[object.digest],
            )
        )

    @trace_sentry.global_trace_sentry.watch()
    def delete_op_version(self, op: OpRef) -> None:
        self.server.obj_delete(
            ObjDeleteReq(
                project_id=self._project_id(),
                object_id=op.name,
                digests=[op.digest],
            )
        )

    def get_feedback(
        self,
        query: Query | str | None = None,
        *,
        reaction: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> FeedbackQuery:
        """Query project for feedback.

        Examples:
            ```python
            # Fetch a specific feedback object.
            # Note that this still returns a collection, which is expected
            # to contain zero or one item(s).
            client.get_feedback("1B4082A3-4EDA-4BEB-BFEB-2D16ED59AA07")

            # Find all feedback objects with a specific reaction.
            client.get_feedback(reaction="👍", limit=10)
            ```

        Args:
            query: A mongo-style query expression. For convenience, also accepts a feedback UUID string.
            reaction: For convenience, filter by a particular reaction emoji.
            offset: The offset to start fetching feedback objects from.
            limit: The maximum number of feedback objects to fetch.

        Returns:
            A FeedbackQuery object.
        """
        expr: dict[str, Any] = {
            "$eq": [
                {"$literal": "1"},
                {"$literal": "1"},
            ],
        }
        if isinstance(query, str):
            expr = {
                "$eq": [
                    {"$getField": "id"},
                    {"$literal": query},
                ],
            }
        elif isinstance(query, Query):
            expr = query.expr_.dict()

        if reaction:
            expr = {
                "$and": [
                    expr,
                    {
                        "$eq": [
                            {"$getField": "feedback_type"},
                            {"$literal": "wandb.reaction.1"},
                        ],
                    },
                    {
                        "$eq": [
                            {"$getField": "payload.emoji"},
                            {"$literal": reaction},
                        ],
                    },
                ]
            }
        rewritten_query = Query(**{"$expr": expr})

        return FeedbackQuery(
            entity=self.entity,
            project=self.project,
            query=rewritten_query,
            offset=offset,
            limit=limit,
            show_refs=True,
        )

    @deprecated(new_name="get_feedback")
    def feedback(
        self,
        query: Query | str | None = None,
        *,
        reaction: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> FeedbackQuery:
        return self.get_feedback(
            query=query, reaction=reaction, offset=offset, limit=limit
        )

    def add_cost(
        self,
        llm_id: str,
        prompt_token_cost: float,
        completion_token_cost: float,
        effective_date: datetime.datetime | None = datetime.datetime.now(
            datetime.timezone.utc
        ),
        prompt_token_cost_unit: str | None = "USD",
        completion_token_cost_unit: str | None = "USD",
        provider_id: str | None = "default",
    ) -> CostCreateRes:
        """Add a cost to the current project.

        Examples:

            ```python
            client.add_cost(llm_id="my_expensive_custom_model", prompt_token_cost=1, completion_token_cost=2)
            client.add_cost(llm_id="my_expensive_custom_model", prompt_token_cost=500, completion_token_cost=1000, effective_date=datetime(1998, 10, 3))
            ```

        Args:
            llm_id: The ID of the LLM. eg "gpt-4o-mini-2024-07-18"
            prompt_token_cost: The cost per prompt token. eg .0005
            completion_token_cost: The cost per completion token. eg .0015
            effective_date: Defaults to the current date. A datetime.datetime object.
            provider_id: The provider of the LLM. Defaults to "default". eg "openai"
            prompt_token_cost_unit: The unit of the cost for the prompt tokens. Defaults to "USD". (Currently unused, will be used in the future to specify the currency type for the cost eg "tokens" or "time")
            completion_token_cost_unit: The unit of the cost for the completion tokens. Defaults to "USD". (Currently unused, will be used in the future to specify the currency type for the cost eg "tokens" or "time")

        Returns:
            A CostCreateRes object.
            Which has one field called a list of tuples called ids.
            Each tuple contains the llm_id and the id of the created cost object.
        """
        cost = CostCreateInput(
            prompt_token_cost=prompt_token_cost,
            completion_token_cost=completion_token_cost,
            effective_date=effective_date,
            prompt_token_cost_unit=prompt_token_cost_unit,
            completion_token_cost_unit=completion_token_cost_unit,
            provider_id=provider_id,
        )
        return self.server.cost_create(
            CostCreateReq(project_id=self._project_id(), costs={llm_id: cost})
        )

    def purge_costs(self, ids: list[str] | str) -> None:
        """Purge costs from the current project.

        Examples:

            ```python
            client.purge_costs([ids])
            client.purge_costs(ids)
            ```

        Args:
            ids: The cost IDs to purge. Can be a single ID or a list of IDs.
        """
        if isinstance(ids, str):
            ids = [ids]
        expr = {
            "$in": [
                {"$getField": "id"},
                [{"$literal": id} for id in ids],
            ]
        }
        self.server.cost_purge(
            CostPurgeReq(project_id=self._project_id(), query=Query(**{"$expr": expr}))
        )

    def query_costs(
        self,
        query: Query | str | None = None,
        llm_ids: list[str] | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[CostQueryOutput]:
        """Query project for costs.

        Examples:

            ```python
            # Fetch a specific cost object.
            # Note that this still returns a collection, which is expected
            # to contain zero or one item(s).
            client.query_costs("1B4082A3-4EDA-4BEB-BFEB-2D16ED59AA07")

            # Find all cost objects with a specific reaction.
            client.query_costs(llm_ids=["gpt-4o-mini-2024-07-18"], limit=10)
            ```

        Args:
            query: A mongo-style query expression. For convenience, also accepts a cost UUID string.
            llm_ids: For convenience, filter for a set of llm_ids.
            offset: The offset to start fetching cost objects from.
            limit: The maximum number of cost objects to fetch.

        Returns:
            A CostQuery object.
        """
        expr: dict[str, Any] = {
            "$eq": [
                {"$literal": "1"},
                {"$literal": "1"},
            ],
        }
        if isinstance(query, str):
            expr = {
                "$eq": [
                    {"$getField": "id"},
                    {"$literal": query},
                ],
            }
        elif isinstance(query, Query):
            expr = query.expr_

        if llm_ids:
            expr = {
                "$and": [
                    expr,
                    {
                        "$in": [
                            {"$getField": "llm_id"},
                            [{"$literal": llm_id} for llm_id in llm_ids],
                        ],
                    },
                ]
            }
        rewritten_query = Query(**{"$expr": expr})

        res = self.server.cost_query(
            CostQueryReq(
                project_id=self._project_id(),
                query=rewritten_query,
                offset=offset,
                limit=limit,
            )
        )
        return res.results

    @trace_sentry.global_trace_sentry.watch()
    def _send_score_call(
        self,
        predict_call: Call,
        score_call: Call,
        scorer_object_ref_uri: str | None = None,
    ) -> Future[str]:
        """(Private) Adds a score to a call. This is particularly useful
        for adding evaluation metrics to a call.
        """

        def send_score_call() -> str:
            call_ref = get_ref(predict_call)
            if call_ref is None:
                raise ValueError("Predict call must have a ref")
            weave_ref_uri = call_ref.uri()
            scorer_call_ref = get_ref(score_call)
            if scorer_call_ref is None:
                raise ValueError("Score call must have a ref")
            scorer_call_ref_uri = scorer_call_ref.uri()

            # If scorer_object_ref_uri is provided, it is used as the runnable_ref_uri
            # Otherwise, we use the op_name from the score_call. This should happen
            # when there is a Scorer subclass that is the source of the score call.
            runnable_ref_uri = scorer_object_ref_uri or score_call.op_name
            score_results = score_call.output

            return self._add_runnable_feedback(
                weave_ref_uri=weave_ref_uri,
                output=score_results,
                call_ref_uri=scorer_call_ref_uri,
                runnable_ref_uri=runnable_ref_uri,
            )

        return self.future_executor.defer(send_score_call)

    @trace_sentry.global_trace_sentry.watch()
    def _add_runnable_feedback(
        self,
        *,
        weave_ref_uri: str,
        output: Any,
        call_ref_uri: str,
        runnable_ref_uri: str,
        # , supervision: dict
    ) -> str:
        """(Private) Low-level, non object-oriented method for adding a score to a call.

        Outstanding questions:
        - Should we somehow include supervision (ie. the ground truth) in the payload?
        """
        # Parse the refs (acts as validation)
        call_ref = parse_uri(weave_ref_uri)
        if not isinstance(call_ref, CallRef):
            raise TypeError(f"Invalid call ref: {weave_ref_uri}")
        scorer_call_ref = parse_uri(call_ref_uri)
        if not isinstance(scorer_call_ref, CallRef):
            raise TypeError(f"Invalid scorer call ref: {call_ref_uri}")
        runnable_ref = parse_uri(runnable_ref_uri)
        if not isinstance(runnable_ref, (OpRef, ObjectRef)):
            raise TypeError(f"Invalid scorer op ref: {runnable_ref_uri}")

        # Prepare the result payload - we purposely do not map to refs here
        # because we prefer to have the raw data.
        results_json = to_json(output, self._project_id(), self)

        # # Prepare the supervision payload

        payload = {
            "output": results_json,
        }

        freq = FeedbackCreateReq(
            project_id=self._project_id(),
            weave_ref=weave_ref_uri,
            feedback_type=RUNNABLE_FEEDBACK_TYPE_PREFIX + "." + runnable_ref.name,
            payload=payload,
            runnable_ref=runnable_ref_uri,
            call_ref=call_ref_uri,
        )
        response = self.server.feedback_create(freq)

        return response.id

    ################# Object Saving ##################
    # `_save_object` is the top level entry point for saving data to the weave server.
    # `_save_nested_objects` is a recursive method to dispatch saving of nested objects.
    #  it is called by `_save_object` above, as well as `create_call` and `finish_call`
    #  since we don't save the entire dictionary, but rather want to save any nested objects
    # `_save_object_basic` is the lowest level object saving logic which:
    #  - serializes the object to json
    #  - calls the server to save the object
    #  - creates an ObjectRef and attaches it to the object
    # `_save_op` and `_save_table` are the sister functions to `_save_object_basic`
    #  but for Ops and Tables respectively.

    @trace_sentry.global_trace_sentry.watch()
    def _save_object(self, val: Any, name: str, branch: str = "latest") -> ObjectRef:
        """Save an object to the weave server and return it's Ref. This is the top
        level entry point for saving any data to the weave server. Importantly, it
        will also save all children objects that are "Refable".

        Args:
            val: The object to save.
            name: The name to save the object under.
            branch: The branch to save the object under. Defaults to "latest".

        Returns:
            An ObjectRef to the saved object.
        """
        if isinstance(val, WeaveTable):
            # TODO: Probably should error here
            pass

        # If it's an Op, use the Op saving logic
        if is_op(val):
            # TODO: Probably should call _save_op directly here (or error)
            pass

        # Step 1: Recursively save all nested objects
        self._save_nested_objects(val, name=name)

        # Step 2: Save the object itself
        return self._save_object_basic(val, name, branch)

    @trace_sentry.global_trace_sentry.watch()
    def _save_nested_objects(self, obj: Any, name: str | None = None) -> Any:
        """Recursively visits all values, ensuring that any "Refable" objects are
        saved and reffed.
        As of this writing, the only "Refable" objects are instances of:
        - weave.flow.obj.Object
        - weave.trace.op.Op
        - weave.trace.Table
        - weave.trace.vals.WeaveTable
        This procedure is a bit complicated, so it is worth making the details explicit:
        1. If the `obj` value already has a `ref`:
            - If the ref is to the current project, do nothing.
            - If the ref is to a different project, remove it. (to avoid cross-project references)
        2. If the `obj` value can be "reffed" (according to one of the above cases), invoke
            the appropriate "save" function for that type of object, and attach the ref result to `obj`.
            - `_save_object_basic` (for `weave.flow.obj.Object` instances)
            - `_save_op` (for `weave.trace.op.Op` instances)
            - `_save_table` (for `weave.trace.Table` and `weave.trace.vals.WeaveTable` instances)
        3. Otherwise, traverse all values within `obj` recursively, applying the above logic to each value.
        Important notes to developers: This method does not return anything - it _mutates_ the
        values that it traverses (specifically, it attaches `ref` values to them)

        Important: This method calls low level save methods directly - causing network events. Until
        these are backgrounded, they should not be invoked from inside a critical path.
        """
        # Base case: if the object is already refed
        #  - if the ref is to a different project, remove it
        #  - if the ref is to the current project, do nothing
        if (ref := get_ref(obj)) is not None:
            if ALLOW_MIXED_PROJECT_REFS:
                return
            # Check if existing ref is to current project, if not,
            # remove the ref and recreate it in the current project
            if ref.project == self.project:
                return
            remove_ref(obj)
        # Must defer import here to avoid circular import
        from weave.flow.obj import Object

        # Case 1: Object:
        # Here we recurse into each of the properties of the object
        # and save them, and then save the object itself.
        if isinstance(obj, Object):
            obj_rec = pydantic_object_record(obj)
            for v in obj_rec.__dict__.values():
                self._save_nested_objects(v)
            ref = self._save_object_basic(obj_rec, name or get_obj_name(obj_rec))
            # Personally, i think we should be passing `obj` into _save_object_basic,
            # and letting `to_json` handle converting the pydantic object into a jsonable object
            # but that might have unintended consequences. As a result, we break the
            # typical pattern and explicitly set the ref here.
            set_ref(obj, ref)

        # Case 2: Op:
        # Here we save the op itself.
        elif is_op(obj):
            # Ref is attached in here
            self._save_op(obj)

        # Case 3: Table
        elif isinstance(obj, Table):
            self._save_table(obj)

        # Case 4: WeaveTable
        elif isinstance(obj, WeaveTable):
            self._save_table(obj)

        # Special case: Custom recursive handling for WeaveObject with rows
        # TODO: Kinda hacky way to dispatching Dataset with rows: Table
        elif isinstance(obj, WeaveObject) and hasattr(obj, "rows"):
            self._save_nested_objects(obj.rows)

        # Recursive traversal of other pydantic objects
        elif isinstance(obj, (pydantic.BaseModel, pydantic.v1.BaseModel)):
            obj_rec = pydantic_object_record(obj)
            for v in obj_rec.__dict__.values():
                self._save_nested_objects(v)

        # Recursive traversal of other dataclasses
        elif dataclasses.is_dataclass(obj) and not isinstance(obj, Ref):
            obj_rec = dataclass_object_record(obj)
            for v in obj_rec.__dict__.values():
                self._save_nested_objects(v)

        # Recursive traversal of python structures
        elif isinstance_namedtuple(obj):
            for v in obj._asdict().values():
                self._save_nested_objects(v)
        elif isinstance(obj, (list, tuple)):
            for v in obj:
                self._save_nested_objects(v)
        elif isinstance(obj, dict):
            for v in obj.values():
                self._save_nested_objects(v)

    @trace_sentry.global_trace_sentry.watch()
    def _save_object_basic(
        self, val: Any, name: str | None = None, branch: str = "latest"
    ) -> ObjectRef:
        """Directly saves an object to the weave server and attach
        the ref to the object. This is the lowest level object saving logic.
        """
        orig_val = val

        # The WeaveTable case is special because object saving happens inside
        # _save_object_nested and it has a special table_ref -- skip it here.
        if getattr(val, "_is_dirty", False) and not isinstance(val, WeaveTable):
            val.ref = None

        val = map_to_refs(val)
        if isinstance(val, ObjectRef):
            if ALLOW_MIXED_PROJECT_REFS:
                return val
            # Check if existing ref is to current project, if not,
            # remove the ref and recreate it in the current project
            if val.project == self.project:
                return val
            val = orig_val

        if name is None:
            serializer = get_serializer_for_obj(val)
            if serializer:
                name = serializer.id()

        if name is None:
            raise ValueError("Name must be provided for object saving")

        name = sanitize_object_name(name)

        def send_obj_create() -> ObjCreateRes:
            # `to_json` is mostly fast, except for CustomWeaveTypes
            # which incur network costs to serialize the payload
            json_val = to_json(val, self._project_id(), self)
            req = ObjCreateReq(
                obj=ObjSchemaForInsert(
                    project_id=self.entity + "/" + self.project,
                    object_id=name,
                    val=json_val,
                )
            )
            return self.server.obj_create(req)

        res_future: Future[ObjCreateRes] = self.future_executor.defer(send_obj_create)
        digest_future: Future[str] = self.future_executor.then(
            [res_future], lambda res: res[0].digest
        )

        ref: Ref
        if is_op(orig_val):
            ref = OpRef(self.entity, self.project, name, digest_future)
        else:
            ref = ObjectRef(self.entity, self.project, name, digest_future)

        # Attach the ref to the object
        try:
            set_ref(orig_val, ref)
        except Exception:
            # Don't worry if we can't set the ref.
            # This can happen for primitive types that don't have __dict__
            pass

        return ref

    @trace_sentry.global_trace_sentry.watch()
    def _save_op(self, op: Op, name: str | None = None) -> ObjectRef:
        """
        Saves an Op to the weave server and returns the Ref. This is the sister
        function to _save_object_basic, but for Ops
        """
        if name is None:
            name = op.name

        return self._save_object_basic(op, name)

    @trace_sentry.global_trace_sentry.watch()
    def _save_table(self, table: Table | WeaveTable) -> TableRef:
        """Saves a Table to the weave server and returns the TableRef.
        This is the sister function to _save_object_basic but for Tables.
        """
        # Skip saving the table if it is already persisted.
        if isinstance(table, WeaveTable) and table.table_ref is not None:
            return table.table_ref

        def send_table_create() -> TableCreateRes:
            rows = to_json(table.rows, self._project_id(), self)
            req = TableCreateReq(
                table=TableSchemaForInsert(project_id=self._project_id(), rows=rows)
            )
            return self.server.table_create(req)

        res_future: Future[TableCreateRes] = self.future_executor.defer(
            send_table_create
        )

        digest_future: Future[str] = self.future_executor.then(
            [res_future], lambda res: res[0].digest
        )
        row_digests_future: Future[list[str]] = self.future_executor.then(
            [res_future], lambda res: res[0].row_digests
        )

        table_ref = TableRef(
            self.entity, self.project, digest_future, row_digests_future
        )

        table.ref = table_ref

        if isinstance(table, WeaveTable):
            table.table_ref = table_ref

        return table_ref

    def _append_to_table(self, table_digest: str, rows: list[dict]) -> WeaveTable:
        payloads = [TableAppendSpecPayload(row=row) for row in rows]
        table_update_req = TableUpdateReq(
            project_id=self._project_id(),
            base_digest=table_digest,
            updates=[TableAppendSpec(append=payload) for payload in payloads],
        )
        res = self.server.table_update(table_update_req)
        return WeaveTable(
            table_ref=TableRef(
                entity=self.entity,
                project=self.project,
                _digest=res.digest,
            ),
            server=self.server,
        )

    ################ Internal Helpers ################

    def _ref_is_own(self, ref: Ref) -> bool:
        return isinstance(ref, Ref)

    def _project_id(self) -> str:
        return f"{self.entity}/{self.project}"

    @trace_sentry.global_trace_sentry.watch()
    def _op_calls(self, op: Op) -> CallsIter:
        op_ref = get_ref(op)
        if op_ref is None:
            raise ValueError(f"Can't get runs for unpublished op: {op}")
        return self.get_calls(filter=CallsFilter(op_names=[op_ref.uri()]))

    @trace_sentry.global_trace_sentry.watch()
    def _objects(self, filter: ObjectVersionFilter | None = None) -> list[ObjSchema]:
        if not filter:
            filter = ObjectVersionFilter()
        else:
            filter = filter.model_copy()
        filter = cast(ObjectVersionFilter, filter)
        filter.is_op = False

        response = self.server.objs_query(
            ObjQueryReq(
                project_id=self._project_id(),
                filter=filter,
            )
        )
        return response.objs

    @trace_sentry.global_trace_sentry.watch()
    def _set_call_display_name(
        self, call: Call, display_name: str | None = None
    ) -> None:
        # Removing call display name, use "" for db representation
        if display_name is None:
            display_name = ""
        self.server.call_update(
            CallUpdateReq(
                project_id=self._project_id(),
                call_id=call.id,
                display_name=elide_display_name(display_name),
            )
        )

    def _remove_call_display_name(self, call: Call) -> None:
        self._set_call_display_name(call, None)

    def _ref_output_of(self, ref: ObjectRef) -> Call | None:
        raise NotImplementedError()

    def _op_runs(self, op_def: Op) -> Sequence[Call]:
        raise NotImplementedError()

    def _ref_uri(self, name: str, version: str, path: str) -> str:
        return ObjectRef(self.entity, self.project, name, version).uri()

    def _send_file_create(self, req: FileCreateReq) -> Future[FileCreateRes]:
        cached_res = self.send_file_cache.get(req)
        if cached_res:
            return cached_res

        if self.future_executor_fastlane:
            # If we have a separate upload worker pool, use it
            res = self.future_executor_fastlane.defer(self.server.file_create, req)
        else:
            res = self.future_executor.defer(self.server.file_create, req)

        self.send_file_cache.put(req, res)
        return res

    @property
    def num_outstanding_jobs(self) -> int:
        """
        Returns the total number of pending jobs across all executors and the server.

        This property can be used to check the progress of background tasks
        without blocking the main thread.

        Returns:
            int: The total number of pending jobs
        """
        total = self.future_executor.num_outstanding_futures
        if self.future_executor_fastlane:
            total += self.future_executor_fastlane.num_outstanding_futures

        # Add call batch uploads if available
        if self._server_is_flushable:
            server = cast(RemoteHTTPTraceServer, self.server)
            assert server.call_processor is not None
            total += server.call_processor.num_outstanding_jobs
        return total

    def finish(
        self,
        use_progress_bar: bool = True,
        callback: Callable[[FlushStatus], None] | None = None,
    ) -> None:
        """
        Flushes all background tasks to ensure they are processed.

        This method blocks until all currently enqueued jobs are processed,
        displaying a progress bar to show the status of the pending tasks.
        It ensures parallel processing during main thread execution and can
        improve performance when user code completes before data has been
        uploaded to the server.

        Args:
            use_progress_bar: Whether to display a progress bar during flush.
                              Set to False for environments where a progress bar
                              would not render well (e.g., CI environments).
            callback: Optional callback function that receives status updates.
                      Overrides use_progress_bar.
        """
        if use_progress_bar and callback is None:
            from weave.trace.client_progress_bar import create_progress_bar_callback

            callback = create_progress_bar_callback()

        if callback is not None:
            self._flush_with_callback(callback=callback)
        else:
            self._flush()

    def flush(self) -> None:
        """Flushes background asynchronous tasks, safe to call multiple times."""
        self._flush()

    def _flush_with_callback(
        self,
        callback: Callable[[FlushStatus], None],
        refresh_interval: float = 0.1,
    ) -> None:
        """Used to wait until all currently enqueued jobs are processed.

        Args:
            callback: Optional callback function that receives status updates.
            refresh_interval: Time in seconds between status updates.
        """
        # Initialize tracking variables
        prev_job_counts = self._get_pending_jobs()

        total_completed = 0
        while self._has_pending_jobs():
            current_job_counts = self._get_pending_jobs()

            # If new jobs were added, update the total
            if (
                current_job_counts["total_jobs"]
                > prev_job_counts["total_jobs"] - total_completed
            ):
                new_jobs = current_job_counts["total_jobs"] - (
                    prev_job_counts["total_jobs"] - total_completed
                )
                prev_job_counts["total_jobs"] += new_jobs

            # Calculate completed jobs since last update
            main_completed = max(
                0, prev_job_counts["main_jobs"] - current_job_counts["main_jobs"]
            )
            fastlane_completed = max(
                0,
                prev_job_counts["fastlane_jobs"] - current_job_counts["fastlane_jobs"],
            )
            call_processor_completed = max(
                0,
                prev_job_counts["call_processor_jobs"]
                - current_job_counts["call_processor_jobs"],
            )
            completed_this_iteration = (
                main_completed + fastlane_completed + call_processor_completed
            )

            if completed_this_iteration > 0:
                total_completed += completed_this_iteration

            status = FlushStatus(
                job_counts=current_job_counts,
                completed_since_last_update=completed_this_iteration,
                total_completed=total_completed,
                max_total_jobs=prev_job_counts["total_jobs"],
                has_pending_jobs=True,
            )

            callback(status)

            # Store current counts for next iteration
            prev_job_counts = current_job_counts

            # Sleep briefly to allow background threads to make progress
            time.sleep(refresh_interval)

        # Do the actual flush
        self._flush()

        # Final callback with no pending jobs
        final_status = FlushStatus(
            job_counts=PendingJobCounts(
                main_jobs=0,
                fastlane_jobs=0,
                call_processor_jobs=0,
                total_jobs=0,
            ),
            completed_since_last_update=0,
            total_completed=total_completed,
            max_total_jobs=prev_job_counts["total_jobs"],
            has_pending_jobs=False,
        )
        callback(final_status)

    def _flush(self) -> None:
        """Used to wait until all currently enqueued jobs are processed."""
        if not self.future_executor._in_thread_context.get():
            self.future_executor.flush()
        if self.future_executor_fastlane:
            self.future_executor_fastlane.flush()
        if self._server_is_flushable:
            # We don't want to do an instance check here because it could
            # be susceptible to shutdown race conditions. So we save a boolean
            # _server_is_flushable and only call this if we know the server is
            # flushable.
            server = cast(RemoteHTTPTraceServer, self.server)
            assert server.call_processor is not None
            server.call_processor.stop_accepting_new_work_and_flush_queue()

            # Restart call processor processing thread after flushing
            server.call_processor.accept_new_work()

    def _get_pending_jobs(self) -> PendingJobCounts:
        """Get the current number of pending jobs for each type.

        Returns:
            PendingJobCounts:
                - main_jobs: Number of pending jobs in the main executor
                - fastlane_jobs: Number of pending jobs in the fastlane executor
                - call_processor_jobs: Number of pending jobs in the call processor
                - total_jobs: Total number of pending jobs
        """
        main_jobs = self.future_executor.num_outstanding_futures
        fastlane_jobs = 0
        if self.future_executor_fastlane:
            fastlane_jobs = self.future_executor_fastlane.num_outstanding_futures
        call_processor_jobs = 0
        if self._server_is_flushable:
            server = cast(RemoteHTTPTraceServer, self.server)
            assert server.call_processor is not None
            call_processor_jobs = server.call_processor.num_outstanding_jobs

        return PendingJobCounts(
            main_jobs=main_jobs,
            fastlane_jobs=fastlane_jobs,
            call_processor_jobs=call_processor_jobs,
            total_jobs=main_jobs + fastlane_jobs + call_processor_jobs,
        )

    def _has_pending_jobs(self) -> bool:
        """Check if there are any pending jobs.

        Returns:
            True if there are pending jobs, False otherwise.
        """
        return self._get_pending_jobs()["total_jobs"] > 0


class PendingJobCounts(TypedDict):
    """Counts of pending jobs for each type."""

    main_jobs: int
    fastlane_jobs: int
    call_processor_jobs: int
    total_jobs: int


class FlushStatus(TypedDict):
    """Status information about the current flush operation."""

    # Current job counts
    job_counts: PendingJobCounts

    # Tracking of completed jobs
    completed_since_last_update: int
    total_completed: int

    # Maximum number of jobs seen during this flush operation
    max_total_jobs: int

    # Whether there are any pending jobs
    has_pending_jobs: bool


def get_parallelism_settings() -> tuple[int | None, int | None]:
    total_parallelism = client_parallelism()

    # if user has explicitly set 0 or 1 for total parallelism,
    # don't use fastlane executor
    if total_parallelism is not None and total_parallelism <= 1:
        return total_parallelism, 0

    # if total_parallelism is None, calculate it
    if total_parallelism is None:
        total_parallelism = min(32, (os.cpu_count() or 1) + 4)

    # use 50/50 split between main and fastlane
    parallelism_main = int(total_parallelism * (1 - BACKGROUND_PARALLELISM_MIX))
    parallelism_fastlane = total_parallelism - parallelism_main

    return parallelism_main, parallelism_fastlane


def safe_current_wb_run_id() -> str | None:
    try:
        import wandb

        wandb_run = wandb.run
        if wandb_run is None:
            return None
    except ImportError:
        return None
    else:
        return f"{wandb_run.entity}/{wandb_run.project}/{wandb_run.id}"


def check_wandb_run_matches(
    wandb_run_id: str | None, weave_entity: str, weave_project: str
) -> None:
    if wandb_run_id:
        # ex: "entity/project/run_id"
        wandb_entity, wandb_project, _ = wandb_run_id.split("/")
        if wandb_entity != weave_entity or wandb_project != weave_project:
            raise ValueError(
                f'Project Mismatch: weave and wandb must be initialized using the same project. Found wandb.init targeting project "{wandb_entity}/{wandb_project}" and weave.init targeting project "{weave_entity}/{weave_project}". To fix, please use the same project for both library initializations.'
            )


def _build_anonymous_op(name: str, config: dict | None = None) -> Op:
    if config is None:

        def op_fn(*args, **kwargs):  # type: ignore
            # Code-capture unavailable for this op
            pass

    else:

        def op_fn(*args, **kwargs):  # type: ignore
            # Code-capture unavailable for this op
            op_config = config

    op_fn.__name__ = name
    op = op_deco(op_fn)
    op = as_op(op)
    op.name = name
    return op


def redact_sensitive_keys(obj: Any) -> Any:
    # We should NEVER mutate reffed objects.
    #
    # 1. This code builds new objects that no longer have refs
    # 2. Even if we did an in-place edit, that would invalidate the ref (since
    # the ref is to the object's digest)
    if get_ref(obj):
        return obj

    if isinstance(obj, dict):
        dict_res = {}
        for k, v in obj.items():
            if isinstance(k, str) and should_redact(k):
                dict_res[k] = REDACTED_VALUE
            else:
                dict_res[k] = redact_sensitive_keys(v)
        return dict_res

    elif isinstance(obj, list):
        list_res = []
        for v in obj:
            list_res.append(redact_sensitive_keys(v))
        return list_res

    elif isinstance(obj, tuple):
        tuple_res = []
        for v in obj:
            tuple_res.append(redact_sensitive_keys(v))
        return tuple(tuple_res)

    return obj


def sanitize_object_name(name: str) -> str:
    # Replaces any non-alphanumeric characters with a single dash and removes
    # any leading or trailing dashes. This is more restrictive than the DB
    # constraints and can be relaxed if needed.
    res = re.sub(r"([._-]{2,})+", "-", re.sub(r"[^\w._]+", "-", name)).strip("-_")
    if not res:
        raise ValueError(f"Invalid object name: {name}")
    if len(res) > MAX_OBJECT_NAME_LENGTH:
        res = res[:MAX_OBJECT_NAME_LENGTH]
    return res


def elide_display_name(name: str) -> str:
    if len(name) > MAX_DISPLAY_NAME_LENGTH:
        log_once(
            logger.warning,
            f"Display name {name} is longer than {MAX_DISPLAY_NAME_LENGTH} characters.  It will be truncated!",
        )
        return name[: MAX_DISPLAY_NAME_LENGTH - 3] + "..."
    return name


__docspec__ = [WeaveClient, Call, CallsIter]
