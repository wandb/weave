import dataclasses
import datetime
import platform
import re
import sys
import typing
from functools import lru_cache
from typing import Any, Dict, Iterator, Optional, Sequence, Union

import pydantic
from requests import HTTPError

from weave import version
from weave.legacy.weave import ref_base, urls
from weave.trace import call_context, trace_sentry
from weave.trace.client_context import weave_client as weave_client_context
from weave.trace.exception import exception_to_json_str
from weave.trace.feedback import FeedbackQuery, RefFeedbackQuery
from weave.trace.object_record import (
    ObjectRecord,
    dataclass_object_record,
    pydantic_object_record,
)
from weave.trace.op import Op, maybe_unbind_method
from weave.trace.op import op as op_deco
from weave.trace.refs import CallRef, ObjectRef, OpRef, Ref, TableRef
from weave.trace.serialize import from_json, isinstance_namedtuple, to_json
from weave.trace.serializer import get_serializer_for_obj
from weave.trace.table import Table
from weave.trace.util import deprecated
from weave.trace.vals import WeaveObject, WeaveTable, make_trace_obj
from weave.trace_server.ids import generate_id
from weave.trace_server.trace_server_interface import (
    CallEndReq,
    CallSchema,
    CallsDeleteReq,
    CallsFilter,
    CallsQueryReq,
    CallStartReq,
    CallUpdateReq,
    EndedCallSchemaForInsert,
    ObjCreateReq,
    ObjectVersionFilter,
    ObjQueryReq,
    ObjReadReq,
    ObjSchema,
    ObjSchemaForInsert,
    Query,
    RefsReadBatchReq,
    StartedCallSchemaForInsert,
    TableCreateReq,
    TableSchemaForInsert,
    TraceServerInterface,
)

# Controls if objects can have refs to projects not the WeaveClient project.
# If False, object refs with with mismatching projects will be recreated.
# If True, use existing ref to object in other project.
ALLOW_MIXED_PROJECT_REFS = False


def dataclasses_asdict_one_level(obj: Any) -> typing.Dict[str, Any]:
    # dataclasses.asdict is recursive. We don't want that when json encoding
    return {f.name: getattr(obj, f.name) for f in dataclasses.fields(obj)}


# TODO: unused


def get_obj_name(val: Any) -> str:
    name = getattr(val, "name", None)
    if name is None:
        if isinstance(val, ObjectRecord):
            name = val._class_name
        else:
            name = f"{val.__class__.__name__}"
    if not isinstance(name, str):
        raise ValueError(f"Object's name attribute is not a string: {name}")
    return name


def get_ref(obj: Any) -> Optional[ObjectRef]:
    return getattr(obj, "ref", None)


def remove_ref(obj: Any) -> None:
    if get_ref(obj) is not None:
        if "ref" in obj.__dict__:  # for methods
            obj.__dict__["ref"] = None
        else:
            obj.ref = None


def _get_direct_ref(obj: Any) -> Optional[Ref]:
    if isinstance(obj, WeaveTable):
        # TODO: this path is odd. We want to use table_ref when serializing
        # which is the direct ref to the table. But .ref on WeaveTable is
        # the "container ref", ie a ref to the root object that the WeaveTable
        # is within, with extra pointing to the table.
        return obj.table_ref
    return getattr(obj, "ref", None)


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
    elif isinstance(obj, list):
        return [map_to_refs(v) for v in obj]
    elif isinstance(obj, dict):
        return {k: map_to_refs(v) for k, v in obj.items()}

    # This path should only be reached if the object is both:
    # 1. A `WeaveObject`; and
    # 2. Has been dirtied (edited in any way), causing obj.ref=None
    elif isinstance(obj, WeaveObject):
        return map_to_refs(obj._val)

    return obj


