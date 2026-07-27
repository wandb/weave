import pytest

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.errors import InvalidFieldError
from weave.trace_server.orm import (
    Column,
    ParamBuilder,
    Table,
    _transform_external_field_to_internal_field,
    combine_conditions,
    python_value_to_ch_type,
    quote_json_path,
    quote_json_path_parts,
    split_escaped_field_path,
)


def test_python_value_to_ch_type_negative_integers():
    """Negative integers must map to a signed type (Int64), not UInt64.

    Requirement: Numeric filter literals support negative values
    Interface: python_value_to_ch_type() return value used in ClickHouse query params
    Given: A negative integer like -1 or -100
    When: python_value_to_ch_type is called
    Then: Returns "Int64" (signed), not "UInt64" (unsigned)
    """
    # Negative integers must use a signed type
    assert python_value_to_ch_type(-1) == "Int64"
    assert python_value_to_ch_type(-100) == "Int64"

    # Positive integers should also work with signed type
    assert python_value_to_ch_type(0) == "Int64"
    assert python_value_to_ch_type(42) == "Int64"

    # Floats (including negative) should remain Float64
    assert python_value_to_ch_type(-0.1) == "Float64"
    assert python_value_to_ch_type(3.14) == "Float64"


def test_parambuilder_clickhouse():
    pb = ParamBuilder()
    name = pb.add("bar", "foo", "String")
    assert name == "{foo:String}"
    name = pb.add(12, "bim")
    assert name == "{bim:Int64}"
    assert pb.get_params() == {
        "foo": "bar",
        "bim": 12,
    }


def test_add_param_dedups_by_type_not_just_value():
    """Equal-but-differently-typed values must not share a param (WB-37505).

    Python treats True == 1 == 1.0 as equal with equal hashes, so a value-only
    dedup cache would hand a bool literal and an int the same param name. That
    one param then renders under two ClickHouse types (e.g. Bool and UInt64),
    and ClickHouse rejects "True cannot be parsed as UInt64". Keying on
    (type, value) keeps them distinct while still deduping genuine repeats.
    """
    pb = ParamBuilder(prefix="pb")
    assert pb.add_param(True) == "pb_0"
    assert pb.add_param(1) == "pb_1"
    assert pb.add_param(False) == "pb_2"
    assert pb.add_param(0) == "pb_3"
    assert pb.add_param(1.0) == "pb_4"

    # Genuine repeats (same type and value) still dedup to the first param.
    assert pb.add_param(True) == "pb_0"
    assert pb.add_param(1) == "pb_1"

    # Assert on type identity, not ==: True == 1 == 1.0 would hide the bug.
    params = pb.get_params()
    assert params["pb_0"] is True
    assert params["pb_2"] is False
    assert type(params["pb_1"]) is int
    assert type(params["pb_3"]) is int
    assert type(params["pb_4"]) is float
    assert params == {"pb_0": True, "pb_1": 1, "pb_2": False, "pb_3": 0, "pb_4": 1.0}


def test_combine_conditions():
    with pytest.raises(ValueError, match="Invalid operator"):
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


def test_quote_json_path_array_indices():
    """Non-negative ints bracket-index; negative indices are rejected.

    ClickHouse JSON_VALUE's JSONPath grammar rejects negative array indices
    (`[-1]`) with BAD_ARGUMENTS, 502-ing the whole request. We reject them at
    compile time as a client-facing InvalidFieldError (HTTP 422) instead.
    """
    assert quote_json_path_parts(["a", "0", "2"]) == '$."a"[0][2]'
    assert quote_json_path("output.scores.0") == '$."output"."scores"[0]'

    with pytest.raises(InvalidFieldError, match="Negative array index '-1'"):
        quote_json_path_parts(["turn", "user_prompt_parts", "-1"])
    with pytest.raises(InvalidFieldError, match="Negative array index '-1'"):
        quote_json_path("turn.user_prompt_parts.-1")
    with pytest.raises(InvalidFieldError, match="Negative array index '-2'"):
        _transform_external_field_to_internal_field(
            "payload.turn.user_prompt_parts.-2",
            all_columns=["payload_dump"],
            json_columns=["payload"],
        )


