from typing import Iterator, Literal, Any, Union, Optional, Generator, SupportsIndex
import dataclasses
import operator
import typing

from weave.trace_server.refs import (
    RefWithExtra,
    ObjectRef,
    TableRef,
    KEY_EDGE_TYPE,
    ATTRIBUTE_EDGE_TYPE,
    INDEX_EDGE_TYPE,
    ID_EDGE_TYPE,
)
from weave import box
from weave.trace.serialize import from_json
from weave.trace.object_record import ObjectRecord
from weave.trace_server.trace_server_interface import (
    TraceServerInterface,
    _TableRowFilter,
    TableQueryReq,
    ObjReadReq,
)


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
MutationOperation = Union[Literal["setitem"], Literal["setattr"], Literal["append"]]


def make_mutation(
    path: list[str], operation: MutationOperation, args: tuple[Any, ...]
) -> Mutation:
    if operation == "setitem":
        if len(args) != 2 or not isinstance(args[0], str):
            raise ValueError("setitem mutation requires 2 args")
        args = typing.cast(tuple[str, Any], args)
        return MutationSetitem(path, operation, args)
    elif operation == "setattr":
        if len(args) != 2 or not isinstance(args[0], str):
            raise ValueError("setattr mutation requires 2 args")
        args = typing.cast(tuple[str, Any], args)
        return MutationSetattr(path, operation, args)
    elif operation == "append":
        if len(args) != 1:
            raise ValueError("append mutation requires 1 arg")
        args = typing.cast(tuple[Any], args)
        return MutationAppend(path, operation, args)
    else:
        raise ValueError(f"Unknown operation: {operation}")


class Tracable:
    mutated_value: Any = None
    ref: RefWithExtra
    list_mutations: Optional[list] = None
    mutations: Optional[list[Mutation]] = None
    root: "Tracable"
    server: TraceServerInterface

    def add_mutation(
        self, path: list[str], operation: MutationOperation, *args: Any
    ) -> None:
        if self.mutations is None:
            self.mutations = []
        self.mutations.append(make_mutation(path, operation, args))

    def save(self) -> ObjectRef:
        if not isinstance(self.ref, ObjectRef):
            raise ValueError("Can only save from object refs")
        if self.root is not self:
            raise ValueError("Can only save from root object")
        if self.mutations is None:
            raise ValueError("No mutations to save")

        mutations = self.mutations
        self.mutations = None
        raise NotImplementedError("Traceable.save not implemented")
        # return self.server.mutate(self.ref, mutations)


class TraceObject(Tracable):
    def __init__(
        self,
        val: Any,
        ref: RefWithExtra,
        server: TraceServerInterface,
        root: typing.Optional[Tracable],
    ) -> None:
        self._val = val
        self.ref = ref
        self.server = server
        if root is None:
            root = self
        self.root = root

    def __getattribute__(self, __name: str) -> Any:
        try:
            return object.__getattribute__(self, __name)
        except AttributeError:
            pass
        val_attr_val = object.__getattribute__(self._val, __name)
        # Not ideal, what about properties?
        if callable(val_attr_val):
            return val_attr_val

        new_ref = self.ref.with_attr(__name)

        return make_trace_obj(
            val_attr_val,
            new_ref,
            self.server,
            self.root,
        )

    def __setattr__(self, __name: str, __value: Any) -> None:
        if __name in ["_val", "ref", "server", "root", "mutations"]:
            return object.__setattr__(self, __name, __value)
        else:
            if not isinstance(self.ref, ObjectRef):
                raise ValueError("Can only set attributes on object refs")
            object.__getattribute__(self, "root").add_mutation(
                self.ref.extra, "setattr", __name, __value
            )
            return object.__setattr__(self._val, __name, __value)

    def __repr__(self) -> str:
        return f"TraceObject({self._val})"

    def __eq__(self, other: Any) -> bool:
        return self._val == other


class TraceTable(Tracable):
    filter: _TableRowFilter

    def __init__(
        self,
        table_ref: TableRef,
        ref: Optional[RefWithExtra],
        server: TraceServerInterface,
        filter: _TableRowFilter,
        root: typing.Optional[Tracable],
    ) -> None:
        self.table_ref = table_ref
        self.filter = filter
        self.ref = ref  # type: ignore
        self.server: TraceServerInterface = server
        if root is None:
            root = self
        self.root = root

    def __getitem__(self, key: Union[int, slice, str]) -> Any:
        if isinstance(key, slice):
            raise ValueError("Slices not yet supported")
        elif isinstance(key, int):
            response = self.server.table_query(
                TableQueryReq(
                    project_id=f"{self.table_ref.entity}/{self.table_ref.project}",
                    table_digest=self.table_ref.digest,
                )
            )
            row = response.rows[key]
            new_ref = self.ref.with_item(row.digest)

            return make_trace_obj(
                row.val,
                new_ref,
                self.server,
                self.root,
            )
        else:
            for row in self:
                if row.ref.extra[-1] == key:
                    return row
            else:
                raise KeyError(f"Row ID not found: {key}")

    def __iter__(self) -> Generator[Any, None, None]:
        page_index = 0
        page_size = 1000
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
                    project_id=f"{self.table_ref.entity}/{self.table_ref.project}",
                    table_digest=self.table_ref.digest,
                    # TODO: must do paging or this will infinite loop
                    # if table is larger than page_size!
                    # filter=self.filter,
                )
            )
            for item in response.rows:
                new_ref = self.ref.with_item(item.digest)
                yield make_trace_obj(
                    item.val,
                    new_ref,
                    self.server,
                    self.root,
                )
                i += 1
            if len(response.rows) < page_size:
                break
            page_index += 1

    def append(self, val: Any) -> None:
        if not isinstance(self.ref, ObjectRef):
            raise ValueError("Can only append to object refs")
        self.root.add_mutation(self.ref.extra, "append", val)


