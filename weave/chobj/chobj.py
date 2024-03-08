from typing import Optional, Any, TypedDict, Literal, Union
import clickhouse_connect
import copy
import uuid
import json
import dataclasses
from rich import print

from weave import box


class Ref:
    pass


def log_ch_commands():
    from clickhouse_connect.driver import httpclient
    from clickhouse_connect.driver import client

    orig_command = httpclient.HttpClient.command

    def logging_command(*args, **kwargs):
        print("CH Command", args, kwargs)
        return orig_command(*args, **kwargs)

    httpclient.HttpClient.command = logging_command

    orig_query = client.Client.query

    def logging_query(*args, **kwargs):
        print("CH Query", args, kwargs)
        return orig_query(*args, **kwargs)

    client.Client.query = logging_query


# log_ch_commands()


@dataclasses.dataclass
class TableRef(Ref):
    table_id: uuid.UUID

    def uri(self) -> str:
        return f"table:///{self.table_id}"


@dataclasses.dataclass
class ValRef(Ref):
    val_id: uuid.UUID
    extra: list[str] = dataclasses.field(default_factory=list)

    def uri(self) -> str:
        u = f"val:///{self.val_id}"
        if self.extra:
            u += "/" + "/".join(self.extra)
        return u

    def with_key(self, key) -> "ValRef":
        return ValRef(self.val_id, self.extra + ["key", key])

    def with_attr(self, attr) -> "ValRef":
        return ValRef(self.val_id, self.extra + ["attr", attr])

    def with_id(self, index) -> "ValRef":
        return ValRef(self.val_id, self.extra + ["id", index])


@dataclasses.dataclass
class ObjectRef(Ref):
    name: str
    val_id: uuid.UUID
    extra: list[str] = dataclasses.field(default_factory=list)

    def uri(self) -> str:
        u = f"object:///{self.name}/{self.val_id}"
        if self.extra:
            u += "/" + "/".join(self.extra)
        return u

    def with_key(self, key) -> "ObjectRef":
        return ObjectRef(self.name, self.val_id, self.extra + ["key", key])

    def with_attr(self, attr) -> "ObjectRef":
        return ObjectRef(self.name, self.val_id, self.extra + ["attr", attr])

    def with_id(self, index) -> "ObjectRef":
        return ObjectRef(self.name, self.val_id, self.extra + ["id", index])


def dataclasses_asdict_one_level(obj):
    # dataclasses.asdict is recursive. We don't want that when json encoding
    return {f.name: getattr(obj, f.name) for f in dataclasses.fields(obj)}


class RefEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, uuid.UUID):
            return {"_type": "UUID", "uuid": o.hex}
        elif dataclasses.is_dataclass(o):
            data = dataclasses_asdict_one_level(o)
            return {"_type": o.__class__.__name__, **data}
        elif isinstance(o, ObjectRecord):
            return o.__dict__
        return json.JSONEncoder.default(self, o)


def json_dumps(val):
    return json.dumps(val, cls=RefEncoder)


def refs(val):
    result_refs = []

    def find_refs(inner_val):
        if isinstance(inner_val, Ref):
            result_refs.append(inner_val)
        else:
            check_val = None
            if isinstance(inner_val, dict):
                check_val = inner_val.values()
            elif isinstance(inner_val, list):
                check_val = inner_val
            elif isinstance(inner_val, ObjectRecord):
                check_val = inner_val.__dict__.values()
            elif dataclasses.is_dataclass(inner_val):
                check_val = dataclasses_asdict_one_level(inner_val).values()
            if check_val:
                for val in check_val:
                    find_refs(val)

    find_refs(val)

    # TODO: ref.uri() instead of str()
    return [str(r) for r in result_refs]


class ObjectRecord:
    def __init__(self, attrs):
        for k, v in attrs.items():
            setattr(self, k, v)

    def __repr__(self):
        return f"ObjectRecord({self.__dict__})"

    def __eq__(self, other):
        if other.__class__.__name__ != getattr(self, "_type"):
            return False
        for k, v in self.__dict__.items():
            if k == "_type" or k == "id":
                continue
            if getattr(other, k) != v:
                return False
        return True