def test_transform_external_field_to_internal_field():
    all_columns = ["id", "creator", "payload_dump"]
    json_columns = ["payload"]

    # Transforming a column that doesn't exist should raise
    with pytest.raises(ValueError, match="Unknown field"):
        _transform_external_field_to_internal_field(
            "foo", all_columns=all_columns, json_columns=json_columns
        )

    result = _transform_external_field_to_internal_field(
        "id", all_columns=all_columns, json_columns=json_columns
    )
    assert result[0] == "id"
    assert result[2] == {"id"}
    result = _transform_external_field_to_internal_field(
        "payload", all_columns=all_columns, json_columns=json_columns
    )
    assert result[0] == "payload_dump"
    assert result[2] == {"payload_dump"}
    pb = ParamBuilder(prefix="pb")
    result = _transform_external_field_to_internal_field(
        "payload.address",
        all_columns=all_columns,
        json_columns=json_columns,
        param_builder=pb,
    )
    assert result[0] == "toString(JSON_VALUE(payload_dump, {pb_0:String}))"
    assert result[2] == {"payload_dump"}


def test_array_string_column_round_trip():
    table = Table("t", [Column("id", "string"), Column("tags", "array_string")])
    insert = table.insert({"id": "a", "tags": ["x", "y"]})
    prepared = insert.prepare()
    # ClickHouse driver accepts native list; ORM must not JSON-encode it.
    assert prepared.data == [["a", ["x", "y"]]]
    # Reading back a CH row returns a native list and ORM passes it through.
    assert table.tuple_to_row(("a", ["x", "y"]), ["id", "tags"]) == {
        "id": "a",
        "tags": ["x", "y"],
    }


def test_map_string_float_column_round_trip():
    table = Table(
        "t",
        [Column("id", "string"), Column("ratings", "map_string_float")],
    )
    payload = {"_rating_": 0.87}
    ch_prepared = table.insert({"id": "a", "ratings": payload}).prepare()
    assert ch_prepared.data == [["a", payload]]
    assert table.tuple_to_row(("a", payload), ["id", "ratings"]) == {
        "id": "a",
        "ratings": payload,
    }


