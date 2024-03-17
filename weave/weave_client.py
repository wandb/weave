from typing import Literal, Any, Union, Optional, TypedDict
import dataclasses
import uuid
import pydantic
import json
import inspect
import copy
import datetime

from weave import box
from weave.table import Table
from weave import urls
from weave import op_def
from weave import run_context
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


def generate_id():
    return str(uuid.uuid4())


@dataclasses.dataclass
class Ref:
    def uri(self) -> str:
        raise NotImplementedError

    def with_extra(self, extra: list[str]) -> "Ref":
        params = dataclasses.asdict(self)
        params["extra"] = self.extra + extra
        return self.__class__(**params)

    def with_key(self, key: str) -> "Ref":
        return self.with_extra(["key", key])

    def with_attr(self, attr: str) -> "Ref":
        return self.with_extra(["attr", attr])

    def with_index(self, index: int) -> "Ref":
        return self.with_extra(["index", str(index)])

    def with_item(self, item_digest: str) -> "Ref":
        return self.with_extra(["id", f"{item_digest}"])


@dataclasses.dataclass
class TableRef(Ref):
    entity: str
    project: str
    digest: str
    extra: list[str] = dataclasses.field(default_factory=list)

    def uri(self) -> str:
        u = f"weave:///{self.entity}/{self.project}/table/{self.digest}"
        if self.extra:
            u += "/" + "/".join(self.extra)
        return u


@dataclasses.dataclass
class ObjectRef(Ref):
    entity: str
    project: str
    name: str
    version: str
    extra: list[str] = dataclasses.field(default_factory=list)

    def uri(self) -> str:
        u = f"weave:///{self.entity}/{self.project}/object/{self.name}:{self.version}"
        if self.extra:
            u += "/" + "/".join(self.extra)
        return u


def parse_uri(uri: str) -> Union[ObjectRef, TableRef]:
    if not uri.startswith("weave:///"):
        raise ValueError(f"Invalid URI: {uri}")
    path = uri[len("weave:///") :]
    parts = path.split("/")
    if len(parts) < 3:
        raise ValueError(f"Invalid URI: {uri}")
    entity, project, kind = parts[:3]
    remaining = parts[3:]
    if kind == "table":
        return TableRef(
            entity=entity, project=project, digest=remaining[0], extra=remaining[1:]
        )
    elif kind == "object":
        name, version = remaining[0].split(":")
        return ObjectRef(
            entity=entity,
            project=project,
            name=name,
            version=version,
            extra=remaining[1:],
        )
    else:
        raise ValueError(f"Unknown ref kind: {kind}")


@dataclasses.dataclass
class CallRef(Ref):
    id: uuid.UUID
    extra: list[str] = dataclasses.field(default_factory=list)

    def uri(self) -> str:
        u = f"weave:///call/{self.id}"
        if self.extra:
            u += "/" + "/".join(self.extra)
        return u


class ValueFilter(TypedDict, total=False):
    id: uuid.UUID
    ref: Ref
    type: str
    val: dict


def dataclasses_asdict_one_level(obj):
    # dataclasses.asdict is recursive. We don't want that when json encoding
    return {f.name: getattr(obj, f.name) for f in dataclasses.fields(obj)}


def pydantic_asdict_one_level(obj: pydantic.BaseModel):
    return {k: getattr(obj, k) for k in obj.model_fields}


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


class ObjectRecord:
    _class_name: str

    def __init__(self, attrs):
        for k, v in attrs.items():
            setattr(self, k, v)

    def __repr__(self):
        return f"ObjectRecord({self.__dict__})"

    def __eq__(self, other):
        if other.__class__.__name__ != getattr(self, "_class_name"):
            return False
        for k, v in self.__dict__.items():
            if k == "_class_name" or k == "id":
                continue
            if getattr(other, k) != v:
                return False
        return True


@dataclasses.dataclass
class MutationSetitem:
    path: list[str]
    operation: Literal["setitem"]
    args: tuple[str, Any]


@dataclasses.dataclass
class MutationSetattr:
    path: list[str]
    operation: Literal["setattr"]
    args: tuple[str, Any]


@dataclasses.dataclass
class MutationAppend:
    path: list[str]
    operation: Literal["append"]
    args: tuple[Any]


Mutation = Union[MutationSetattr, MutationSetitem, MutationAppend]