@dataclasses.dataclass
class Call:
    op_name: str
    trace_id: str
    project_id: str
    parent_id: Optional[str]
    inputs: dict
    id: Optional[str] = None
    output: Any = None
    exception: Optional[str] = None
    summary: Optional[dict] = None
    display_name: Optional[str] = None
    attributes: Optional[dict] = None
    started_at: Optional[datetime.datetime] = None
    ended_at: Optional[datetime.datetime] = None
    deleted_at: Optional[datetime.datetime] = None
    # These are the live children during logging
    _children: list["Call"] = dataclasses.field(default_factory=list)

    _feedback: Optional[RefFeedbackQuery] = None

    @property
    def feedback(self) -> RefFeedbackQuery:
        if not self.id:
            raise ValueError("Can't get feedback for call without ID")
        if self._feedback is None:
            project_parts = self.project_id.split("/")
            if len(project_parts) != 2:
                raise ValueError(f"Invalid project_id: {self.project_id}")
            entity, project = project_parts
            weave_ref = CallRef(entity, project, self.id)
            self._feedback = RefFeedbackQuery(weave_ref.uri())
        return self._feedback

    @property
    def ui_url(self) -> str:
        project_parts = self.project_id.split("/")
        if len(project_parts) != 2:
            raise ValueError(f"Invalid project_id: {self.project_id}")
        entity, project = project_parts
        if not self.id:
            raise ValueError("Can't get URL for call without ID")
        return urls.redirect_call(entity, project, self.id)

    # These are the children if we're using Call at read-time
    def children(self) -> "CallsIter":
        client = weave_client_context.require_weave_client()
        if not self.id:
            raise ValueError("Can't get children of call without ID")
        return CallsIter(
            client.server,
            self.project_id,
            CallsFilter(parent_ids=[self.id]),
        )

    def delete(self) -> bool:
        client = weave_client_context.require_weave_client()
        return client.delete_call(call=self)

    def set_display_name(self, name: Optional[str]) -> None:
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


class CallsIter:
    server: TraceServerInterface
    filter: CallsFilter
    include_costs: bool

    def __init__(
        self,
        server: TraceServerInterface,
        project_id: str,
        filter: CallsFilter,
        include_costs: bool = False,
    ) -> None:
        self.server = server
        self.project_id = project_id
        self.filter = filter
        self._page_size = 1000
        self.include_costs = include_costs

    # seems like this caching should be on the server, but it's here for now...
    @lru_cache
    def _fetch_page(self, index: int) -> list[CallSchema]:
        # caching in here means that any other CallsIter objects would also
        # benefit from the cache
        response = self.server.calls_query(
            CallsQueryReq(
                project_id=self.project_id,
                filter=self.filter,
                offset=index * self._page_size,
                limit=self._page_size,
                include_costs=self.include_costs,
            )
        )
        return response.calls

    def _get_one(self, index: int) -> WeaveObject:
        if index < 0:
            raise IndexError("Negative indexing not supported")

        page_index = index // self._page_size
        page_offset = index % self._page_size

        calls = self._fetch_page(page_index)
        if page_offset >= len(calls):
            raise IndexError(f"Index {index} out of range")

        call = calls[page_offset]
        entity, project = self.project_id.split("/")
        return make_client_call(entity, project, call, self.server)

    def _get_slice(self, key: slice) -> Iterator[WeaveObject]:
        if (start := key.start or 0) < 0:
            raise ValueError("Negative start not supported")
        if (stop := key.stop) is not None and stop < 0:
            raise ValueError("Negative stop not supported")
        if (step := key.step or 1) < 0:
            raise ValueError("Negative step not supported")

        i = start
        while stop is None or i < stop:
            try:
                yield self._get_one(i)
            except IndexError:
                break
            i += step

    def __getitem__(
        self, key: Union[slice, int]
    ) -> Union[WeaveObject, list[WeaveObject]]:
        if isinstance(key, slice):
            return list(self._get_slice(key))
        return self._get_one(key)

    def __iter__(self) -> typing.Iterator[WeaveObject]:
        return self._get_slice(slice(0, None, 1))