class TraceList(Tracable, list):
    def __init__(
        self,
        *args: Any,
        **kwargs: Any,
    ):
        self.ref: RefWithExtra = kwargs.pop("ref")
        self.server: TraceServerInterface = kwargs.pop("server")
        root: Optional[Tracable] = kwargs.pop("root", None)
        if root is None:
            root = self
        self.root = root
        super().__init__(*args, **kwargs)

    def __getitem__(self, i: Union[SupportsIndex, slice]) -> Any:
        if isinstance(i, slice):
            raise ValueError("Slices not yet supported")
        index = operator.index(i)
        new_ref = self.ref.with_index(index)
        index_val = super().__getitem__(index)
        return make_trace_obj(index_val, new_ref, self.server, self.root)

    def __iter__(self) -> Iterator[Any]:
        for i in range(len(self)):
            yield self[i]


class TraceDict(Tracable, dict):
    def __init__(
        self,
        val: dict,
        ref: RefWithExtra,
        server: TraceServerInterface,
        root: typing.Optional[Tracable],
    ) -> None:
        self.val = val
        self.ref = ref
        self.server = server
        if root is None:
            root = self
        self.root = root

    def __getitem__(self, key: str) -> Any:
        new_ref = self.ref.with_key(key)
        return make_trace_obj(self.val[key], new_ref, self.server, self.root)

    def get(self, key: str, default: Any = None) -> Any:
        new_ref = self.ref.with_key(key)
        return make_trace_obj(
            self.val.get(key, default), new_ref, self.server, self.root
        )

    def __setitem__(self, key: str, value: Any) -> None:
        if not isinstance(self.ref, ObjectRef):
            raise ValueError("Can only set items on object refs")
        self.val[key] = value
        self.root.add_mutation(self.ref.extra, "setitem", key, value)

    def keys(self):  # type: ignore
        return self.val.keys()

    def values(self):  # type: ignore
        return self.val.values()

    def items(self):  # type: ignore
        for k in self.keys():
            yield k, self[k]

    def __iter__(self) -> Iterator[Any]:
        return iter(self.val)

    def __repr__(self) -> str:
        return f"TraceDict({self.val})"

    def __eq__(self, other: Any) -> bool:
        return self.val == other


def make_trace_obj(
    val: Any,
    new_ref: RefWithExtra,
    server: TraceServerInterface,
    root: Optional[Tracable],
) -> Any:
    if isinstance(val, Tracable):
        # If val is a TraceTable, we want to refer to it via the outer object
        # that it is within, rather than via the TableRef. For example we
        # want Dataset row refs to be Dataset.rows[id] rather than table[id]
        if isinstance(val, TraceTable):
            val.ref = new_ref
        return val
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
        val = from_json(read_res.obj.val, val.entity + "/" + val.project, server)

    if isinstance(val, TableRef):
        val = TraceTable(val, new_ref, server, _TableRowFilter(), root)

    if extra:
        # This is where extra resolution happens?
        for extra_index in range(0, len(extra), 2):
            op, arg = extra[extra_index], extra[extra_index + 1]
            if op == KEY_EDGE_TYPE:
                val = val[arg]
            elif op == ATTRIBUTE_EDGE_TYPE:
                val = getattr(val, arg)
            elif op == INDEX_EDGE_TYPE:
                val = val[int(arg)]
            elif op == ID_EDGE_TYPE:
                val = val[arg]
            else:
                raise ValueError(f"Unknown ref type: {extra[extra_index]}")

            # need to deref if we encounter these
            if isinstance(val, TableRef):
                val = TraceTable(val, new_ref, server, _TableRowFilter(), root)

    if not isinstance(val, Tracable):
        if isinstance(val, ObjectRecord):
            return TraceObject(val, new_ref, server, root)
        elif isinstance(val, list):
            return TraceList(val, ref=new_ref, server=server, root=root)
        elif isinstance(val, dict):
            return TraceDict(val, new_ref, server, root)
    box_val = box.box(val)
    setattr(box_val, "ref", new_ref)
    return box_val
