import dataclasses
import inspect
import logging
import operator
import typing
from typing import Any, Generator, Iterator, Literal, Optional, SupportsIndex, Union

from pydantic import BaseModel
from pydantic import v1 as pydantic_v1

from weave.trace import box
from weave.trace.client_context.weave_client import get_weave_client
from weave.trace.context import get_raise_on_captured_errors
from weave.trace.errors import InternalError
from weave.trace.object_record import ObjectRecord
from weave.trace.op import is_op, maybe_bind_method
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
from weave.trace.table import Table
from weave.trace_server.trace_server_interface import (
    ObjReadReq,
    TableQueryReq,
    TableRowFilter,
    TraceServerInterface,
)

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class MutationSetitem:
    path: tuple[str, ...]
    operation: Literal["setitem"]
    args: tuple[str, Any]


@dataclasses.dataclass
class MutationSetattr:
    path: tuple[str, ...]
    operation: Literal["setattr"]
    args: tuple[str, Any]


@dataclasses.dataclass
class MutationAppend:
    path: tuple[str, ...]
    operation: Literal["append"]
    args: tuple[Any]


Mutation = Union[MutationSetattr, MutationSetitem, MutationAppend]
MutationOperation = Union[Literal["setitem"], Literal["setattr"], Literal["append"]]


