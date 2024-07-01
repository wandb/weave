import pytest

from weave.trace_server.orm import (
    Column,
    ParamBuilder,
    Table,
    _transform_external_field_to_internal_field,
    combine_conditions,
)


def test_parambuilder_clickhouse():
    pb = ParamBuilder(database_type="clickhouse")
    name = pb.add("bar", "foo", "String")
    assert name == "{foo:String}"
    name = pb.add(12, "bim")
    assert name == "{bim:UInt64}"
    assert pb.get_params() == {
        "foo": "bar",
        "bim": 12,
    }


def test_parambuilder_sqlite():
    pb = ParamBuilder(database_type="sqlite")
    placeholder = pb.add("bar", "foo", "String")
    assert placeholder == ":foo"
    placeholder = pb.add(12, "bim")
    assert placeholder == ":bim"
    assert pb.get_params() == {
        "foo": "bar",
        "bim": 12,
    }


def test_combine_conditions():
    with pytest.raises(ValueError):
        combine_conditions([], "NOT")

    assert combine_conditions([], "AND") == ""
    assert combine_conditions(["foo = 'bar'"], "AND") == "foo = 'bar'"
    assert combine_conditions(["foo = 'bar'"], "OR") == "foo = 'bar'"
    assert (
        combine_conditions(["foo = 'bar'", "bim = 12"], "AND")
        == "((foo = 'bar') AND (bim = 12))"
    )
    assert (
        combine_conditions(["foo = 'bar'", "bim = 12"], "OR")
        == "((foo = 'bar') OR (bim = 12))"
    )


def test_transform_external_field_to_internal_field():
    all_columns = ["id", "creator", "payload_dump"]
    json_columns = ["payload"]

    # Transforming a column that doesn't exist should raise
    with pytest.raises(ValueError):
        _transform_external_field_to_internal_field("foo", all_columns, json_columns)

    result = _transform_external_field_to_internal_field(
        "id", all_columns, json_columns
    )
    assert result[0] == "id"
    assert result[2] == {"id"}
    result = _transform_external_field_to_internal_field(
        "payload", all_columns, json_columns
    )
    assert result[0] == "payload_dump"
    assert result[2] == {"payload_dump"}
    pb = ParamBuilder(prefix="pb", database_type="sqlite")
    result = _transform_external_field_to_internal_field(
        "payload.address", all_columns, json_columns, param_builder=pb
    )
    assert result[0] == "json_extract(payload_dump, :pb_0)"
    assert result[2] == {"payload_dump"}
    pb = ParamBuilder(prefix="pb", database_type="clickhouse")
    result = _transform_external_field_to_internal_field(
        "payload.address", all_columns, json_columns, param_builder=pb
    )
    assert result[0] == "toString(JSON_VALUE(payload_dump, {pb_0:String}))"
    assert result[2] == {"payload_dump"}


def test_table_create_sql():
    table = Table(
        "users",
        [
            Column("id", "string"),
            Column("creator", "string", nullable=True),
            Column("payload", "json", db_name="payload_dump"),
        ],
    )
    assert (
        table.create_sql()
        == "CREATE TABLE IF NOT EXISTS users (\n    id TEXT,\n    creator TEXT,\n    payload_dump TEXT\n)"
    )


def test_table_drop_sql():
    table = Table(
        "users",
        [
            Column("id", "string"),
            Column("creator", "string", nullable=True),
            Column("payload", "json", db_name="payload_dump"),
        ],
    )
    assert table.drop_sql() == "DROP TABLE IF EXISTS users"


def test_select_basic():
    table = Table(
        "users",
        [
            Column("id", "string"),
            Column("creator", "string", nullable=True),
            Column("payload", "json", db_name="payload_dump"),
        ],
    )
    select = table.select()
    select = select.limit(10)
    prepared = select.prepare(database_type="clickhouse")
    assert (
        prepared.sql
        == """SELECT id, creator, payload_dump
FROM users
LIMIT {limit:UInt64}"""
    )
    assert prepared.parameters == {"limit": 10}
    assert prepared.fields == ["id", "creator", "payload_dump"]

    prepared = select.prepare(database_type="sqlite")
    assert (
        prepared.sql
        == """SELECT id, creator, payload_dump
FROM users
LIMIT :limit"""
    )
    assert prepared.parameters == {"limit": 10}
    assert prepared.fields == ["id", "creator", "payload_dump"]


def test_select_fields():
    table = Table(
        "users",
        [
            Column("id", "string"),
            Column("creator", "string", nullable=True),
            Column("payload", "json", db_name="payload_dump"),
        ],
    )
    select = table.select()
    select = select.fields(["id", "payload.address"])

    # More complicated than normal usage to fix the ParamBuilder prefix.
    pb = ParamBuilder(prefix="pb", database_type="sqlite")
    prepared = select.prepare(database_type="sqlite", param_builder=pb)
    assert (
        prepared.sql
        == """SELECT id, json_extract(payload_dump, :pb_0)
FROM users"""
    )
    assert prepared.parameters == {"pb_0": '$."address"'}
    assert prepared.fields == ["id", "payload.address"]

    pb = ParamBuilder(prefix="pb", database_type="clickhouse")
    prepared = select.prepare(database_type="clickhouse", param_builder=pb)
    assert (
        prepared.sql
        == """SELECT id, toString(JSON_VALUE(payload_dump, {pb_0:String}))
FROM users"""
    )
    assert prepared.parameters == {"pb_0": '$."address"'}
    assert prepared.fields == ["id", "payload.address"]
