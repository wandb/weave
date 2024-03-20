from typing import Any, Union, Optional, TypedDict
import dataclasses
import uuid
import pydantic
import inspect
import datetime

from weave import box
from weave.table import Table
from weave import urls
from weave import op_def
from weave.trace.object_record import ObjectRecord, pydantic_object_record
from weave.trace.serialize import to_json, from_json
from weave import graph_client_context
from weave.chobj import custom_objs
from weave.trace_server.trace_server_interface import (
    TraceServerInterface,
    ObjCreateReq,
    ObjSchemaForInsert,
    ObjReadReq,
    StartedCallSchemaForInsert,
    CallStartReq,
    CallsQueryReq,
    CallEndReq,
    CallSchema,
    ObjQueryReq,
    ObjQueryRes,
    TableCreateReq,
    TableSchemaForInsert,
    TableQueryReq,
    _TableRowFilter,
    _CallsFilter,
    _ObjectVersionFilter,
)
from weave.wandb_interface import project_creator
from weave.trace.refs import (
    Ref,
    ObjectRef,
    TableRef,
    CallRef,
    parse_uri,
    OpRef,
)
from weave.trace.vals import TraceObject, TraceTable, Tracable, make_trace_obj


def generate_id():
    return str(uuid.uuid4())


class ValueFilter(TypedDict, total=False):
    id: uuid.UUID
    ref: Ref
    type: str
    val: dict


def dataclasses_asdict_one_level(obj):
    # dataclasses.asdict is recursive. We don't want that when json encoding
    return {f.name: getattr(obj, f.name) for f in dataclasses.fields(obj)}


# TODO: unused


def get_obj_name(val):
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
    if isinstance(obj, TraceTable):
        # TODO: this path is odd. We want to use table_ref when serializing
        # which is the direct ref to the table. But .ref on TraceTable is
        # the "container ref", ie a ref to the root object that the TraceTable
        # is within, with extra pointing to the table.
        return obj.table_ref
    return getattr(obj, "ref", None)


def map_to_refs(obj: Any) -> Any:
    ref = get_ref(obj)
    if ref:
        return ref
    if isinstance(obj, ObjectRecord):
        return obj.map_values(map_to_refs)
    if isinstance(obj, pydantic.BaseModel):
        obj_record = pydantic_object_record(obj)
        return obj_record.map_values(map_to_refs)
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

    @property
    def ui_url(self):
        project_parts = self.project_id.split("/")
        if len(project_parts) != 2:
            raise ValueError(f"Invalid project_id: {self.project_id}")
        entity, project = project_parts
        return urls.call_path_as_peek(entity, project, self.id)

    def children(self):
        client = graph_client_context.require_graph_client()
        if not self.id:
            raise ValueError("Can't get children of call without ID")
        return CallsIter(
            client.server,
            self.project_id,
            _CallsFilter(parent_ids=[self.id]),
        )


class CallsIter:
    server: TraceServerInterface
    filter: _CallsFilter

    def __init__(self, server, project_id: str, filter: _CallsFilter):
        self.server = server
        self.project_id = project_id
        self.filter = filter

    def __iter__(self):
        page_index = 0
        page_size = 10
        while True:
            response = self.server.calls_query(
                CallsQueryReq(
                    project_id=self.project_id,
                    filter=self.filter,
                    # TODO: server doesn't implement offset yet.
                    # offset=page_index * page_size,
                    limit=page_size,
                )
            )
            page_data = response.calls
            for call in page_data:
                # TODO: if we want to be able to refer to call outputs
                # we need to yield a ref-tracking call here.
                yield make_client_call(call, self.server)
                # yield make_trace_obj(call, ValRef(call.id), self.server, None)
            if len(page_data) < page_size:
                break
            page_index += 1


def make_client_call(server_call: CallSchema, server: TraceServerInterface):
    output = server_call.outputs
    if isinstance(output, dict) and "_result" in output:
        output = output["_result"]
    call = Call(
        op_name=server_call.name,
        project_id=server_call.project_id,
        trace_id=server_call.trace_id,
        parent_id=server_call.parent_id,
        id=server_call.id,
        inputs=from_json(server_call.inputs, server_call.project_id, server),
        output=output,
    )
    return TraceObject(call, CallRef(call.id), server, call)