def ref_decoder(d):
    if "_type" in d:
        if d["_type"] == "UUID":
            return uuid.UUID(d["uuid"])
        elif d["_type"] == "TableRef":
            return TableRef(d["table_id"])
        elif d["_type"] == "ValRef":
            return ValRef(d["val_id"])
        elif d["_type"] == "ObjectRef":
            return ObjectRef(d["name"], d["val_id"], d["extra"])
        else:
            return ObjectRecord(d)
    return d


def json_loads(d):
    return json.loads(d, object_hook=ref_decoder)


class ValueFilter(TypedDict):
    ref: Optional[Ref]
    val: Optional[dict]


def make_value_filter(filter: ValueFilter):
    query_parts = []
    if filter["val"]:
        for key, value in filter["val"].items():
            # Assume all values are to be treated as strings for simplicity. Adjust the casting as necessary.
            query_part = f"JSONExtractString(val, '{key}') = '{value}'"
            query_parts.append(query_part)
    elif filter["ref"]:
        ref = filter["ref"]
        query_parts.append(f"{ref} IN refs")
    return " AND ".join(query_parts)


class ObjectServer:
    def __init__(self):
        self.client = clickhouse_connect.get_client()

    def drop_tables(self):
        # TODO: branches
        self.client.command("DROP TABLE IF EXISTS objects")
        self.client.command("DROP TABLE IF EXISTS values")
        self.client.command("DROP TABLE IF EXISTS tables")
        self.client.command("DROP TABLE IF EXISTS table_transactions")

    def create_tables(self):
        self.client.command(
            """
            CREATE TABLE IF NOT EXISTS objects
            (
                id UUID,
                name String,
                branch String,
                created_at DateTime64 DEFAULT now64(),
                # TODO: should be a ref always
                val String
            ) 
            ENGINE = MergeTree() 
            ORDER BY (name, branch, created_at)"""
        )
        self.client.command(
            """
            CREATE TABLE IF NOT EXISTS values
            (
                id UUID,
                created_at DateTime64 DEFAULT now64(),
                refs Array(String),
                # TODO: should be type, val
                val String
            ) 
            ENGINE = MergeTree() 
            ORDER BY (id, created_at)"""
        )
        self.client.command(
            """
            CREATE TABLE IF NOT EXISTS tables
            (
                id UUID,
                created_at DateTime64 DEFAULT now64(),
                transaction_ids Array(UUID)
            ) 
            ENGINE = MergeTree() 
            ORDER BY (id)"""
        )
        self.client.command(
            """
            CREATE TABLE IF NOT EXISTS table_transactions
            (
                id UUID,
                item_id UUID,
                created_at DateTime64 DEFAULT now64(),
                tx_order UInt32,
                refs Array(String),
                val Nullable(String)
            ) 
            ENGINE = MergeTree() 
            ORDER BY (id, tx_order)"""
        )

    def new_table(self, initial_table: list):
        tx_id = uuid.uuid4().hex
        tx_items = [
            (tx_id, uuid.uuid4().hex, i, refs(v), json_dumps(v))
            for i, v in enumerate(initial_table)
        ]
        self.client.insert(
            "table_transactions",
            data=tx_items,
            column_names=("id", "item_id", "tx_order", "refs", "val"),
        )
        table_id = uuid.uuid4()
        self.client.insert(
            "tables",
            data=[(table_id, [tx_id])],
            column_names=("id", "transaction_ids"),
        )
        return TableRef(table_id)

    def table_query(
        self,
        table_ref: TableRef,
        filter: Optional[ValueFilter] = None,
        offset: Optional[int] = 0,
        limit: Optional[int] = 100,
    ):
        predicate = make_value_filter(filter) if filter else "1 = 1"
        query_result = self.client.query(
            f"""
            WITH RankedItems AS (
                SELECT
                    id,
                    item_id,
                    FIRST_VALUE(tuple(created_at, tx_order)) OVER (PARTITION BY item_id ORDER BY (created_at, tx_order) DESC) AS item_record_time_order,
                    ROW_NUMBER() OVER (PARTITION BY item_id ORDER BY (created_at, tx_order) DESC) AS item_record_index,
                    val,
                FROM table_transactions
                WHERE id IN (
                    SELECT tx_id
                    FROM tables
                    ARRAY JOIN transaction_ids AS tx_id
                    WHERE id = %(table_id)s
                )
                ORDER BY item_record_time_order ASC
            )
            SELECT
            item_id, val
            FROM RankedItems
            WHERE item_record_index = 1 AND val IS NOT NULL AND {predicate}
            LIMIT %(limit)s OFFSET %(offset)s
            """,
            parameters={
                "table_id": table_ref.table_id,
                "offset": offset,
                "limit": limit,
            },
        )
        # TODO: we shouldn't json load here, this can be put on the wire
        # as encoded json, and then decoded on the read side (split server into
        # client/server pair)
        return [(r[0], json_loads(r[1])) for r in query_result.result_rows]

    def _add_table_transaction(self, table_ref: TableRef, tx_id: uuid.UUID):
        # TODO: this can be one command instead of two

        table_txs = self.client.query(
            """
            SELECT transaction_ids
            FROM tables
            WHERE id = %(table_id)s
            """,
            parameters={"table_id": table_ref.table_id},
        ).result_rows[0][0]
        new_table_id = uuid.uuid4()
        self.client.insert(
            "tables",
            data=[(new_table_id, table_txs + [tx_id])],
            column_names=("id", "transaction_ids"),
        )
        return TableRef(new_table_id)

    def table_append(self, table_ref: TableRef, value):
        tx_id = uuid.uuid4()
        item_id = uuid.uuid4()
        tx_items = [(tx_id, item_id, 0, json.dumps(value))]
        self.client.insert(
            "table_transactions",
            data=tx_items,
            column_names=("id", "item_id", "tx_order", "val"),
        )
        new_table_ref = self._add_table_transaction(table_ref, tx_id)
        return new_table_ref, item_id

    def table_remove(self, table_row_ref: TableRef, item_id: uuid.UUID):
        tx_id = uuid.uuid4()
        tx_items = [(tx_id, item_id, 0, None)]
        self.client.insert(
            "table_transactions",
            data=tx_items,
            column_names=("id", "item_id", "tx_order", "val"),
        )
        return self._add_table_transaction(TableRef(table_row_ref.table_id), tx_id)

    def new_val(self, val, value_id: Optional[uuid.UUID] = None):
        # map val (this could do more than lists_to_tables)
        def lists_to_tables(val):
            if isinstance(val, dict):
                return {k: lists_to_tables(v) for k, v in val.items()}
            elif isinstance(val, ObjectRecord):
                return ObjectRecord(
                    {k: lists_to_tables(v) for k, v in val.__dict__.items()}
                )
            elif isinstance(val, list):
                return self.new_table(val)
            return val

        val = lists_to_tables(val)

        # encode val
        encoded_val = json_dumps(val)

        if value_id is None:
            value_id = uuid.uuid4()
        self.client.insert(
            "values",
            data=[(value_id, refs(val), encoded_val)],
            column_names=("id", "refs", "val"),
        )
        return ValRef(val_id=value_id)

    def get_val(self, val_ref: ValRef):
        query_result = self.client.query(
            """
            SELECT val from values
            WHERE id = %(value_id)s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            parameters={"value_id": val_ref.val_id},
        )
        return json_loads(query_result.result_rows[0][0])

    def query_vals(
        self, filter: ValueFilter, offset: Optional[int] = 0, limit: Optional[int] = 100
    ):
        predicate = make_value_filter(filter)
        query_result = self.client.query(
            f"""
            SELECT val FROM (
                SELECT *,
                    ROW_NUMBER() OVER(PARTITION BY id ORDER BY created_at DESC) AS rn
                FROM values
            ) WHERE rn = 1 AND {predicate} ORDER BY created_at ASC
            LIMIT %(limit)s OFFSET %(offset)s
            """,
            parameters={"limit": limit, "offset": offset},
        )
        return [json_loads(r[0]) for r in query_result.result_rows]

    def new_object(self, val, name: str, branch: str) -> ObjectRef:
        val_ref = self.new_val(val)
        self.client.insert(
            "objects",
            data=[(uuid.uuid4(), name, branch, json_dumps(val_ref))],
            column_names=("id", "name", "branch", "val"),
        )
        return ObjectRef(name, val_ref.val_id)

    def _resolve_object(self, name: str, branch: str) -> Optional[ValRef]:
        query_result = self.client.query(
            """
            SELECT val from objects
            WHERE name = %(name)s AND branch = %(branch)s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            parameters={"name": name, "branch": branch},
        )
        result = query_result.result_rows
        if not result:
            return None
        return json_loads(result[0][0])

    def _apply_mutation(self, root, mutation: "Mutation"):
        val = root
        for i in range(0, len(mutation.path), 2):
            op, arg = mutation.path[i], mutation.path[i + 1]
            if isinstance(val, TableRef):
                if op == "id":
                    table_path = tuple(mutation.path[:i])
                    return None, (
                        table_path,
                        make_mutation(
                            [op, arg, *mutation.path[i + 2 :]],
                            mutation.operation,
                            mutation.args,
                        ),
                    )
                else:
                    raise ValueError(f"Unknown table op: {op}")
            if op == "attr":
                val = getattr(val, arg)
            elif op == "key":
                val = val[arg]
            elif op == "id":
                val = val[arg]
        if mutation.operation == "setattr":
            setattr(val, mutation.args[0], mutation.args[1])
        elif mutation.operation == "append":
            if isinstance(val, TableRef):
                return None, (
                    tuple(mutation.path),
                    make_mutation(
                        [],
                        mutation.operation,
                        mutation.args,
                    ),
                )
            else:
                val.append(mutation.args[0])
        elif mutation.operation == "setitem":
            val[mutation.args[0]] = mutation.args[1]
        return val, None

    def _table_mutate(self, table_ref: TableRef, mutations: list["Mutation"]):
        table_items = self.table_query(table_ref, limit=10000)
        if len(table_items) >= 100000:
            raise ValueError(
                "mutation not yet implemented for tables with >= 100000 items"
            )

        tx_id = uuid.uuid4()
        tx_append_items = []
        updated_row_ids = set()
        for mutation in mutations:
            if not mutation.path:
                if mutation.operation == "append":
                    item_id = uuid.uuid4()
                    tx_append_items.append(
                        (
                            tx_id,
                            item_id,
                            len(tx_append_items),
                            json.dumps(mutation.args[0]),
                        )
                    )
                else:
                    raise ValueError(
                        f"Mutation operation not yet supported on table root: {mutation.operation}"
                    )
            else:
                op, arg = mutation.path[0], mutation.path[1]
                if op != "id":
                    raise ValueError(
                        f"Mutation path incorrect for table: {mutation.path}"
                    )
                row_id = arg
                updated_row_ids.add(row_id)
                row = table_items[row_id][1]
                val = row
                for i in range(2, len(mutation.path), 2):
                    op, arg = mutation.path[i], mutation.path[i + 1]
                    if op == "key":
                        val = val[arg]
                    elif op == "id":
                        val = val[arg]
                    else:
                        raise ValueError(f"Unknown op: {op}")
                if mutation.operation == "setitem":
                    val[mutation.args[0]] = mutation.args[1]
                elif mutation.operation == "append":
                    val.append(mutation.args[0])
                else:
                    raise ValueError(
                        f"Mutation operation not yet supported: {mutation.operation}"
                    )
        tx_items = []
        for row_id in updated_row_ids:
            tx_items.append(
                (
                    tx_id,
                    table_items[row_id][0],
                    len(tx_items),
                    json.dumps(table_items[row_id][1]),
                )
            )
        for tx_append_item in tx_append_items:
            tx_items.append(
                (
                    tx_id,
                    tx_append_item[1],
                    len(tx_items),
                    tx_append_item[3],
                )
            )

        self.client.insert(
            "table_transactions",
            data=tx_items,
            column_names=("id", "item_id", "tx_order", "val"),
        )
        return self._add_table_transaction(table_ref, tx_id)

    def mutate(self, ref: ObjectRef, mutations: list["Mutation"]):
        root = self.get_val(ValRef(ref.val_id))
        table_mutations = {}
        for mutation in mutations:
            new_val, table_mutation = self._apply_mutation(root, mutation)
            if new_val is not None:
                root = new_val
            elif table_mutation is not None:
                table_mutations.setdefault(table_mutation[0], []).append(
                    table_mutation[1]
                )

        for table_path, mutations in table_mutations.items():
            table_ref_parent = root
            for i in range(0, len(table_path[:-2]), 2):
                op, arg = table_path[i], table_path[i + 1]
                table_ref_parent = apply_path_step(table_ref_parent, op, arg)
            table_ref = apply_path_step(
                table_ref_parent, table_path[-2], table_path[-1]
            )
            if not isinstance(table_ref, TableRef):
                raise ValueError("Expected table ref")
            new_table_ref = self._table_mutate(table_ref, mutations)
            # TODO: put table ref back into root
            set_path_step(
                table_ref_parent, table_path[-2], table_path[-1], new_table_ref
            )

        return self.new_object(root, ref.name, "latest")