def test_select_query_collection_size_with_or():
    table = Table(
        "feedback",
        [
            Column("id", "string"),
            Column("tags", "array_string"),
            Column("ratings", "map_string_float"),
        ],
    )

    query = tsi.Query.model_validate(
        {
            "$expr": {
                "$or": [
                    {
                        "$gt": [
                            {"$size": {"$getField": "tags"}},
                            {"$literal": 0},
                        ]
                    },
                    {
                        "$gt": [
                            {"$size": {"$getField": "ratings"}},
                            {"$literal": 0},
                        ]
                    },
                ]
            }
        }
    )
    prepared = (
        table.select()
        .project_id("entity/project")
        .where(query)
        .prepare(ParamBuilder("test"))
    )

    assert (
        prepared.sql
        == """SELECT id, tags, ratings
FROM feedback
WHERE ((project_id = {project_id:String}) AND (((length(tags) > {test_1:Int64}) OR (length(ratings) > {test_2:Int64}))))"""
    )
    assert prepared.parameters == {
        "project_id": "entity/project",
        "test_1": 0,
        "test_2": 0,
    }
    assert prepared.fields == ["id", "tags", "ratings"]


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
    prepared = select.prepare()
    assert (
        prepared.sql
        == """SELECT id, creator, payload_dump
FROM users
LIMIT {limit:UInt64}"""
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
    pb = ParamBuilder(prefix="pb")
    prepared = select.prepare(param_builder=pb)
    assert (
        prepared.sql
        == """SELECT id, toString(JSON_VALUE(payload_dump, {pb_0:String}))
FROM users"""
    )
    assert prepared.parameters == {"pb_0": '$."address"'}
    assert prepared.fields == ["id", "payload.address"]


def test_join():
    table1 = Table(
        "users",
        [
            Column("id", "string"),
            Column("creator", "string", nullable=True),
            Column("payload", "json", db_name="payload_dump"),
        ],
    )
    table2 = Table(
        "roles",
        [
            Column("id", "string"),
            Column("name", "string"),
        ],
    )

    select = (
        table1.select()
        .fields(["id", "name"])
        .join(
            table2,
            tsi.Query(
                **{
                    "$expr": {
                        "$eq": [
                            {"$getField": "table1.id"},
                            {"$getField": "table2.id"},
                        ]
                    }
                }
            ),
        )
    )

    prepared = select.prepare()

    assert (
        prepared.sql
        == """SELECT id, name
FROM users
JOIN roles ON (table1.id = table2.id)"""
    )


def test_join_with_join_type():
    table1 = Table(
        "users",
        [
            Column("id", "string"),
            Column("creator", "string", nullable=True),
            Column("payload", "json", db_name="payload_dump"),
        ],
    )
    table2 = Table(
        "roles",
        [
            Column("id", "string"),
            Column("name", "string"),
        ],
    )

    select = (
        table1.select()
        .fields(["id", "name"])
        .join(
            table2,
            tsi.Query(
                **{
                    "$expr": {
                        "$eq": [
                            {"$getField": "table1.id"},
                            {"$getField": "table2.id"},
                        ]
                    }
                }
            ),
            "inner",
        )
    )

    prepared = select.prepare()

    assert (
        prepared.sql
        == """SELECT id, name
FROM users
inner JOIN roles ON (table1.id = table2.id)"""
    )


def test_join_global():
    table1 = Table(
        "users",
        [
            Column("id", "string"),
            Column("creator", "string", nullable=True),
            Column("payload", "json", db_name="payload_dump"),
        ],
    )
    table2 = Table(
        "roles",
        [
            Column("id", "string"),
            Column("name", "string"),
        ],
    )

    select = (
        table1.select()
        .fields(["id", "name"])
        .join(
            table2,
            tsi.Query(
                **{
                    "$expr": {
                        "$eq": [
                            {"$getField": "table1.id"},
                            {"$getField": "table2.id"},
                        ]
                    }
                }
            ),
            "LEFT",
            global_=True,
        )
    )

    prepared = select.prepare()

    assert (
        prepared.sql
        == """SELECT id, name
FROM users
GLOBAL LEFT JOIN roles ON (table1.id = table2.id)"""
    )

    join_query = tsi.Query(
        **{"$expr": {"$eq": [{"$getField": "table1.id"}, {"$getField": "table2.id"}]}}
    )
    no_type = (
        table1.select().fields(["id", "name"]).join(table2, join_query, global_=True)
    )
    assert (
        no_type.prepare().sql
        == """SELECT id, name
FROM users
GLOBAL JOIN roles ON (table1.id = table2.id)"""
    )


def test_group_by():
    table = Table(
        "users",
        [
            Column("id", "string"),
            Column("creator", "string", nullable=True),
            Column("payload", "json", db_name="payload_dump"),
        ],
    )

    select = table.select().fields(["id", "creator"]).group_by(["id", "creator"])

    prepared = select.prepare()

    assert (
        prepared.sql
        == """SELECT id, creator
FROM users
GROUP BY id, creator"""
    )


def test_split_escaped_field_path() -> None:
    """Test that split_escaped_field_path correctly handles escaped dots in field names."""
    # Normal case - no escaping
    assert split_escaped_field_path("output.metrics.run") == [
        "output",
        "metrics",
        "run",
    ]

    # Single escaped dot in middle segment
    assert split_escaped_field_path("output.metrics\\.run.actor") == [
        "output",
        "metrics.run",
        "actor",
    ]

    # Multiple escaped dots in one segment
    assert split_escaped_field_path("output.a\\.b\\.c.d") == ["output", "a.b.c", "d"]

    # Escaped dot at start of segment
    assert split_escaped_field_path("output.\\.hidden") == ["output", ".hidden"]

    # Multiple segments with escaping
    assert split_escaped_field_path("output.metrics\\.scorer\\.run.actor\\.phase") == [
        "output",
        "metrics.scorer.run",
        "actor.phase",
    ]

    # Single field (no dots)
    assert split_escaped_field_path("output") == ["output"]

    # All dots escaped (single field with dots in name)
    assert split_escaped_field_path("output\\.metrics\\.run") == ["output.metrics.run"]

    # Edge case: trailing dot (unescaped)
    assert split_escaped_field_path("output.metrics.") == ["output", "metrics", ""]

    # Edge case: leading dot (unescaped)
    assert split_escaped_field_path(".output") == ["", "output"]


def _feedback_table() -> Table:
    return Table(
        "feedback",
        [
            Column("id", "string"),
            Column("feedback_type", "string"),
            Column("created_at", "datetime"),
            Column("payload", "json", db_name="payload_dump"),
        ],
    )


def _prepare_clickhouse(select):
    return select.prepare(param_builder=ParamBuilder(prefix="pb"))


@pytest.mark.parametrize(
    ("literal", "expected_field_sql", "expected_param_value", "expected_param_type"),
    [
        # Bool literals: JSON_VALUE returns 'true'/'false' strings, so
        # multiIf must coerce both before falling back to numeric coercion.
        (
            False,
            "multiIf(JSON_VALUE(payload_dump, {pb_0:String}) = 'true', 1, "
            "JSON_VALUE(payload_dump, {pb_0:String}) = 'false', 0, "
            "toUInt8OrNull(JSON_VALUE(payload_dump, {pb_0:String})))",
            False,
            "Bool",
        ),
        (
            True,
            "multiIf(JSON_VALUE(payload_dump, {pb_0:String}) = 'true', 1, "
            "JSON_VALUE(payload_dump, {pb_0:String}) = 'false', 0, "
            "toUInt8OrNull(JSON_VALUE(payload_dump, {pb_0:String})))",
            True,
            "Bool",
        ),
        (
            5,
            "toInt64OrNull(JSON_VALUE(payload_dump, {pb_0:String}))",
            5,
            "Int64",
        ),
        (
            2.5,
            "toFloat64OrNull(JSON_VALUE(payload_dump, {pb_0:String}))",
            2.5,
            "Float64",
        ),
    ],
)
def test_feedback_query_infers_cast_from_literal(
    literal, expected_field_sql, expected_param_value, expected_param_type
) -> None:
    """Regression for WB-33832: /feedback/query 500s with NO_COMMON_TYPE.

    JSON_VALUE returns a string and the literal is bound with its native CH
    type, so without inference ClickHouse refuses the comparison. The peer
    literal's type now drives the field-side cast.
    """
    select = (
        _feedback_table()
        .select()
        .fields(["id"])
        .where(
            tsi.Query(
                **{
                    "$expr": {
                        "$eq": [
                            {"$getField": "payload.is_positive"},
                            {"$literal": literal},
                        ]
                    }
                }
            )
        )
    )
    prepared = _prepare_clickhouse(select)
    assert prepared.sql == (
        "SELECT id\n"
        "FROM feedback\n"
        f"WHERE ({expected_field_sql} = {{pb_1:{expected_param_type}}})"
    )
    assert prepared.parameters == {
        "pb_0": '$."is_positive"',
        "pb_1": expected_param_value,
    }


def test_feedback_query_string_literal_keeps_uncast_path() -> None:
    """String literals must keep the existing toString(JSON_VALUE(...)) path.

    Inferring a cast for strings would break legitimate JSON-string
    comparisons (e.g. category fields).
    """
    select = (
        _feedback_table()
        .select()
        .fields(["id"])
        .where(
            tsi.Query(
                **{
                    "$expr": {
                        "$eq": [
                            {"$getField": "payload.label"},
                            {"$literal": "ok"},
                        ]
                    }
                }
            )
        )
    )
    prepared = _prepare_clickhouse(select)
    assert prepared.sql == (
        "SELECT id\n"
        "FROM feedback\n"
        "WHERE (toString(JSON_VALUE(payload_dump, {pb_0:String})) = {pb_1:String})"
    )


def test_feedback_query_explicit_convert_overrides_inference() -> None:
    """An explicit $convert wins over inference and is not double-cast."""
    select = (
        _feedback_table()
        .select()
        .fields(["id"])
        .where(
            tsi.Query(
                **{
                    "$expr": {
                        "$eq": [
                            {
                                "$convert": {
                                    "input": {"$getField": "payload.is_positive"},
                                    "to": "bool",
                                },
                            },
                            {"$literal": True},
                        ]
                    }
                }
            )
        )
    )
    prepared = _prepare_clickhouse(select)
    # ConvertOperation runs after process_operand for the field, so the cast
    # we infer for the field side has no effect (the inner JSON_VALUE
    # already wears toString from the default), and the outer cast wins.
    assert prepared.sql == (
        "SELECT id\n"
        "FROM feedback\n"
        "WHERE (toUInt8OrNull(toString(JSON_VALUE(payload_dump, {pb_0:String}))) = {pb_1:Bool})"
    )


def test_feedback_query_literal_on_lhs_casts_field_on_rhs() -> None:
    """Inference works regardless of which side carries the literal."""
    select = (
        _feedback_table()
        .select()
        .fields(["id"])
        .where(
            tsi.Query(
                **{
                    "$expr": {
                        "$gt": [
                            {"$literal": 3},
                            {"$getField": "payload.score"},
                        ]
                    }
                }
            )
        )
    )
    prepared = _prepare_clickhouse(select)
    assert prepared.sql == (
        "SELECT id\n"
        "FROM feedback\n"
        "WHERE ({pb_0:Int64} > toInt64OrNull(JSON_VALUE(payload_dump, {pb_1:String})))"
    )


def test_feedback_query_in_homogeneous_literal_list_casts_field() -> None:
    """$in with a homogeneous numeric list infers a single cast for the field."""
    select = (
        _feedback_table()
        .select()
        .fields(["id"])
        .where(
            tsi.Query(
                **{
                    "$expr": {
                        "$in": [
                            {"$getField": "payload.score"},
                            [{"$literal": 1}, {"$literal": 2}, {"$literal": 3}],
                        ]
                    }
                }
            )
        )
    )
    prepared = _prepare_clickhouse(select)
    assert prepared.sql == (
        "SELECT id\n"
        "FROM feedback\n"
        "WHERE (toInt64OrNull(JSON_VALUE(payload_dump, {pb_0:String})) "
        "IN ({pb_1:Int64},{pb_2:Int64},{pb_3:Int64}))"
    )


def test_feedback_query_inference_threads_through_and_or_not() -> None:
    """Inference is per-binary-op, so each leaf inside AND/OR/NOT must
    independently resolve its own cast. This pins that nested combinators
    don't drop the inference (e.g. by accidentally short-circuiting in
    process_operation before reaching the leaf).
    """
    select = (
        _feedback_table()
        .select()
        .fields(["id"])
        .where(
            tsi.Query(
                **{
                    "$expr": {
                        "$and": [
                            {
                                "$eq": [
                                    {"$getField": "payload.is_positive"},
                                    {"$literal": False},
                                ]
                            },
                            {
                                "$or": [
                                    {
                                        "$gt": [
                                            {"$getField": "payload.score"},
                                            {"$literal": 0.5},
                                        ]
                                    },
                                    {
                                        "$not": [
                                            {
                                                "$eq": [
                                                    {"$getField": "payload.rank"},
                                                    {"$literal": 1},
                                                ]
                                            }
                                        ]
                                    },
                                ]
                            },
                        ]
                    }
                }
            )
        )
    )
    prepared = _prepare_clickhouse(select)
    bool_field = (
        "multiIf(JSON_VALUE(payload_dump, {pb_0:String}) = 'true', 1, "
        "JSON_VALUE(payload_dump, {pb_0:String}) = 'false', 0, "
        "toUInt8OrNull(JSON_VALUE(payload_dump, {pb_0:String})))"
    )
    score_field = "toFloat64OrNull(JSON_VALUE(payload_dump, {pb_2:String}))"
    rank_field = "toInt64OrNull(JSON_VALUE(payload_dump, {pb_4:String}))"
    assert prepared.sql == (
        "SELECT id\n"
        "FROM feedback\n"
        f"WHERE (({bool_field} = {{pb_1:Bool}}) "
        f"AND (({score_field} > {{pb_3:Float64}}) "
        f"OR (NOT (({rank_field} = {{pb_5:Int64}})))))"
    )


def test_feedback_query_in_mixed_literal_list_keeps_uncast_path() -> None:
    """A heterogeneous $in list cannot share a single cast and falls back."""
    select = (
        _feedback_table()
        .select()
        .fields(["id"])
        .where(
            tsi.Query(
                **{
                    "$expr": {
                        "$in": [
                            {"$getField": "payload.value"},
                            [{"$literal": 1}, {"$literal": "two"}],
                        ]
                    }
                }
            )
        )
    )
    prepared = _prepare_clickhouse(select)
    assert prepared.sql == (
        "SELECT id\n"
        "FROM feedback\n"
        "WHERE (toString(JSON_VALUE(payload_dump, {pb_0:String})) "
        "IN ({pb_1:Int64},{pb_2:String}))"
    )


@pytest.mark.parametrize(
    ("field", "literal", "expected_param"),
    [
        # Regression for WB-34897: the exact ISO-8601 shape (T separator + Z
        # suffix) ClickHouse rejected against a DateTime64 column.
        ("created_at", "2026-05-27T17:49:15.491230Z", "2026-05-27 17:49:15.491230"),
        ("created_at", "2026-05-27T17:49:15", "2026-05-27 17:49:15.000000"),
        ("created_at", "2026-05-27", "2026-05-27 00:00:00.000000"),
        # Numeric unix timestamps normalize to the same canonical form.
        ("created_at", 1709251200, "2024-03-01 00:00:00.000000"),
        # A non-DateTime column with an ISO-looking string is left untouched.
        (
            "feedback_type",
            "2026-05-27T17:49:15.491230Z",
            "2026-05-27T17:49:15.491230Z",
        ),
    ],
)
def test_feedback_query_normalizes_datetime_literal(
    field, literal, expected_param
) -> None:
    """DateTime-column literals are rewritten to CH-native datetime strings.

    ClickHouse cannot convert ISO-8601 `T`/`Z` strings to DateTime64, so a
    literal compared against a DateTime column is normalized to the canonical
    `YYYY-MM-DD HH:MM:SS.ffffff` form. Non-DateTime columns are unaffected.
    """
    select = (
        _feedback_table()
        .select()
        .fields(["id"])
        .where(
            tsi.Query(
                **{"$expr": {"$gte": [{"$getField": field}, {"$literal": literal}]}}
            )
        )
    )
    prepared = _prepare_clickhouse(select)
    assert prepared.sql == (
        f"SELECT id\nFROM feedback\nWHERE ({field} >= {{pb_0:String}})"
    )
    assert prepared.parameters == {"pb_0": expected_param}
