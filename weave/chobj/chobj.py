from typing import Optional
import clickhouse_connect
import uuid
import json
import dataclasses
import time


class Ref:
    pass


@dataclasses.dataclass
class TableRef(Ref):
    table_id: uuid.UUID


@dataclasses.dataclass
class ValRef(Ref):
    val_id: uuid.UUID


class RefEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, TableRef):
            return {"_type": "TableRef", "table_id": o.table_id}
        elif isinstance(o, ValRef):
            return {"_type": "ValRef", "val_id": o.val_id}
        elif isinstance(o, uuid.UUID):
            return {"_type": "UUID", "uuid": o.hex}
        return json.JSONEncoder.default(self, o)


def ref_decoder(d):
    if "_type" in d:
        if d["_type"] == "TableRef":
            return TableRef(d["table_id"])
        elif d["_type"] == "ValRef":
            return ValRef(d["val_id"])
        elif d["_type"] == "UUID":
            return uuid.UUID(d["uuid"])
    return d


class CHClient:
    def __init__(self):
        self.client = clickhouse_connect.get_client()

    def drop_tables(self):
        self.client.command("DROP TABLE IF EXISTS values")
        self.client.command("DROP TABLE IF EXISTS tables")
        self.client.command("DROP TABLE IF EXISTS table_transactions")

    def create_tables(self):
        self.client.command(
            """
            CREATE TABLE IF NOT EXISTS values
            (
                id UUID,
                val String
            ) 
            ENGINE = MergeTree() 
            ORDER BY (id)"""
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
            (tx_id, uuid.uuid4().hex, i, json.dumps(v))
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

    def get_table(self, table_ref: TableRef):
        query_result = self.client.query(
            """
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
            WHERE item_record_index = 1 AND val IS NOT NULL
            """,
            parameters={
                "table_id": table_ref.table_id,
            },
        )
        for row in query_result.result_rows:
            yield json.loads(row[0])

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

    def new_val(self, val):
        # map val (this could do more than lists_to_tables)
        def lists_to_tables(val):
            if isinstance(val, dict):
                return {k: lists_to_tables(v) for k, v in val.items()}
            elif isinstance(val, list):
                return self.new_table(val)
            return val

        val = lists_to_tables(val)

        # encode val
        encoded_val = json.dumps(val, cls=RefEncoder)

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
            SELECT val from values WHERE id = %(value_id)s
            """,
            parameters={"value_id": val_ref.val_id},
        )
        val = json.loads(query_result.result_rows[0][0], object_hook=ref_decoder)
        if isinstance(val, Ref):
            return self.get(val)
        elif isinstance(val, dict):
            val = {k: self.get(v) if isinstance(v, Ref) else v for k, v in val.items()}
        return val

    def get(self, val_ref: Ref):
        if isinstance(val_ref, TableRef):
            return list(self.get_table(val_ref))
        elif isinstance(val_ref, ValRef):
            return self.get_val(val_ref)
        else:
            raise ValueError(f"Unknown ref type: {val_ref}")


# OK so I need
#   - append and set mutations
#   - files
#   - hook it into the client somehow
