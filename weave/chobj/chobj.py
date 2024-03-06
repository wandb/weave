from typing import Optional, Any
import clickhouse_connect
import copy
import uuid
import json
import dataclasses

from weave import box


class Ref:
    pass


@dataclasses.dataclass
class TableRef(Ref):
    table_id: uuid.UUID


@dataclasses.dataclass
class ValRef(Ref):
    val_id: uuid.UUID
    extra: list[str] = dataclasses.field(default_factory=list)

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


def make_value_filter(filter: dict):
    query_parts = []
    for key, value in filter.items():
        # Assume all values are to be treated as strings for simplicity. Adjust the casting as necessary.
        query_part = f"JSONExtractString(val, '{key}') = '{value}'"
        query_parts.append(query_part)
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
                val Nullable(String)
            ) 
            ENGINE = MergeTree() 
            ORDER BY (id, tx_order)"""
        )

    def new_table(self, initial_table: list):
        tx_id = uuid.uuid4().hex
        tx_items = [
            (tx_id, uuid.uuid4().hex, i, json_dumps(v))
            for i, v in enumerate(initial_table)
        ]
        self.client.insert(
            "table_transactions",
            data=tx_items,
            column_names=("id", "item_id", "tx_order", "val"),
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
        filter: Optional[dict] = None,
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
            val
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
        return [json_loads(r[0]) for r in query_result.result_rows]

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
            data=[(value_id, encoded_val)],
            column_names=("id", "val"),
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
        self, filter: dict, offset: Optional[int] = 0, limit: Optional[int] = 100
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


class TraceObject:
    def __init__(self, val, ref, server):
        self.val = val
        self.ref = ref
        self.server = server

    def __getattribute__(self, __name: str) -> Any:
        try:
            return object.__getattribute__(self, __name)
        except AttributeError:
            pass
        return make_trace_obj(
            object.__getattribute__(self.val, __name),
            self.ref.with_attr(__name),
            self.server,
        )

    def __repr__(self):
        return f"TraceObject({self.val})"

    def __eq__(self, other):
        return self.val == other


class TraceTable:
    def __init__(self, table_ref, ref, server, filter):
        self.table_ref = table_ref
        self.filter = filter
        self.ref = ref
        self.server: ObjectServer = server

    def __iter__(self):
        page_index = 0
        page_size = 1
        i = 0
        while True:
            page_data = self.server.table_query(
                self.table_ref,
                self.filter,
                offset=page_index * page_size,
                limit=page_size,
            )
            for item in page_data:
                yield make_trace_obj(item, self.ref.with_id(i), self.server)
            if len(page_data) < page_size:
                break
            i += 1
            page_index += 1


class TraceList:
    def __init__(self, val, ref, server):
        self.val = val
        self.ref = ref
        self.server: ObjectServer = server

    def __getitem__(self, i):
        return make_trace_obj(self.val[i], self.ref.with_id(i), self.server)

    def __eq__(self, other):
        return self.val == other


class TraceDict:
    def __init__(self, val, ref, server):
        self.val = val
        self.ref = ref
        self.server = server

    def __getitem__(self, key):
        return make_trace_obj(self.val[key], self.ref.with_key(key), self.server)

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


def make_trace_obj(val: Any, new_ref: Ref, server: ObjectServer):
    # Derefence val and create the appropriate wrapper object
    if isinstance(val, TableRef):
        return TraceTable(val, new_ref, server, {})
    if isinstance(val, ObjectRef):
        obj = server._resolve_object(val.name, "latest")
        if isinstance(obj, ValRef):
            obj = server.get_val(obj)
        elif isinstance(obj, Ref):
            raise ValueError(f"Unexpected type: {obj}")
        # This is where extra resolution happens?
        for extra_index in range(0, len(val.extra), 2):
            if val.extra[extra_index] == "key":
                obj = obj[val.extra[extra_index + 1]]
            elif val.extra[extra_index] == "attr":
                obj = getattr(obj, val.extra[extra_index + 1])
            elif val.extra[extra_index] == "id":
                obj = obj[val.extra[extra_index + 1]]
            else:
                raise ValueError(f"Unknown ref type: {val}")
        val = obj
    if isinstance(val, ObjectRecord):
        return TraceObject(val, new_ref, server)
    elif isinstance(val, list):
        return TraceList(val, new_ref, server)
    elif isinstance(val, dict):
        return TraceDict(val, new_ref, server)
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
class Call:
    op_name: str
    inputs: dict
    id: Optional[uuid.UUID] = None
    parent_id: Optional[uuid.UUID] = None
    output: Any = None


class ValueIter:
    def __init__(self, server, filter):
        self.server = server
        self.filter = filter

    def __iter__(self):
        page_index = 0
        page_size = 1
        while True:
            page_data = self.server.query_vals(
                self.filter, offset=page_index * page_size, limit=page_size
            )
            for call in page_data:
                yield make_trace_obj(call, ValRef(call.id), self.server)
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

        return make_trace_obj(val, ref, self.server)

    def calls(self, filter: dict):
        filt = copy.copy(filter)
        filt["_type"] = "Call"
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
#   - refactor paging stuff to ensure its shared
#   - batch ref resolution in call query / dataset join path
#   - ensure true client/server wire interface
#   - mutations (append, set, remove)
#   - files
#   - client queries / filters / client objects
#   - table ID refs instead of index
#   - dedupe, content ID
#   - efficient walking of all relationships
#   - pull out _type to top-level of value and index
#   - don't encode UUID
#   - call outputs as refs
#   - merge extra stuff in refs
#   - filter non-string
#   - filter table when not dicts

# Biggest question, can the val table be stored as a table?