def make_mutation(path, operation, args):
    if operation == "setitem":
        return MutationSetitem(path, operation, args)
    elif operation == "setattr":
        return MutationSetattr(path, operation, args)
    elif operation == "append":
        return MutationAppend(path, operation, args)
    else:
        raise ValueError(f"Unknown operation: {operation}")


class Tracable:
    mutated_value: Any = None
    ref: Ref
    list_mutations: Optional[list] = None
    mutations: Optional[list[Mutation]] = None
    root: "Tracable"
    server: TraceServerInterface

    def add_mutation(self, path, operation, *args):
        if self.mutations is None:
            self.mutations = []
        self.mutations.append(make_mutation(path, operation, args))

    def save(self):
        if not isinstance(self.ref, ObjectRef):
            raise ValueError("Can only save from object refs")
        if self.root is not self:
            raise ValueError("Can only save from root object")
        if self.mutations is None:
            raise ValueError("No mutations to save")

        mutations = self.mutations
        self.mutations = None
        return self.server.mutate(self.ref, mutations)


class TraceObject(Tracable):
    def __init__(self, val, ref, server, root):
        self.val = val
        self.ref = ref
        self.server = server
        self.root = root
        if self.root is None:
            self.root = self

    def __getattribute__(self, __name: str) -> Any:
        try:
            return object.__getattribute__(self, __name)
        except AttributeError:
            pass
        return make_trace_obj(
            object.__getattribute__(self.val, __name),
            self.ref.with_attr(__name),
            self.server,
            self.root,
        )

    def __setattr__(self, __name: str, __value: Any) -> None:
        if __name in ["val", "ref", "server", "root", "mutations"]:
            return object.__setattr__(self, __name, __value)
        else:
            object.__getattribute__(self, "root").add_mutation(
                self.ref.extra, "setattr", __name, __value
            )
            return object.__setattr__(self.val, __name, __value)

    def __repr__(self):
        return f"TraceObject({self.val})"

    def __eq__(self, other):
        return self.val == other


class TraceTable(Tracable):
    filter: _TableRowFilter

    def __init__(self, table_ref: TableRef, ref, server, filter, root):
        self.table_ref = table_ref
        self.filter = filter
        self.ref = ref
        self.server: TraceServerInterface = server
        self.root = root
        if self.root is None:
            self.root = self

    def __getitem__(self, key):
        if isinstance(key, slice):
            raise ValueError("Slices not yet supported")
        elif isinstance(key, int):
            response = self.server.table_query(
                TableQueryReq(
                    entity=self.table_ref.entity,
                    project=self.table_ref.project,
                    table_digest=self.table_ref.digest,
                )
            )
        else:
            filter = self.filter.model_copy()
            filter.row_digests = [key]
            response = self.server.table_query(
                TableQueryReq(
                    entity=self.table_ref.entity,
                    project=self.table_ref.project,
                    table_digest=self.table_ref.digest,
                    filter=_TableRowFilter(row_digests=[key]),
                )
            )
        row = response.rows[0]
        return make_trace_obj(
            row.val,
            self.ref.with_item(row.digest),
            self.server,
            self.root,
        )

    def __iter__(self):
        page_index = 0
        page_size = 10
        i = 0
        while True:
            # page_data = self.server.table_query(
            #     self.table_ref,
            #     self.filter,
            #     offset=page_index * page_size,
            #     limit=page_size,
            # )
            response = self.server.table_query(
                TableQueryReq(
                    entity=self.table_ref.entity,
                    project=self.table_ref.project,
                    table_digest=self.table_ref.digest,
                    # filter=self.filter,
                )
            )
            for item in response.rows:
                yield make_trace_obj(
                    item.val,
                    self.ref.with_item(item.digest),
                    self.server,
                    self.root,
                )
                i += 1
            if len(response.rows) < page_size:
                break
            page_index += 1

    def append(self, val):
        self.root.add_mutation(self.ref.extra, "append", val)


class TraceList(Tracable):
    def __init__(self, val, ref, server, root):
        self.val = val
        self.ref = ref
        self.server: TraceServerInterface = server
        self.root = root
        if self.root is None:
            self.root = self

    def __getitem__(self, i):
        return make_trace_obj(
            self.val[i], self.ref.with_index(i), self.server, self.root
        )

    def __eq__(self, other):
        return self.val == other


