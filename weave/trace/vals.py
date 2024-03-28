import inspect
from typing import Iterator, Literal, Any, Union, Optional, Generator, SupportsIndex
import dataclasses
import operator
import typing

from weave.trace.op import Op
from weave.trace.refs import (
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

        # This condition attempts to bind the current `self` to the attribute if
        # it happens to be both an `Op` and have a `self` argument. This is a
        # bit of a hack since we are not always sure that the current object is
        # the correct object to bind. There are 3 cases:
        # 1. The attribute is part of the instance methods and the binding is
        #    correct
        # 2. The attribute is assigned as a property and is not bound at
        #    assignment time. In this case, it is "unlikely" that the args
        #    contain a `self` argument - which is why we apply this heuristic.
        # 3. The attribute is assigned as a property and is bound to another
        #    object at the time of assignment. In this case, the binding is
        #    incorrect. However, in our evaluation use case we do not have this
        #    case. We are accepting the incorrect assignment here for the sake
        #    of expediency, but should be fixed.
        if isinstance(val_attr_val, Op) and inspect.signature(
            val_attr_val.resolve_fn
        ).parameters.get("self"):
            val_attr_val = val_attr_val.__get__(self, type(self))

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
        self._loaded_rows: typing.Optional[typing.List[typing.Dict]] = None

    def __len__(self) -> int:
        return len(self._all_rows())

    def _all_rows(self) -> typing.List[typing.Dict]:
        # TODO: This is not an efficient way to do this - we essentially
        # load the entire set of rows the first time we need anything. However
        # the previous implementation loaded the entire set of rows for every action
        # so this is still better.
        if self._loaded_rows == None:
            self._loaded_rows = [row for row in self._remote_iter()]

        return typing.cast(typing.List[typing.Dict], self._loaded_rows)

    def _remote_iter(self) -> Generator[typing.Dict, None, None]:
        page_index = 0
        page_size = 1000
        i = 0
        while True:
            response = self.server.table_query(
                TableQueryReq(
                    project_id=f"{self.table_ref.entity}/{self.table_ref.project}",
                    table_digest=self.table_ref.digest,
                    offset=page_index * page_size,
                    limit=page_size,
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

    def __getitem__(self, key: Union[int, slice, str]) -> Any:
        rows = self._all_rows()
        if isinstance(key, slice):
            return rows[key]
        elif isinstance(key, int):
            return rows[key]
        else:
            for row in rows:
                if row.ref.extra[-1] == key:  # type: ignore
                    return row
            else:
                raise KeyError(f"Row ID not found: {key}")

    def __iter__(self) -> Generator[Any, None, None]:
        for row in self._all_rows():
            yield row

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

    def __repr__(self) -> str:
        return f"TraceList({super().__repr__()})"


class TraceDict(Tracable, dict):
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

    def __getitem__(self, key: str) -> Any:
        new_ref = self.ref.with_key(key)
        return make_trace_obj(super().__getitem__(key), new_ref, self.server, self.root)

    def get(self, key: str, default: Any = None) -> Any:
        new_ref = self.ref.with_key(key)
        return make_trace_obj(
            super().get(key, default), new_ref, self.server, self.root
        )

    def __setitem__(self, key: str, value: Any) -> None:
        if not isinstance(self.ref, ObjectRef):
            raise ValueError("Can only set items on object refs")
        super().__setitem__(key, value)
        self.root.add_mutation(self.ref.extra, "setitem", key, value)

    def keys(self):  # type: ignore
        return super().keys()

    def values(self):  # type: ignore
        for k in self.keys():
            yield self[k]

    def items(self):  # type: ignore
        for k in self.keys():
            yield k, self[k]

    def __iter__(self) -> Iterator[str]:
        # Simply define this to so that d = TraceDict({'a': 1, 'b': 2})); d2 = dict(d)
        # works. The dict(d) constructor works differently if __iter__ is not defined
        # on d.
        return super().__iter__()

    def __repr__(self) -> str:
        return f"TraceDict({super().__repr__()})"


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
    if hasattr(val, "ref") and isinstance(val.ref, RefWithExtra):
        # The Tracable check above does not currently work for Ops, where we
        # directly attach a ref, or to our Boxed classes. We should use Tracable
        # for all of these, but for now we need to check for the ref attribute.
        return val
    # Derefence val and create the appropriate wrapper object
    extra: list[str] = []
    if isinstance(val, ObjectRef):
        new_ref = val
        extra = val.extra
        read_res = server.obj_read(
            ObjReadReq(
                project_id=f"{val.entity}/{val.project}",
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
            return TraceDict(val, ref=new_ref, server=server, root=root)
    box_val = box.box(val)
    setattr(box_val, "ref", new_ref)
    return box_val
