import dataclasses
import datetime
import typing
import uuid
from collections import namedtuple
from typing import Any, Dict, Optional, Sequence, TypedDict, Union

import pydantic
from requests import HTTPError

from weave import call_context, client_context, trace_sentry, urls
from weave.exception import exception_to_json_str
from weave.feedback import FeedbackQuery, RefFeedbackQuery
from weave.table import Table
from weave.trace.object_record import (
    ObjectRecord,
    dataclass_object_record,
    pydantic_asdict_one_level,
    pydantic_object_record,
)
from weave.trace.op import Op
from weave.trace.refs import (
    CallRef,
    ObjectRef,
    OpRef,
    Ref,
    TableRef,
    parse_uri,
)
from weave.trace.serialize import from_json, isinstance_namedtuple, to_json
from weave.trace.vals import TraceObject, TraceTable, make_trace_obj
from weave.trace_server.trace_server_interface import (
    CallEndReq,
    CallSchema,
    CallsDeleteReq,
    CallsQueryReq,
    CallStartReq,
    CallUpdateReq,
    EndedCallSchemaForInsert,
    Feedback,
    FeedbackQueryReq,
    ObjCreateReq,
    ObjQueryReq,
    ObjQueryRes,
    ObjReadReq,
    ObjSchema,
    ObjSchemaForInsert,
    Query,
    RefsReadBatchReq,
    StartedCallSchemaForInsert,
    TableCreateReq,
    TableQueryReq,
    TableSchemaForInsert,
    TraceServerInterface,
    _CallsFilter,
    _ObjectVersionFilter,
    _TableRowFilter,
)

if typing.TYPE_CHECKING:
    from . import ref_base


def generate_id() -> str:
    return str(uuid.uuid4())


class ValueFilter(TypedDict, total=False):
    id: uuid.UUID
    ref: Ref
    type: str
    val: dict


def dataclasses_asdict_one_level(obj: Any) -> typing.Dict[str, Any]:
    # dataclasses.asdict is recursive. We don't want that when json encoding
    return {f.name: getattr(obj, f.name) for f in dataclasses.fields(obj)}


# TODO: unused


def get_obj_name(val: Any) -> str:
    name = getattr(val, "name", None)
    if name == None:
        if isinstance(val, ObjectRecord):
            name = val._class_name
        else:
            name = f"{val.__class__.__name__}"
    if not isinstance(name, str):
        raise ValueError(f"Object's name attribute is not a string: {name}")
    return name


def get_ref(obj: Any) -> Optional[ObjectRef]:
    return getattr(obj, "ref", None)


def _get_direct_ref(obj: Any) -> Optional[Ref]:
    if isinstance(obj, TraceTable):
        # TODO: this path is odd. We want to use table_ref when serializing
        # which is the direct ref to the table. But .ref on TraceTable is
        # the "container ref", ie a ref to the root object that the TraceTable
        # is within, with extra pointing to the table.
        return obj.table_ref
    return getattr(obj, "ref", None)


def map_to_refs(obj: Any) -> Any:
    ref = _get_direct_ref(obj)
    if ref:
        return ref
    if isinstance(obj, ObjectRecord):
        return obj.map_values(map_to_refs)
    elif isinstance(obj, pydantic.BaseModel):
        obj_record = pydantic_object_record(obj)
        return obj_record.map_values(map_to_refs)
    elif dataclasses.is_dataclass(obj):
        obj_record = dataclass_object_record(obj)
        return obj_record.map_values(map_to_refs)
    elif isinstance(obj, Table):
        return obj.ref
    elif isinstance(obj, list):
        return [map_to_refs(v) for v in obj]
    elif isinstance(obj, dict):
        return {k: map_to_refs(v) for k, v in obj.items()}

    return obj


@dataclasses.dataclass
class Dataset:
    rows: list[Any]


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
        client = client_context.weave_client.require_weave_client()
        if not self.id:
            raise ValueError("Can't get children of call without ID")
        return CallsIter(
            client.server,
            self.project_id,
            _CallsFilter(parent_ids=[self.id]),
        )

    def delete(self) -> bool:
        client = client_context.weave_client.require_weave_client()
        return client.delete_call(call=self)

    def set_display_name(self, name: Optional[str]) -> None:
        if name == "":
            raise ValueError(
                "Display name cannot be empty. To remove the display_name, set name=None or use remove_display_name."
            )
        if name == self.display_name:
            return
        client = client_context.weave_client.require_weave_client()
        client._set_call_display_name(call=self, display_name=name)
        self.display_name = name

    def remove_display_name(self) -> None:
        self.set_display_name(None)


class CallsIter:
    server: TraceServerInterface
    filter: _CallsFilter

    def __init__(
        self, server: TraceServerInterface, project_id: str, filter: _CallsFilter
    ) -> None:
        self.server = server
        self.project_id = project_id
        self.filter = filter

    def __getitem__(self, key: Union[slice, int]) -> TraceObject:
        if isinstance(key, slice):
            raise NotImplementedError("Slicing not supported")
        for i, call in enumerate(self):
            if i == key:
                return call
        raise IndexError(f"Index {key} out of range")

    def __iter__(self) -> typing.Iterator[TraceObject]:
        page_index = 0
        page_size = 10
        entity, project = self.project_id.split("/")
        while True:
            response = self.server.calls_query(
                CallsQueryReq(
                    project_id=self.project_id,
                    filter=self.filter,
                    offset=page_index * page_size,
                    limit=page_size,
                )
            )
            page_data = response.calls
            for call in page_data:
                # TODO: if we want to be able to refer to call outputs
                # we need to yield a ref-tracking call here.
                yield make_client_call(entity, project, call, self.server)
                # yield make_trace_obj(call, ValRef(call.id), self.server, None)
            if len(page_data) < page_size:
                break
            page_index += 1


