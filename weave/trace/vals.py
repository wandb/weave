import dataclasses
import inspect
import operator
import typing
from typing import Any, Generator, Iterator, Literal, Optional, SupportsIndex, Union

from pydantic import BaseModel
from pydantic import v1 as pydantic_v1

from weave.client_context.weave_client import get_weave_client
from weave.legacy import box
from weave.table import Table
from weave.trace.errors import InternalError
from weave.trace.object_record import ObjectRecord
from weave.trace.op import Op
from weave.trace.refs import (
    DICT_KEY_EDGE_NAME,
    LIST_INDEX_EDGE_NAME,
    OBJECT_ATTR_EDGE_NAME,
    TABLE_ROW_ID_EDGE_NAME,
    ObjectRef,
    RefWithExtra,
    TableRef,
)
from weave.trace.serialize import from_json
from weave.trace_server.trace_server_interface import (
    ObjReadReq,
    TableQueryReq,
    TraceServerInterface,
    _TableRowFilter,
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


def pydantic_getattribute(self: BaseModel, name: str) -> Any:
    attribute = object.__getattribute__(self, name)
    if name not in object.__getattribute__(self, "model_fields"):
        return attribute
    if name == "ref":
        try:
            return object.__getattribute__(self, "ref")
        except AttributeError:
            return None

    server = gc.server if (gc := get_weave_client()) else None
    res = attribute_access_result(self, attribute, name, server=server)

    # We need this because we override __getattribute__ and wrap the returned values.
    # The wrapped result may be mutable (e.g. list), so we need to replace the attribute
    # on self so that mutations are applied to the correct object and the user gets back
    # what they expect when they call `self.<name>`.
    self.__dict__[name] = res
    return res


def attribute_access_result(
    self: object,
    val_attr_val: Any,
    attr_name: str,
    *,
    server: Optional[TraceServerInterface],
) -> Any:
    # Not ideal, what about properties?
    if callable(val_attr_val):
        return val_attr_val

    ref = None
    try:
        ref = self.ref  # type: ignore
    except AttributeError:
        pass
    if ref is None:
        return val_attr_val

    new_ref = ref.with_attr(attr_name)

    if server is None:
        return val_attr_val

    return make_trace_obj(
        val_attr_val,
        new_ref,
        server,
        None,  # TODO: not passing root, needed for mutate which is not implemented yet
        # self.root,
        self,
    )


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
        result = attribute_access_result(self, val_attr_val, __name, server=self.server)
        # Store the result on _val so we don't deref next time.
        try:
            object.__setattr__(self._val, __name, result)
        except AttributeError:
            # Happens if self._val.<name> is a property. Return the raw value instead
            # of a Traceable value.
            return val_attr_val
        return result

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

    def __dir__(self) -> list[str]:
        return dir(self._val)

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
                    digest=self.table_ref.digest,
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
    parent: Any = None,
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
                object_id=val.name,
                digest=val.digest,
            )
        )
        val = from_json(read_res.obj.val, val.entity + "/" + val.project, server)

    if isinstance(val, Table):
        val_ref = val.ref
        if not isinstance(val_ref, TableRef):
            val_table_ref = getattr(val, "table_ref", None)
            if not isinstance(val_table_ref, TableRef):
                raise InternalError(
                    "Expected Table.ref or Table.table_ref to be TableRef"
                )
            val_ref = val_table_ref
        val = TraceTable(val_ref, new_ref, server, _TableRowFilter(), root)
    if isinstance(val, TableRef):
        val = TraceTable(val, new_ref, server, _TableRowFilter(), root)

    if extra:
        # This is where extra resolution happens?
        for extra_index in range(0, len(extra), 2):
            op, arg = extra[extra_index], extra[extra_index + 1]
            if op == DICT_KEY_EDGE_NAME:
                val = val[arg]
            elif op == OBJECT_ATTR_EDGE_NAME:
                val = getattr(val, arg)
            elif op == LIST_INDEX_EDGE_NAME:
                val = val[int(arg)]
            elif op == TABLE_ROW_ID_EDGE_NAME:
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
    if isinstance(val, Op) and inspect.signature(val.resolve_fn).parameters.get("self"):
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
        if parent is None:
            raise MissingSelfInstanceError(
                f"{val.name} Op requires a bound self instance. Must be called from an instance method."
            )
        val = val.__get__(parent, type(parent))
    box_val = box.box(val)
    if isinstance(box_val, pydantic_v1.BaseModel):
        box_val.__dict__["ref"] = new_ref
    else:
        setattr(box_val, "ref", new_ref)
    return box_val


class MissingSelfInstanceError(ValueError):
    pass