def make_mutation(
    path: tuple[str, ...], operation: MutationOperation, args: tuple[Any, ...]
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


class Traceable:
    ref: Optional[RefWithExtra]
    mutations: Optional[list[Mutation]] = None
    root: "Traceable"
    parent: Optional["Traceable"] = None
    server: TraceServerInterface
    _is_dirty: bool = False

    def _mark_dirty(self) -> None:
        """Recursively mark this object and its ancestors as dirty and removes their refs."""
        self._is_dirty = True
        self.ref = None
        if (
            # Written this way to satisfy mypy
            self.parent is not self
            and self.parent is not None
            and hasattr(self.parent, "_mark_dirty")
        ):
            self.parent._mark_dirty()

    def add_mutation(
        self, path: tuple[str, ...], operation: MutationOperation, *args: Any
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
        return maybe_bind_method(val_attr_val, self)

    if (ref := getattr(self, "ref", None)) is None:
        # Even if we have not parent ref, if our current value is an object
        # ref, we should still process it with make_trace_obj. Practically,
        # this allows a user to "get" a Model, update a field, then invoke it.
        # Primary test: `test_dirty_model_op_retrieval`
        if not isinstance(val_attr_val, ObjectRef):
            return val_attr_val
        new_ref = None
    else:
        new_ref = ref.with_attr(attr_name)

    if server is None:
        return val_attr_val

    root = getattr(self, "root", None)

    return make_trace_obj(
        val_attr_val,
        new_ref,
        server,
        root,
        self,
    )


class WeaveObject(Traceable):
    def __init__(
        self,
        val: Any,
        ref: Optional[RefWithExtra],
        server: TraceServerInterface,
        root: typing.Optional[Traceable],
        parent: Optional[Traceable] = None,
    ) -> None:
        self._val = val
        self.ref = ref
        self.server = server
        self.root = root or self
        self.parent = parent

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
        if __name in [
            "_val",
            "ref",
            "server",
            "root",
            "mutations",
            "_is_dirty",
            "parent",
        ]:
            return object.__setattr__(self, __name, __value)
        else:
            self._mark_dirty()
            if isinstance(__value, Traceable):
                __value.parent = self

            return setattr(self._val, __name, __value)

    def __dir__(self) -> list[str]:
        return dir(self._val)

    def __repr__(self) -> str:
        return f"WeaveObject({self._val})"

    def __eq__(self, other: Any) -> bool:
        return self._val == other


class WeaveTable(Traceable):
    filter: TableRowFilter

    def __init__(
        self,
        table_ref: Optional[TableRef],
        ref: Optional[RefWithExtra],
        server: TraceServerInterface,
        filter: TableRowFilter,
        root: Optional[Traceable],
        parent: Optional[Traceable] = None,
    ) -> None:
        self.table_ref = table_ref
        self.filter = filter
        self.ref = ref  # type: ignore
        self.server = server
        self.root = root or self
        self.parent = parent
        self._rows: Optional[list[dict]] = None

        # _prefetched_rows is a local cache of rows that can be used to
        # avoid a remote call. Should only be used by internal code.
        self._prefetched_rows: Optional[list[dict]] = None

    @property
    def rows(self) -> list[dict]:
        if self._rows is None:
            should_local_iter = (
                self.ref is not None
                and self.table_ref is not None
                and self.table_ref._row_digests is not None
                and self._prefetched_rows is not None
            )
            if should_local_iter:
                self._rows = list(self._local_iter_with_remote_fallback())
            else:
                self._rows = list(self._remote_iter())
        return self._rows

    @rows.setter
    def rows(self, value: list[dict]) -> None:
        if not all(isinstance(row, dict) for row in value):
            raise ValueError("All table rows must be dicts")

        self._rows = value
        self._mark_dirty()

    def set_prefetched_rows(self, prefetched_rows: list[dict]) -> None:
        """Sets the rows to a local cache of rows that can be used to
        avoid a remote call. Should only be used by internal code.

        It is expected that these rows are the exact same rows that would
        be returned by a query for this table. Failing to meet this expectation
        will cause table operations to behave unexpectedly.
        """
        if self._rows is not None:
            raise ValueError(
                "Cannot set prefetched rows on WeaveTable when rows are already loaded"
            )
        self._prefetched_rows = prefetched_rows

    def __len__(self) -> int:
        return len(self.rows)

    def __eq__(self, other: Any) -> bool:
        return self.rows == other

    def _mark_dirty(self) -> None:
        self.table_ref = None
        self._prefetched_rows = None
        super()._mark_dirty()

    def _local_iter_with_remote_fallback(self) -> Generator[dict, None, None]:
        """
        This is the case where we:
        1. Have all the rows in memory
        2. Have all the row digests

        In this case, we don't need to make any calls and can just return the rows
        """
        wc = get_weave_client()
        if (
            wc is None
            or self.ref is None
            or self.table_ref is None
            or self.table_ref._row_digests is None
            or self._prefetched_rows is None
        ):
            if get_raise_on_captured_errors():
                raise
            logger.error(
                "Expected all row digests and prefetched rows to be set, falling back to remote iteration"
            )
            yield from self._remote_iter()
            return

        cached_table_ref = self.table_ref
        if isinstance(self.table_ref._row_digests, list):
            # Only do this check if it is resolved
            row_digest_len = len(self.table_ref._row_digests)
            prefetched_rows_len = len(self._prefetched_rows)
            if row_digest_len != prefetched_rows_len:
                if get_raise_on_captured_errors():
                    raise
                logger.error(
                    f"Expected length of row digests ({row_digest_len}) to match prefetched rows ({prefetched_rows_len}). Falling back to remote iteration."
                )
                yield from self._remote_iter()
                return

        for ndx, row in enumerate(self._prefetched_rows):
            next_id_future = wc.future_executor.defer(
                lambda: cached_table_ref.row_digests[ndx]
            )
            new_ref = self.ref.with_item(next_id_future)
            val = self._prefetched_rows[ndx]
            res = from_json(
                val, self.table_ref.entity + "/" + self.table_ref.project, self.server
            )
            res = make_trace_obj(res, new_ref, self.server, self.root)
            yield res

    def _remote_iter(self) -> Generator[dict, None, None]:
        page_index = 0
        page_size = 100
        while True:
            if self.table_ref is None:
                break

            response = self.server.table_query(
                TableQueryReq(
                    project_id=f"{self.table_ref.entity}/{self.table_ref.project}",
                    digest=self.table_ref.digest,
                    offset=page_index * page_size,
                    limit=page_size,
                    # filter=self.filter,
                )
            )

            if self._prefetched_rows is not None and len(response.rows) != len(
                self._prefetched_rows
            ):
                if get_raise_on_captured_errors():
                    raise
                logger.error(
                    f"Expected length of response rows ({len(response.rows)}) to match prefetched rows ({len(self._prefetched_rows)}). Ignoring prefetched rows."
                )
                self._prefetched_rows = None

            for ndx, item in enumerate(response.rows):
                new_ref = self.ref.with_item(item.digest) if self.ref else None
                # Here, we use the raw rows if they exist, otherwise we use the
                # rows from the server. This is a temporary trick to ensure
                # we don't re-deserialize the rows on every access. Once all servers
                # return digests, this branch can be removed because anytime we have prefetched
                # rows we should also have the digests - and we should be in the
                #  _local_iter_with_remote_fallback case.
                val = (
                    item.val
                    if self._prefetched_rows is None
                    else self._prefetched_rows[ndx]
                )
                res = from_json(
                    val,
                    self.table_ref.entity + "/" + self.table_ref.project,
                    self.server,
                )
                res = make_trace_obj(res, new_ref, self.server, self.root)
                yield res

            if len(response.rows) < page_size:
                break

            page_index += 1

    def __getitem__(self, key: Union[int, slice, str]) -> Any:
        rows = self.rows
        if isinstance(key, (int, slice)):
            return rows[key]

        for row in rows:
            if row.ref.extra[-1] == key:  # type: ignore
                return row

        raise KeyError(f"Row ID not found: {key}")

    def __iter__(self) -> Iterator[dict]:
        return iter(self.rows)

    def append(self, val: dict) -> None:
        if not isinstance(val, dict):
            raise ValueError("Can only append dicts to tables")
        self._mark_dirty()
        self.rows.append(val)

    def pop(self, index: int) -> None:
        self._mark_dirty()
        self.rows.pop(index)


class WeaveList(Traceable, list):
    def __init__(
        self,
        *args: Any,
        server: TraceServerInterface,
        ref: Optional[RefWithExtra] = None,
        root: Optional[Traceable] = None,
        parent: Optional[Traceable] = None,
    ) -> None:
        self.server = server

        self.ref = ref
        self.root = root if root is not None else self
        self.parent = parent
        super().__init__(*args)

    def __getitem__(self, i: Union[SupportsIndex, slice]) -> Any:
        if isinstance(i, slice):
            raise ValueError("Slices not yet supported")
        index = operator.index(i)
        new_ref = self.ref.with_index(index) if self.ref else None
        index_val = super().__getitem__(index)
        return make_trace_obj(index_val, new_ref, self.server, self.root)

    def __setitem__(self, i: Union[SupportsIndex, slice], value: Any) -> None:
        if isinstance(i, slice):
            raise ValueError("Slices not yet supported")
        if (index := operator.index(i)) >= len(self):
            raise IndexError("list assignment index out of range")

        # Though this ostensibly only marks the parent (list) as dirty, siblings
        # will also get new refs because their old refs are relative to the parent
        # (the element refs will be extras of the new parent ref)
        self._mark_dirty()
        if isinstance(value, Traceable):
            value.parent = self

        super().__setitem__(index, value)

    def append(self, item: Any) -> None:
        self._mark_dirty()
        if isinstance(item, Traceable):
            item.parent = self

        super().append(item)

    def __iter__(self) -> Iterator[Any]:
        for i in range(len(self)):
            yield self[i]

    def __repr__(self) -> str:
        return f"WeaveList({super().__repr__()})"

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, list):
            return False
        if len(self) != len(other):
            return False
        for v1, v2 in zip(self, other):
            if v1 != v2:
                return False
        return True


class WeaveDict(Traceable, dict):
    def __init__(
        self,
        *args: Any,
        server: TraceServerInterface,
        ref: Optional[RefWithExtra] = None,
        root: Optional[Traceable] = None,
        parent: Optional[Traceable] = None,
        **kwargs: Any,
    ) -> None:
        self.server = server

        self.ref = ref
        self.root = root if root is not None else self
        self.parent = parent
        super().__init__(*args, **kwargs)

    def __getitem__(self, key: str) -> Any:
        new_ref = self.ref.with_key(key) if self.ref else None
        v = super().__getitem__(key)
        return make_trace_obj(v, new_ref, self.server, self.root)

    def get(self, key: str, default: Any = None) -> Any:
        new_ref = self.ref.with_key(key) if self.ref else None
        v = super().get(key, default)
        return make_trace_obj(v, new_ref, self.server, self.root)

    def __setitem__(self, key: str, value: Any) -> None:
        # Though this ostensibly only marks the parent (dict) as dirty, siblings
        # will also get new refs because their old refs are relative to the parent
        # (the element refs will be extras of the new parent ref)
        self._mark_dirty()
        if isinstance(value, Traceable):
            value.parent = self

        super().__setitem__(key, value)

    def keys(self) -> Generator[Any, Any, Any]:  # type: ignore
        yield from super().keys()

    def values(self) -> Generator[Any, Any, Any]:  # type: ignore
        for k in self.keys():
            yield self[k]

    def items(self) -> Generator[tuple[Any, Any], Any, Any]:  # type: ignore
        for k in self.keys():
            yield k, self[k]

    def __iter__(self) -> Iterator[str]:
        # Simply define this to so that d = WeaveDict({'a': 1, 'b': 2})); d2 = dict(d)
        # works. The dict(d) constructor works differently if __iter__ is not defined
        # on d.
        return super().__iter__()

    def __repr__(self) -> str:
        return f"WeaveDict({super().__repr__()})"

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, dict):
            return False
        if len(self) != len(other):
            return False
        for k, v in self.items():
            if k not in other:
                return False
            if other[k] != v:
                return False
        return True