def apply_path_step(val, op, arg):
    if op == "attr":
        return getattr(val, arg)
    elif op == "key":
        return val[arg]
    elif op == "id":
        return val[arg]
    raise ValueError(f"Unknown op: {op}")


def set_path_step(val, op, arg, new_val):
    if op == "attr":
        setattr(val, arg, new_val)
    elif op == "key":
        val[arg] = new_val
    elif op == "id":
        val[arg] = new_val
    else:
        raise ValueError(f"Unknown op: {op}")


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
    server: ObjectServer

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
    def __init__(self, table_ref, ref, server, filter, root):
        self.table_ref = table_ref
        self.filter = filter
        self.ref = ref
        self.server: ObjectServer = server
        self.root = root
        if self.root is None:
            self.root = self

    def __getitem__(self, i):
        page_data = self.server.table_query(
            self.table_ref, self.filter, offset=i, limit=1
        )
        return make_trace_obj(
            page_data[0][1], self.ref.with_id(i), self.server, self.root
        )

    def __iter__(self):
        page_index = 0
        page_size = 10
        i = 0
        while True:
            page_data = self.server.table_query(
                self.table_ref,
                self.filter,
                offset=page_index * page_size,
                limit=page_size,
            )
            for item in page_data:
                yield make_trace_obj(
                    item[1], self.ref.with_id(i), self.server, self.root
                )
                i += 1
            if len(page_data) < page_size:
                break
            page_index += 1

    def append(self, val):
        self.root.add_mutation(self.ref.extra, "append", val)