class WeaveClient:
    server: TraceServerInterface

    def __init__(self, entity: str, project: str, server: TraceServerInterface):
        self.entity = entity
        self.project = project
        self.server = server

        # Maybe this should happen on the first write event? For now, let's just ensure
        # the project exists when the client is initialized. For production, we can move
        # this to the service layer which will: a) save a round trip, and b) reduce the amount
        # of client-side logic to duplicate to TS in the future. We already do auth checks
        # in the service layer, so this is just a matter of convenience.
        project_creator.ensure_project_exists(entity, project)

    def ref_is_own(self, ref):
        return isinstance(ref, Ref)

    def _project_id(self) -> str:
        return f"{self.entity}/{self.project}"

    # This is used by tests and op_execute still, but the save() interface
    # is nicer for clients I think?
    def save_object(self, val, name: str, branch: str = "latest") -> ObjectRef:
        val = self.save_nested_objects(val, name=name)
        return self._save_object(val, name, branch)

    def _save_object(self, val, name: str, branch: str = "latest") -> ObjectRef:
        is_opdef = isinstance(val, op_def.OpDef)
        val = map_to_refs(val)
        if isinstance(val, ObjectRef):
            return val
        json_val = to_json(val, self._project_id(), self.server)

        response = self.server.obj_create(
            ObjCreateReq(
                obj=ObjSchemaForInsert(
                    project_id=self.entity + "/" + self.project, name=name, val=json_val
                )
            )
        )
        if is_opdef:
            ref = OpRef(self.entity, self.project, name, response.version_digest)
        else:
            ref = ObjectRef(self.entity, self.project, name, response.version_digest)
        # TODO: Try to put a ref onto val? Or should user code use a style like
        # save instead?
        return ref

    def save(self, val, name: str, branch: str = "latest") -> Any:
        ref = self.save_object(val, name, branch)
        return self.get(ref)

    def get(self, ref: ObjectRef) -> Any:
        read_res = self.server.obj_read(
            ObjReadReq(
                entity=self.entity,
                project=self.project,
                name=ref.name,
                version_digest=ref.version,
            )
        )
        val = from_json(read_res.obj.val, self._project_id(), self.server)
        return make_trace_obj(val, ref, self.server, None)

    def save_table(self, table: Table) -> TableRef:
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

    def calls(self, filter: Optional[_CallsFilter] = None):
        if filter is None:
            filter = _CallsFilter()

        return CallsIter(self.server, self._project_id(), filter)

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
        return make_client_call(response_call, self.server)

    def op_calls(self, op: op_def.OpDef) -> CallsIter:
        op_ref = get_ref(op)
        if op_ref is None:
            raise ValueError(f"Can't get runs for unpublished op: {op}")
        return self.calls(_CallsFilter(op_version_refs=[op_ref.uri()]))

    def objects(self, filter: Optional[_ObjectVersionFilter] = None):
        if not filter:
            filter = _ObjectVersionFilter()
        else:
            filter = filter.model_copy()
        filter.is_op = False

        response = self.server.objs_query(
            ObjQueryReq(
                project_id=self._project_id(),
                filter=filter,
            )
        )
        return response.objs

    def _save_op(self, op: op_def.OpDef) -> ObjectRef:
        if isinstance(op, op_def.BoundOpDef):
            op = op.op_def
        op_def_ref = self._save_object(op, op.name)
        op.ref = op_def_ref
        return op_def_ref

    def create_call(
        self, op: Union[str, op_def.OpDef], parent: Optional[Call], inputs: dict
    ):
        if isinstance(op, op_def.OpDef):
            op_def_ref = self._save_op(op)
            op_str = op_def_ref.uri()
        else:
            op_str = op
        inputs = self.save_nested_objects(inputs)
        inputs_with_refs = map_to_refs(inputs)
        call_id = generate_id()

        if parent:
            trace_id = parent.trace_id
            parent_id = parent.id
        else:
            trace_id = generate_id()
            parent_id = None
        call = Call(
            op_name=op_str,
            project_id=self._project_id(),
            trace_id=trace_id,
            parent_id=parent_id,
            id=call_id,
            inputs=inputs_with_refs,
        )
        current_wb_run_id = safe_current_wb_run_id()
        start = StartedCallSchemaForInsert(
            project_id=self._project_id(),
            id=call_id,
            name=op_str,
            trace_id=trace_id,
            start_datetime=datetime.datetime.now(tz=datetime.timezone.utc),
            parent_id=parent_id,
            inputs=to_json(inputs_with_refs, self._project_id(), self.server),
            attributes={},
            wb_run_id=current_wb_run_id,
        )
        self.server.call_start(CallStartReq(start=start))
        return call
        # return CallSchemaRun(start)

    def finish_call(self, call: Call, output: Any):
        # TODO: not saving finished call yet
        output = self.save_nested_objects(output)
        output = map_to_refs(output)
        call.output = output
        if not isinstance(output, dict):
            output = {"_result": output}
        self.server.call_end(
            CallEndReq.model_validate(
                {
                    "end": {
                        "project_id": self._project_id(),
                        "id": call.id,
                        "end_datetime": datetime.datetime.now(tz=datetime.timezone.utc),
                        "outputs": to_json(output, self._project_id(), self.server),
                        "summary": {},
                    },
                }
            )
        )

    # These are the old client interface terms, op_execute still relies
    # on them.
    def create_run(self, op_name: str, parent_run, inputs, refs):
        return self.create_call(op_name, parent_run, inputs)

    def finish_run(self, run, output, refs):
        self.finish_call(run, output)

    def fail_run(self, run, exception):
        self.finish_call(run, str(exception))

    def save_nested_objects(self, obj: Any, name: Optional[str] = None) -> Any:
        if isinstance(obj, Tracable):
            return obj
        if isinstance(obj, pydantic.BaseModel):
            if hasattr(obj, "_trace_object"):
                return obj._trace_object
            obj_rec = pydantic_object_record(obj).map_values(self.save_nested_objects)
            ref = self._save_object(obj_rec, name or get_obj_name(obj_rec))
            # return make_trace_obj(obj_rec, ref, client.server, None)
            trace_obj = make_trace_obj(obj_rec, ref, self.server, None)
            obj._trace_object = trace_obj
            return trace_obj
        elif isinstance(obj, Table):
            table_ref = self.save_table(obj)
            return TraceTable(table_ref, None, self.server, _TableRowFilter(), None)
        elif isinstance(obj, list):
            return [self.save_nested_objects(v) for v in obj]
        elif isinstance(obj, dict):
            return {k: self.save_nested_objects(v) for k, v in obj.items()}

        if isinstance(obj, op_def.OpDef):
            self._save_op(obj)
            return obj

        # Leave custom objects alone. They do not need to be saved by the
        # time user code interacts with them since they are always leaves
        # and we don't do ref-tracking inside them.
        return obj


def safe_current_wb_run_id() -> Optional[str]:
    try:
        import wandb

        wandb_run = wandb.run
        if wandb_run is None:
            return None
        return f"{wandb_run.entity}/{wandb_run.project}/{wandb_run.id}"
    except ImportError:
        return None