def make_trace_obj(
    val: Any,
    new_ref: Optional[RefWithExtra],  # Can this actually be None?
    server: TraceServerInterface,
    root: Optional[Traceable],
    parent: Any = None,
) -> Any:
    if isinstance(val, Traceable):
        # If val is a WeaveTable, we want to refer to it via the outer object
        # that it is within, rather than via the TableRef. For example we
        # want Dataset row refs to be Dataset.rows[id] rather than table[id]
        if isinstance(val, WeaveTable):
            val.ref = new_ref
        return val
    if hasattr(val, "ref") and isinstance(val.ref, RefWithExtra):
        # The Traceable check above does not currently work for Ops, where we
        # directly attach a ref, or to our Boxed classes. We should use Traceable
        # for all of these, but for now we need to check for the ref attribute.
        return val
    # Derefence val and create the appropriate wrapper object
    extra: tuple[str, ...] = ()
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
        rows = val.rows
        val = WeaveTable(
            table_ref=val_ref,
            ref=new_ref,
            server=server,
            filter=TableRowFilter(),
            root=root,
            parent=parent,
        )
        # Use in memory rows! This is the case where we are making
        # a trace object from an existing Table! If we don't do this
        # then the WeaveTable will try to fetch all the rows from the
        # server, throwing away the in memory rows. This is really expensive
        # when we are doing evaluations!
        val.set_prefetched_rows(rows)
    if isinstance(val, TableRef):
        val = WeaveTable(
            table_ref=val,
            ref=new_ref,
            server=server,
            filter=TableRowFilter(),
            root=root,
            parent=parent,
        )

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
                val = WeaveTable(
                    table_ref=val,
                    ref=new_ref,
                    server=server,
                    filter=TableRowFilter(),
                    root=root,
                    parent=parent,
                )

    if not isinstance(val, Traceable):
        if isinstance(val, ObjectRecord):
            return WeaveObject(
                val, ref=new_ref, server=server, root=root, parent=parent
            )
        elif isinstance(val, list):
            return WeaveList(val, ref=new_ref, server=server, root=root, parent=parent)
        elif isinstance(val, dict):
            return WeaveDict(val, ref=new_ref, server=server, root=root)
    if is_op(val) and inspect.signature(val.resolve_fn).parameters.get("self"):
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
        # TODO: This binding is correct but not done for consistency with the
        # not-yet-saved-method-op API which requires explicitly passing self
        # val.call = partial(call, val, parent)
        val = maybe_bind_method(val, parent)
    box_val = box.box(val)
    if isinstance(box_val, pydantic_v1.BaseModel) or is_op(val):
        box_val.__dict__["ref"] = new_ref
    elif box_val is None or isinstance(box_val, bool):
        # We intentionally don't box None and bools because it's imposible to
        # make them behave like the underlying True/False/None objects in python.
        # This is unlike other objects (dict, list, int) that can be inherited
        # from and compared.

        # The tradeoff we're making here is:
        # 1. We won't ref track bools or None when passed into a call; but
        # 2. Users can compare them pythonically (e.g. `x is None` vs. `x == None`)

        pass
    else:
        if hasattr(box_val, "ref"):
            setattr(box_val, "ref", new_ref)
    return box_val


class MissingSelfInstanceError(ValueError):
    pass