class TraceList(Tracable):
    def __init__(self, val, ref, server, root):
        self.val = val
        self.ref = ref
        self.server: ObjectServer = server
        self.root = root
        if self.root is None:
            self.root = self

    def __getitem__(self, i):
        return make_trace_obj(self.val[i], self.ref.with_id(i), self.server, self.root)

    def __eq__(self, other):
        return self.val == other


class TraceDict(Tracable):
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
        return self.val.items()

    def __iter__(self):
        return iter(self.val)

    def __repr__(self):
        return f"TraceDict({self.val})"

    def __eq__(self, other):
        return self.val == other


def make_trace_obj(
    val: Any, new_ref: Ref, server: ObjectServer, root: Optional[Tracable]
):
    # Derefence val and create the appropriate wrapper object
    extra: list[str] = []
    if isinstance(val, ObjectRef):
        extra = val.extra
        val = server._resolve_object(val.name, "latest")

    if isinstance(val, ValRef):
        val = server.get_val(val)
    elif isinstance(val, TableRef):
        val = TraceTable(val, new_ref, server, {}, root)

    if extra:
        # This is where extra resolution happens?
        for extra_index in range(0, len(extra), 2):
            if extra[extra_index] == "key":
                val = val[extra[extra_index + 1]]
            elif extra[extra_index] == "attr":
                val = getattr(val, extra[extra_index + 1])
            elif extra[extra_index] == "id":
                val = val[extra[extra_index + 1]]
            else:
                raise ValueError(f"Unknown ref type: {val}")

            # need to deref if we encounter these
            if isinstance(val, ValRef):
                val = server.get_val(val)
            elif isinstance(val, TableRef):
                val = TraceTable(val, new_ref, server, {}, root)

    if isinstance(val, ObjectRecord):
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
    if dataclasses.is_dataclass(obj):
        return ObjectRecord(
            {
                "_type": obj.__class__.__name__,
                **{k: map_to_refs(v) for k, v in dataclasses.asdict(obj).items()},
            },
        )
    elif isinstance(obj, list):
        return [map_to_refs(v) for v in obj]
    elif isinstance(obj, dict):
        return {k: map_to_refs(v) for k, v in obj.items()}
    ref = get_ref(obj)
    if ref:
        return ref
    return obj