def make_client_call(
    entity: str, project: str, server_call: CallSchema, server: TraceServerInterface
) -> WeaveObject:
    output = server_call.output
    call = Call(
        op_name=server_call.op_name,
        project_id=server_call.project_id,
        trace_id=server_call.trace_id,
        parent_id=server_call.parent_id,
        id=server_call.id,
        inputs=from_json(server_call.inputs, server_call.project_id, server),
        output=from_json(output, server_call.project_id, server),
        summary=dict(server_call.summary) if server_call.summary is not None else None,
        display_name=server_call.display_name,
        attributes=server_call.attributes,
        started_at=server_call.started_at,
        ended_at=server_call.ended_at,
        deleted_at=server_call.deleted_at,
    )
    if call.id is None:
        raise ValueError("Call ID is None")
    return WeaveObject(call, CallRef(entity, project, call.id), server, None)


def sum_dict_leaves(dicts: list[dict]) -> dict:
    # dicts is a list of dictionaries, that may or may not
    # have nested dictionaries. Sum all the leaves that match
    result: dict = {}
    for d in dicts:
        for k, v in d.items():
            if isinstance(v, dict):
                result[k] = sum_dict_leaves([result.get(k, {}), v])
            else:
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


class WeaveClient:
    server: TraceServerInterface

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
        self.ensure_project_exists = ensure_project_exists

        if ensure_project_exists:
            resp = self.server.ensure_project_exists(entity, project)
            # Set Client project name with updated project name
            self.project = resp.project_name

    ################ High Level Convenience Methods ################

    @trace_sentry.global_trace_sentry.watch()
    def save(self, val: Any, name: str, branch: str = "latest") -> Any:
        ref = self._save_object(val, name, branch)
        if not isinstance(ref, ObjectRef):
            raise ValueError(f"Expected ObjectRef, got {ref}")
        return self.get(ref)

    @trace_sentry.global_trace_sentry.watch()
    def get(self, ref: ObjectRef) -> Any:
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
            if e.response is not None and e.response.status_code == 404:
                raise ValueError(f"Unable to find object for ref uri: {ref.uri()}")
            raise

        # At this point, `ref.digest` is one of three things:
        # 1. "latest" - the user asked for the latest version of the object
        # 2. "v###" - the user asked for a specific version of the object
        # 3. The actual digest.
        #
        # However, we always want to resolve the ref to the digest. So
        # here, we just directly assign the digest.
        ref = dataclasses.replace(ref, digest=read_res.obj.digest)

        data = read_res.obj.val

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

        val = from_json(data, project_id, self.server)

        return make_trace_obj(val, ref, self.server, None)

    ################ Query API ################

    @trace_sentry.global_trace_sentry.watch()
    def get_calls(
        self,
        filter: Optional[CallsFilter] = None,
        include_costs: Optional[bool] = False,
    ) -> CallsIter:
        if filter is None:
            filter = CallsFilter()

        return CallsIter(
            self.server, self._project_id(), filter, include_costs or False
        )

    @deprecated(new_name="get_calls")
    def calls(
        self,
        filter: Optional[CallsFilter] = None,
        include_costs: Optional[bool] = False,
    ) -> CallsIter:
        return self.get_calls(filter=filter, include_costs=include_costs)

    @trace_sentry.global_trace_sentry.watch()
    def get_call(
        self, call_id: str, include_costs: Optional[bool] = False
    ) -> WeaveObject:
        response = self.server.calls_query(
            CallsQueryReq(
                project_id=self._project_id(),
                filter=CallsFilter(call_ids=[call_id]),
                include_costs=include_costs,
            )
        )
        if not response.calls:
            raise ValueError(f"Call not found: {call_id}")
        response_call = response.calls[0]
        return make_client_call(self.entity, self.project, response_call, self.server)

    @deprecated(new_name="get_call")
    def cll(self, call_id: str, include_costs: Optional[bool] = False) -> WeaveObject:
        return self.get_call(call_id=call_id, include_costs=include_costs)

    @trace_sentry.global_trace_sentry.watch()
    def create_call(
        self,
        op: Union[str, Op],
        inputs: dict,
        parent: Optional[Call] = None,
        attributes: Optional[dict] = None,
        display_name: Optional[str] = None,
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
        if isinstance(op, str):
            if op not in self._anonymous_ops:
                self._anonymous_ops[op] = _build_anonymous_op(op)
            op = self._anonymous_ops[op]
        if isinstance(op, Op):
            unbound_op = maybe_unbind_method(op)
            op_def_ref = self._save_op(unbound_op)
            op_str = op_def_ref.uri()
        else:
            op_str = op

        inputs_redacted = redact_sensitive_keys(inputs)

        self._save_nested_objects(inputs_redacted)
        inputs_with_refs = map_to_refs(inputs_redacted)
        call_id = generate_id()

        if parent is None and use_stack:
            parent = call_context.get_current_call()

        if parent:
            trace_id = parent.trace_id
            parent_id = parent.id
        else:
            trace_id = generate_id()
            parent_id = None

        if attributes is None:
            attributes = {}

        attributes = AttributesDict(**attributes)
        attributes._set_weave_item("client_version", version.VERSION)
        attributes._set_weave_item("source", "python-sdk")
        attributes._set_weave_item("os_name", platform.system())
        attributes._set_weave_item("os_version", platform.version())
        attributes._set_weave_item("os_release", platform.release())
        attributes._set_weave_item("sys_version", sys.version)

        call = Call(
            op_name=op_str,
            project_id=self._project_id(),
            trace_id=trace_id,
            parent_id=parent_id,
            id=call_id,
            inputs=inputs_with_refs,
            display_name=display_name,
            attributes=attributes,
        )
        if parent is not None:
            parent._children.append(call)

        current_wb_run_id = safe_current_wb_run_id()
        check_wandb_run_matches(current_wb_run_id, self.entity, self.project)
        start = StartedCallSchemaForInsert(
            project_id=self._project_id(),
            id=call_id,
            op_name=op_str,
            display_name=display_name,
            trace_id=trace_id,
            started_at=datetime.datetime.now(tz=datetime.timezone.utc),
            parent_id=parent_id,
            inputs=to_json(inputs_with_refs, self._project_id(), self.server),
            attributes=attributes,
            wb_run_id=current_wb_run_id,
        )
        self.server.call_start(CallStartReq(start=start))

        if use_stack:
            call_context.push_call(call)

        return call

    @trace_sentry.global_trace_sentry.watch()
    def finish_call(
        self, call: Call, output: Any = None, exception: Optional[BaseException] = None
    ) -> None:
        self._save_nested_objects(output)
        original_output = output
        output = map_to_refs(original_output)
        call.output = output

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

        # Exception Handling
        exception_str: Optional[str] = None
        if exception:
            exception_str = exception_to_json_str(exception)
            call.exception = exception_str

        self.server.call_end(
            CallEndReq(
                end=EndedCallSchemaForInsert(
                    project_id=self._project_id(),
                    id=call.id,  # type: ignore
                    ended_at=datetime.datetime.now(tz=datetime.timezone.utc),
                    output=to_json(output, self._project_id(), self.server),
                    summary=summary,
                    exception=exception_str,
                )
            )
        )

        # Descendent error tracking disabled til we fix UI
        # Add this call's summary after logging the call, so that only
        # descendents are included in what we log
        # summary.setdefault("descendants", {}).setdefault(
        #     call.op_name, {"successes": 0, "errors": 0}
        # )["successes"] += 1
        call.summary = summary
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

    def get_feedback(
        self,
        query: Optional[Union[Query, str]] = None,
        *,
        reaction: Optional[str] = None,
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
        query: Optional[Union[Query, str]] = None,
        *,
        reaction: Optional[str] = None,
        offset: int = 0,
        limit: int = 100,
    ) -> FeedbackQuery:
        return self.get_feedback(
            query=query, reaction=reaction, offset=offset, limit=limit
        )

    ################ Internal Helpers ################

    def _ref_is_own(self, ref: Ref) -> bool:
        return isinstance(ref, Ref)

    def _project_id(self) -> str:
        return f"{self.entity}/{self.project}"

    # This is used by tests and op_execute still, but the save() interface
    # is nicer for clients I think?
    @trace_sentry.global_trace_sentry.watch()
    def _save_object(self, val: Any, name: str, branch: str = "latest") -> ObjectRef:
        self._save_nested_objects(val, name=name)

        # typically, this condition would belong inside of the
        # `_save_nested_objects` switch. However, we don't want to recursively
        # publish all custom objects. Instead we only want to do this at the
        # top-most level if requested
        if get_serializer_for_obj(val) is not None:
            self._save_and_attach_ref(val)

        return self._save_object_basic(val, name, branch)

    def _save_object_basic(
        self, val: Any, name: Optional[str] = None, branch: str = "latest"
    ) -> ObjectRef:
        # The WeaveTable case is special because object saving happens inside
        # _save_object_nested and it has a special table_ref -- skip it here.
        if getattr(val, "_is_dirty", False) and not isinstance(val, WeaveTable):
            val.ref = None

        is_opdef = isinstance(val, Op)
        val = map_to_refs(val)
        if isinstance(val, ObjectRef):
            return val
        json_val = to_json(val, self._project_id(), self.server)

        if name is None:
            if json_val.get("_type") == "CustomWeaveType":
                custom_name = json_val.get("weave_type", {}).get("type")
                name = custom_name

        if name is None:
            raise ValueError("Name must be provided for object saving")

        name = sanitize_object_name(name)

        response = self.server.obj_create(
            ObjCreateReq(
                obj=ObjSchemaForInsert(
                    project_id=self.entity + "/" + self.project,
                    object_id=name,
                    val=json_val,
                )
            )
        )
        ref: Ref
        if is_opdef:
            ref = OpRef(self.entity, self.project, name, response.digest)
        else:
            ref = ObjectRef(self.entity, self.project, name, response.digest)
        # TODO: Try to put a ref onto val? Or should user code use a style like
        # save instead?
        return ref

    def _save_nested_objects(self, obj: Any, name: Optional[str] = None) -> Any:
        if (ref := get_ref(obj)) is not None:
            if ALLOW_MIXED_PROJECT_REFS:
                return

            # Check if existing ref is to current project, if not,
            # remove the ref and recreate it in the current project
            if ref.project == self.project:
                return
            remove_ref(obj)

        if isinstance(obj, (pydantic.BaseModel, pydantic.v1.BaseModel)):
            obj_rec = pydantic_object_record(obj)
            for v in obj_rec.__dict__.values():
                self._save_nested_objects(v)
            ref = self._save_object_basic(obj_rec, name or get_obj_name(obj_rec))
            obj.__dict__["ref"] = ref
        elif dataclasses.is_dataclass(obj) and not isinstance(obj, Ref):
            obj_rec = dataclass_object_record(obj)
            for v in obj_rec.__dict__.values():
                self._save_nested_objects(v)
            ref = self._save_object_basic(obj_rec, name or get_obj_name(obj_rec))
            obj.__dict__["ref"] = ref
        elif isinstance(obj, Table):
            table_ref = self._save_table(obj)
            obj.ref = table_ref
        elif isinstance(obj, WeaveTable):
            table_ref = self._save_table(obj)
            obj.ref = table_ref
            obj.table_ref = table_ref
        elif isinstance_namedtuple(obj):
            for v in obj._asdict().values():
                self._save_nested_objects(v)
        elif isinstance(obj, (list, tuple)):
            for v in obj:
                self._save_nested_objects(v)
        elif isinstance(obj, dict):
            for v in obj.values():
                self._save_nested_objects(v)
        elif isinstance(obj, Op):
            self._save_op(obj)
        # TODO: Kinda hacky way to dispatching Dataset with rows: Table
        elif isinstance(obj, WeaveObject) and hasattr(obj, "rows"):
            self._save_nested_objects(obj.rows)

    @trace_sentry.global_trace_sentry.watch()
    def _save_table(self, table: Table) -> TableRef:
        rows = to_json(table.rows, self._project_id(), self.server)
        response = self.server.table_create(
            TableCreateReq(
                table=TableSchemaForInsert(project_id=self._project_id(), rows=rows)
            )
        )
        return TableRef(
            entity=self.entity, project=self.project, digest=response.digest
        )

    @trace_sentry.global_trace_sentry.watch()
    def _op_calls(self, op: Op) -> CallsIter:
        op_ref = get_ref(op)
        if op_ref is None:
            raise ValueError(f"Can't get runs for unpublished op: {op}")
        return self.get_calls(CallsFilter(op_names=[op_ref.uri()]))

    @trace_sentry.global_trace_sentry.watch()
    def _objects(self, filter: Optional[ObjectVersionFilter] = None) -> list[ObjSchema]:
        if not filter:
            filter = ObjectVersionFilter()
        else:
            filter = filter.model_copy()
        filter = typing.cast(ObjectVersionFilter, filter)
        filter.is_op = False

        response = self.server.objs_query(
            ObjQueryReq(
                project_id=self._project_id(),
                filter=filter,
            )
        )
        return response.objs

    def _save_op(self, op: Op, name: Optional[str] = None) -> Ref:
        if op.ref is not None:
            return op.ref

        if name is None:
            name = op.name

        return self._save_and_attach_ref(op, name)

    def _save_and_attach_ref(self, op: Any, name: Optional[str] = None) -> Ref:
        if (ref := getattr(op, "ref", None)) is not None:
            return ref

        op_def_ref = self._save_object_basic(op, name)

        # setattr(op, "ref", op_def_ref) fails here
        # op.ref = op_def_ref fails here
        # Seems to be the only way to set the ref on the op
        op.__dict__["ref"] = op_def_ref
        return op_def_ref

    @trace_sentry.global_trace_sentry.watch()
    def _set_call_display_name(
        self, call: Call, display_name: Optional[str] = None
    ) -> None:
        # Removing call display name, use "" for db representation
        if display_name is None:
            display_name = ""
        self.server.call_update(
            CallUpdateReq(
                project_id=self._project_id(),
                call_id=call.id,
                display_name=display_name,
            )
        )

    def _remove_call_display_name(self, call: Call) -> None:
        self._set_call_display_name(call, None)

    def _ref_input_to(self, ref: ref_base.Ref) -> Sequence[Call]:
        raise NotImplementedError()

    def _ref_value_input_to(self, ref: ref_base.Ref) -> list[Call]:
        raise NotImplementedError()

    def _ref_output_of(self, ref: ObjectRef) -> typing.Optional[Call]:
        raise NotImplementedError()

    def _op_runs(self, op_def: Op) -> Sequence[Call]:
        raise NotImplementedError()

    def _ref_uri(self, name: str, version: str, path: str) -> str:
        return ObjectRef(self.entity, self.project, name, version).uri()


def safe_current_wb_run_id() -> Optional[str]:
    try:
        import wandb

        wandb_run = wandb.run
        if wandb_run is None:
            return None
        return f"{wandb_run.entity}/{wandb_run.project}/{wandb_run.id}"
    except ImportError:
        return None


def check_wandb_run_matches(
    wandb_run_id: Optional[str], weave_entity: str, weave_project: str
) -> None:
    if wandb_run_id:
        # ex: "entity/project/run_id"
        wandb_entity, wandb_project, _ = wandb_run_id.split("/")
        if wandb_entity != weave_entity or wandb_project != weave_project:
            raise ValueError(
                f'Project Mismatch: weave and wandb must be initialized using the same project. Found wandb.init targeting project "{wandb_entity}/{wandb_project}" and weave.init targeting project "{weave_entity}/{weave_project}". To fix, please use the same project for both library initializations.'
            )


def _build_anonymous_op(name: str, config: Optional[Dict] = None) -> Op:
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
    op.name = name
    return op


REDACT_KEYS = (
    "api_key",
    "Authorization",
)
REDACTED_VALUE = "REDACTED"


def redact_sensitive_keys(obj: typing.Any) -> typing.Any:
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
            if k in REDACT_KEYS:
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
    if len(res) > 128:
        res = res[:128]
    return res


__docspec__ = [WeaveClient, Call, CallsIter]