def make_client_call(
    entity: str, project: str, server_call: CallSchema, server: TraceServerInterface
) -> TraceObject:
    output = server_call.output
    call = Call(
        op_name=server_call.op_name,
        project_id=server_call.project_id,
        trace_id=server_call.trace_id,
        parent_id=server_call.parent_id,
        id=server_call.id,
        inputs=from_json(server_call.inputs, server_call.project_id, server),
        output=output,
        summary=server_call.summary,
        display_name=server_call.display_name,
        attributes=server_call.attributes,
    )
    if call.id is None:
        raise ValueError("Call ID is None")
    return TraceObject(call, CallRef(entity, project, call.id), server, None)


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
            self.server.ensure_project_exists(entity, project)

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

        # Probably bad form to mutate the ref here
        # At this point, `ref.digest` is one of three things:
        # 1. "latest" - the user asked for the latest version of the object
        # 2. "v###" - the user asked for a specific version of the object
        # 3. The actual digest.
        #
        # However, we always want to resolve the ref to the digest. So
        # here, we just directly assign the digest.
        ref.digest = read_res.obj.digest

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
    def calls(self, filter: Optional[_CallsFilter] = None) -> CallsIter:
        if filter is None:
            filter = _CallsFilter()

        return CallsIter(self.server, self._project_id(), filter)

    @trace_sentry.global_trace_sentry.watch()
    def call(self, call_id: str) -> TraceObject:
        response = self.server.calls_query(
            CallsQueryReq(
                project_id=self._project_id(),
                filter=_CallsFilter(call_ids=[call_id]),
            )
        )
        if not response.calls:
            raise ValueError(f"Call not found: {call_id}")
        response_call = response.calls[0]
        return make_client_call(self.entity, self.project, response_call, self.server)

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
            op_def_ref = self._save_op(op)
            op_str = op_def_ref.uri()
        else:
            op_str = op

        self._save_nested_objects(inputs)
        inputs_with_refs = map_to_refs(inputs)
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
        elif isinstance(output, dict) and "usage" in output and "model" in output:
            summary["usage"] = {}
            summary["usage"][output["model"]] = {"requests": 1, **output["usage"]}
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

    def feedback(
        self,
        query: Optional[Union[Query, str]] = None,
        *,
        reaction: Optional[str] = None,
        offset: int = 0,
        limit: int = 100,
    ) -> FeedbackQuery:
        """Query project for feedback.

        Examples:
            # Fetch a specific feedback object.
            # Note that this still returns a collection, which is expected
            # to contain zero or one item(s).
            client.feedback("1B4082A3-4EDA-4BEB-BFEB-2D16ED59AA07")

            # Find all feedback objects with a specific reaction.
            client.feedback(reaction="👍", limit=10)

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
        return self._save_object_basic(val, name, branch)

    def _save_object_basic(
        self, val: Any, name: str, branch: str = "latest"
    ) -> ObjectRef:
        is_opdef = isinstance(val, Op)
        val = map_to_refs(val)
        if isinstance(val, ObjectRef):
            return val
        json_val = to_json(val, self._project_id(), self.server)

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
        if get_ref(obj) is not None:
            return
        if isinstance(obj, pydantic.BaseModel):
            obj_rec = pydantic_object_record(obj)
            for v in obj_rec.__dict__.values():
                self._save_nested_objects(v)
            ref = self._save_object_basic(obj_rec, name or get_obj_name(obj_rec))
            obj.__dict__["ref"] = ref
        elif dataclasses.is_dataclass(obj):
            obj_rec = dataclass_object_record(obj)
            for v in obj_rec.__dict__.values():
                self._save_nested_objects(v)
            ref = self._save_object_basic(obj_rec, name or get_obj_name(obj_rec))
            obj.__dict__["ref"] = ref
        elif isinstance(obj, Table):
            table_ref = self._save_table(obj)
            obj.ref = table_ref
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

    @trace_sentry.global_trace_sentry.watch()
    def _save_table(self, table: Table) -> TableRef:
        response = self.server.table_create(
            TableCreateReq(
                table=TableSchemaForInsert(
                    project_id=self._project_id(), rows=table.rows
                )
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
        return self.calls(_CallsFilter(op_names=[op_ref.uri()]))

    @trace_sentry.global_trace_sentry.watch()
    def _objects(
        self, filter: Optional[_ObjectVersionFilter] = None
    ) -> list[ObjSchema]:
        if not filter:
            filter = _ObjectVersionFilter()
        else:
            filter = filter.model_copy()
        filter = typing.cast(_ObjectVersionFilter, filter)
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
        op_def_ref = self._save_object_basic(op, name)
        op.ref = op_def_ref  # type: ignore
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

    def _ref_input_to(self, ref: "ref_base.Ref") -> Sequence[Call]:
        raise NotImplementedError()

    def _ref_value_input_to(self, ref: "ref_base.Ref") -> list[Call]:
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
    op = Op(op_fn)
    op.name = name
    return op