@dataclasses.dataclass
class Dataset:
    rows: list[Any]


@dataclasses.dataclass
class Call:
    op_name: str
    inputs: dict
    id: Optional[uuid.UUID] = None
    parent_id: Optional[uuid.UUID] = None
    output: Any = None


class ValueIter:
    server: ObjectServer
    filter: ValueFilter

    def __init__(self, server, filter: ValueFilter):
        self.server = server
        self.filter = filter

    def __iter__(self):
        page_index = 0
        page_size = 10
        while True:
            page_data = self.server.query_vals(
                self.filter, offset=page_index * page_size, limit=page_size
            )
            for call in page_data:
                yield make_trace_obj(call, ValRef(call.id), self.server, None)
            if len(page_data) < page_size:
                break
            page_index += 1


class ObjectClient:
    def __init__(self):
        self.server = ObjectServer()

    def save(self, val, name: str, branch: str = "latest") -> Any:
        val = map_to_refs(val)
        ref = self.server.new_object(val, name, branch)
        return self.get(ref)

    def get(self, ref: ObjectRef):
        val = self.server.get_val(ValRef(ref.val_id))

        return make_trace_obj(val, ref, self.server, None)

    def calls(self, filter: ValueFilter):
        filt = copy.deepcopy(filter)
        if "val" not in filt:
            filt["val"] = {}
        filt["val"]["_type"] = "Call"
        return ValueIter(self.server, filt)

    def call(self, call_id: uuid.UUID) -> Optional[Call]:
        return self.server.get_val(ValRef(call_id))

    def create_call(self, op_name: str, inputs: dict):
        inputs = map_to_refs(inputs)
        call = Call(op_name, inputs)
        val_ref = self.server.new_val(call)
        call.id = val_ref.val_id
        return call

    def finish_call(self, call: Call, output: Any):
        call.output = output
        self.server.new_val(call, value_id=call.id)


# TODO
# Fix types
# Pull out value type to top-level

# TODO
#
# must prove
#   - [x] mutations (append, set, remove)
#   - calls on dataset rows are stable
#   - batch ref resolution in call query / dataset join path
#   - custom objects
#   - files
#   - ensure true client/server wire interface
#   - table ID refs instead of index
#   - dedupe, content ID
#   - efficient walking of all relationships
#   - call outputs as refs
#   - performance tests
#
# perf related
#   - pull out _type to top-level of value and index
#   - don't encode UUID
# code quality
#   - clean up mutation stuff
#   - merge extra stuff in refs
#   - naming: Value / Object / Record etc.
# bugs
#   - filter non-string
#   - filter table when not dicts

# Biggest question, can the val table be stored as a table?