class TraceDict(Tracable, dict):
    def __init__(self, val, ref, server, root):
        self.val = val
        self.ref = ref
        self.server = server
        self.root = root
        if self.root is None:
            self.root = self

    def __getitem__(self, key):
        return make_trace_obj(
            self.val[key], self.ref.with_key(key), self.server, self.root
        )

    def __setitem__(self, key, value):
        self.val[key] = value
        self.root.add_mutation(self.ref.extra, "setitem", key, value)

    def keys(self):
        return self.val.keys()

    def values(self):
        return self.val.values()

    def items(self):
        for k in self.keys():
            yield k, self[k]

    def __iter__(self):
        return iter(self.val)

    def __repr__(self):
        return f"TraceDict({self.val})"

    def __eq__(self, other):
        return self.val == other


def make_trace_obj(
    val: Any, new_ref: Ref, server: TraceServerInterface, root: Optional[Tracable]
):
    # Derefence val and create the appropriate wrapper object
    extra: list[str] = []
    if isinstance(val, ObjectRef):
        new_ref = val
        extra = val.extra
        read_res = server.obj_read(
            ObjReadReq(
                entity=val.entity,
                project=val.project,
                name=val.name,
                version_digest=val.version,
            )
        )
        val = from_json(read_res.obj.val)
        # val = server._resolve_object(val.name, "latest")

    if isinstance(val, TableRef):
        val = TraceTable(val, new_ref, server, _TableRowFilter(), root)

    if extra:
        # This is where extra resolution happens?
        for extra_index in range(0, len(extra), 2):
            op, arg = extra[extra_index], extra[extra_index + 1]
            if op == "key":
                val = val[arg]
            elif op == "attr":
                val = getattr(val, arg)
            elif op == "index":
                val = val[int(arg)]
            elif op == "id":
                val = val[arg]
            else:
                raise ValueError(f"Unknown ref type: {extra[extra_index]}")

            # need to deref if we encounter these
            if isinstance(val, TableRef):
                val = TraceTable(val, new_ref, server, _TableRowFilter(), root)

    if isinstance(val, ObjectRecord):
        # if val._type == "custom_obj":
        #     return custom_objs.decode_custom_obj(val.weave_type, val.files)  # type: ignore
        return TraceObject(val, new_ref, server, root)
    elif isinstance(val, list):
        return TraceList(val, new_ref, server, root)
    elif isinstance(val, dict):
        return TraceDict(val, new_ref, server, root)
    box_val = box.box(val)
    setattr(box_val, "ref", new_ref)
    return box_val


def get_ref(obj: Any) -> Optional[ObjectRef]:
    return getattr(obj, "ref", None)


def map_to_refs(obj: Any) -> Any:
    ref = get_ref(obj)
    if ref:
        return ref
    if isinstance(obj, ObjectRecord):
        return ObjectRecord(
            {k: map_to_refs(v) for k, v in obj.__dict__.items()},
        )
    if isinstance(obj, pydantic.BaseModel):
        return ObjectRecord(
            {
                "_class_name": obj.__class__.__name__,
                **{
                    k: map_to_refs(v) for k, v in pydantic_asdict_one_level(obj).items()
                },
                **{
                    k: map_to_refs(v)
                    for k, v in inspect.getmembers(
                        obj, lambda x: isinstance(x, op_def.OpDef)
                    )
                    if isinstance(v, op_def.OpDef)
                },
            },
        )
    elif isinstance(obj, list):
        return [map_to_refs(v) for v in obj]
    elif isinstance(obj, dict):
        return {k: map_to_refs(v) for k, v in obj.items()}

    return obj


def to_json(obj: Any) -> Any:
    # if isinstance(obj, uuid.UUID):
    #     return {"_type": "UUID", "uuid": obj.hex}
    if isinstance(obj, TableRef):
        return obj.uri()
    elif isinstance(obj, ObjectRef):
        return obj.uri()
    elif isinstance(obj, ObjectRecord):
        res = {"_type": obj._class_name}
        for k, v in obj.__dict__.items():
            res[k] = to_json(v)
        return res
    elif isinstance(obj, list):
        return [to_json(v) for v in obj]
    elif isinstance(obj, dict):
        return {k: to_json(v) for k, v in obj.items()}

    if isinstance(obj, (int, float, str, bool, box.BoxedNone)) or obj is None:
        return obj

    return custom_objs.encode_custom_obj(obj)


def from_json(obj: Any) -> Any:
    if isinstance(obj, list):
        return [from_json(v) for v in obj]
    elif isinstance(obj, dict):
        val_type = obj.get("_type")
        if val_type is not None:
            del obj["_type"]
            if val_type == "ObjectRecord":
                return ObjectRecord({k: from_json(v) for k, v in obj.items()})
            elif val_type == "CustomWeaveType":
                return custom_objs.decode_custom_obj(obj["weave_type"], obj["files"])
            else:
                return ObjectRecord({k: from_json(v) for k, v in obj.items()})
        return {k: from_json(v) for k, v in obj.items()}
    elif isinstance(obj, str) and obj.startswith("weave://"):
        return parse_uri(obj)

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
        inputs=from_json(server_call.inputs),
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
        val = map_to_refs(val)
        if isinstance(val, ObjectRef):
            return val
        json_val = to_json(val)

        response = self.server.obj_create(
            ObjCreateReq(
                obj=ObjSchemaForInsert(
                    entity=self.entity, project=self.project, name=name, val=json_val
                )
            )
        )
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
        val = from_json(read_res.obj.val)
        return make_trace_obj(val, ref, self.server, None)

    def save_table(self, table: Table) -> TableRef:
        response = self.server.table_create(
            TableCreateReq(
                table=TableSchemaForInsert(
                    entity=self.entity, project=self.project, rows=table.rows
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
                entity=self.entity,
                project=self.project,
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
            inputs=to_json(inputs_with_refs),
            attributes={},
            wb_run_id=current_wb_run_id,
        )
        self.server.call_start(CallStartReq(start=start))
        return call
        # return CallSchemaRun(start)

    def finish_call(self, call: Call, output: Any):
        # TODO: not saving finished call yet
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
                        "outputs": output,
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
        if isinstance(obj, pydantic.BaseModel):
            if hasattr(obj, "_trace_object"):
                return obj._trace_object
            obj_rec = ObjectRecord(
                {
                    "_class_name": obj.__class__.__name__,
                    **{
                        k: self.save_nested_objects(v)
                        for k, v in pydantic_asdict_one_level(obj).items()
                    },
                    **{
                        k: self.save_nested_objects(v)
                        for k, v in inspect.getmembers(
                            obj, lambda x: isinstance(x, op_def.OpDef)
                        )
                        if isinstance(v, op_def.OpDef)
                    },
                },
            )
            ref = self._save_object(obj_rec, name or get_obj_name(obj_rec))
            # return make_trace_obj(obj_rec, ref, client.server, None)
            trace_obj = make_trace_obj(obj_rec, ref, self.server, None)
            obj._trace_object = trace_obj
            return trace_obj
        elif isinstance(obj, Table):
            table_ref = self.save_table(obj)
            return TraceTable(
                table_ref, table_ref, self.server, _TableRowFilter(), None
            )
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


# TODO
#
# must prove
# - eval test
#   - why are there two tables. two problems:
#     - create_run, finish_run
#       - issue is that the client doesn't handle table saving, so it can't
#         associate the table with an ID
#     - seems like we're not using a ref?
#       - this is because this is the eval_rows table, which is output
#         by eval
#   - top-level op-name instead of via nested ref?
#     - ie we need some logic for "ref switching when walking refs"
#   - Is this whole evaluation relocatable?
#   - [x] mutations (append, set, remove)
#   - [x] calls on dataset rows are stable
#   - batch ref resolution in call query / dataset join path
#   - [x] custom objects
#   - [x] files
#   - large files
#   - store files at top-level?
#   - can't efficiently fetch OpDef, and custom objects, by type yet.
#   - ensure true client/server wire interface
#   - [x] table ID refs instead of index
#   - Don't save the same objects over and over again.
#   - runs setting run ID for memoization
#   - dedupe, content ID
#   - efficient walking of all relationships
#   - call outputs as refs
#   - performance tests
#   - save all ops as top-level objects
#   - WeaveList
#
# perf related
#   - pull out _type to top-level of value and index
#   - don't encode UUID
# code quality
#   - clean up mutation stuff
#   - merge extra stuff in refs
#   - naming: Value / Object / Record etc.
# bugs
#   - have to manually pass self when reloading op_def on Object
#   - filter non-string
#   - filter table when not dicts
#   - duplicating _type into value and column (maybe fine)

# Biggest question, can the val table be stored as a table?


def safe_current_wb_run_id() -> Optional[str]:
    try:
        import wandb

        wandb_run = wandb.run
        if wandb_run is None:
            return None
        return f"{wandb_run.entity}/{wandb_run.project}/{wandb_run.id}"
    except ImportError:
        return None
